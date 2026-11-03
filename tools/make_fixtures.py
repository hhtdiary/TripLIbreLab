#!/usr/bin/env python3
"""
Build synthetic TripLibre `travel.sqlite` fixtures for TripLibreLab import tests.

The schema is applied from tools/triplibre_schema.sql, which is TripLibre's migration SQL copied
verbatim, and every fixture is finished with `VACUUM INTO`, exactly as TripLibre's exporter writes
travel.sqlite. Nothing here comes from a real person: the places are public landmarks in Philadelphia
and the times, routes and GPS fixes are generated.

Usage:  python3 tools/make_fixtures.py [out_dir]      (default: fixtures/)

Fixtures written:
  travel-sample.sqlite        schema v6, one full diary day plus edge cases (see DAY below)
  travel-empty.sqlite         schema v6, no records at all
  travel-no-gps.sqlite        schema v6, trips and stays but no raw points and no route polylines
  travel-v1.sqlite            schema v1 only (no places.deleted, no stamps/expenses), one simple day
  travel-future-schema.sqlite schema v6 tables plus PRAGMA user_version = 99 (newer than Lab knows)
  not-triplibre.sqlite        a valid SQLite file with unrelated tables
  not-sqlite.sqlite           random bytes with a .sqlite name

DAY (travel-sample, local date 2026-09-15, America/New_York):
  stay  Home                 00:00-08:00
  trip  1  Home -> Penn       08:00-08:27  bicycle, polyline + raw points
  stay  Penn                 08:27-12:10
  trip  2  Penn -> Lunch      12:10-12:22  walk, polyline + raw points
  stay  Lunch (restaurant)   12:22-13:05
  trip  3  Lunch -> Penn      13:05-13:18  walk, polyline, NO raw points, has_gap = 1 (gap in the middle)
  stay  Penn                 13:18-18:00
  trip  4  Penn -> Grocery    18:00-18:35  multimodal: walk / subway / walk segments, polyline + raw points
  stay  Grocery              18:35-19:00
  trip  5  Grocery -> Home    19:00-19:20  car, NO polyline and NO raw points (endpoints only)
  stay  Home                 19:20-23:40
  trip  6  Home -> Friend     23:40-00:05 (+1 day)  taxi; departs on the 15th, arrives on the 16th
  stay  Friend               00:05-  (departure NULL: still there at export time)
  plus: one soft-deleted trip (deleted = 1) inside the day that must never be shown,
        a merged place tombstone, one stamp, one expense, and audit_log rows.
"""
from __future__ import annotations

import math
import random
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
SCHEMA = HERE / "triplibre_schema.sql"
TZ = "America/New_York"
R_EARTH = 6_371_008.8

# Public landmarks (not anyone's real home). Coordinates are approximate.
PLACES = {
    "home": ("Home", "home", 39.9526, -75.1652),               # City Hall area
    "penn": ("Penn", "work_school", 39.9522, -75.1932),        # University of Pennsylvania
    "lunch": ("Lunch spot", "restaurant", 39.9540, -75.2010),
    "grocery": ("Grocery", "grocery", 39.9480, -75.1700),
    "friend": (None, "friend_family", 39.9700, -75.1600),      # unnamed place
    "old_cafe": ("Old cafe (merged)", "cafe", 39.9523, -75.1930),
}

rng = random.Random(42)


def uid() -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def ts(day: str, hhmm: str, tz: str = TZ, plus_days: int = 0) -> float:
    d = datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz))
    return (d + timedelta(days=plus_days)).timestamp()


def haversine(a, b) -> float:
    (lat1, lon1), (lat2, lon2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(min(1, math.sqrt(h)))


def encode_polyline(coords) -> str:
    """Google encoded polyline, precision 1e-5, (lat, lon) pairs: same algorithm as TripLibre's Polyline.encode."""
    out = []
    plat = plon = 0
    for lat, lon in coords:
        ilat, ilon = round(lat * 1e5), round(lon * 1e5)
        for v in (ilat - plat, ilon - plon):
            v = ~(v << 1) if v < 0 else v << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = ilat, ilon
    return "".join(out)


def path(a, b, n: int, wobble: float = 0.0004):
    """n+1 points from a to b with a slight bow so it is not a straight line."""
    pts = []
    for i in range(n + 1):
        f = i / n
        lat = a[0] + (b[0] - a[0]) * f + wobble * math.sin(math.pi * f)
        lon = a[1] + (b[1] - a[1]) * f
        pts.append((lat, lon))
    return pts


def path_length(pts) -> float:
    return sum(haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


class Builder:
    def __init__(self, out: Path, versions: int = 6):
        self.tmp = out.with_suffix(".building.sqlite")
        for f in (self.tmp, Path(str(self.tmp) + "-wal"), Path(str(self.tmp) + "-shm")):
            if f.exists():
                f.unlink()
        self.out = out
        self.con = sqlite3.connect(self.tmp)
        self.con.execute("PRAGMA journal_mode = WAL")  # TripLibre's live database runs in WAL mode
        blocks = SCHEMA.read_text().split("-- ==== migration v")
        for block in blocks[1:]:
            v, _, sql = block.partition(" ====")
            if int(v) <= versions:
                self.con.executescript(sql)
                self.con.execute(f"PRAGMA user_version = {int(v)}")
        self.con.commit()
        self.versions = versions
        self.now = ts("2026-09-16", "09:00")  # export time
        self.place_ids: dict[str, str] = {}

    def run(self, sql: str, *args):
        self.con.execute(sql, args)

    def finish(self, user_version: int | None = None):
        self.run("INSERT OR REPLACE INTO app_meta VALUES ('last_inference_at', ?)", str(self.now))
        if user_version is not None:
            self.con.execute(f"PRAGMA user_version = {user_version}")
        self.con.commit()
        if self.out.exists():
            self.out.unlink()
        self.con.execute("VACUUM INTO ?", (str(self.out),))  # what TravelStore.backup(to:) does
        self.con.close()
        for f in (self.tmp, Path(str(self.tmp) + "-wal"), Path(str(self.tmp) + "-shm")):
            if f.exists():
                f.unlink()

    # ---- records -------------------------------------------------------------

    def place(self, key: str, source="inferred", merged_into=None, deleted=0) -> str:
        name, cat, lat, lon = PLACES[key]
        pid = uid()
        self.place_ids[key] = pid
        cols = "id, name, lat, lon, radius_m, category, favorite, source, merged_into, created_at, updated_at"
        vals = [pid, name, lat, lon, 100, cat, 1 if key == "home" else 0, source, merged_into, self.now - 86400 * 30, self.now]
        if self.versions >= 2:
            cols += ", deleted"
            vals.append(deleted)
        self.run(f"INSERT INTO places ({cols}) VALUES ({','.join('?' * len(vals))})", *vals)
        return pid

    def visit(self, place_key: str, arrival: float, departure: float | None, purpose=None,
              user_status="auto", deleted=0, point_count=12) -> str:
        vid = uid()
        _, _, lat, lon = PLACES[place_key]
        self.run(
            """INSERT INTO visits (id, place_id, arrival_ts, departure_ts, lat, lon, purpose, auto_confidence, source,
                                   user_status, deleted, tz, point_count, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            vid, self.place_ids[place_key], arrival, departure, lat + 0.00005, lon - 0.00005, purpose, 0.9,
            "inferred", user_status, deleted, TZ, point_count, None, self.now, self.now)
        return vid

    def trip(self, origin_visit: str, dest_visit: str, dep: float, arr: float, route, *,
             mode_auto=None, mode_user=None, mode_conf=None, has_gap=0, deleted=0, user_status="auto",
             raw_points=True, polyline=True, segments=None, purpose=None, notes=None) -> str:
        tid = uid()
        distance = path_length(route) if route else None
        poly = encode_polyline(route) if (route and polyline) else None
        self.run(
            """INSERT INTO trips (id, origin_visit_id, destination_visit_id, departure_ts, arrival_ts, distance_m,
                                  mode_auto, mode_confidence, mode_user, purpose, route_polyline, has_gap, auto_confidence,
                                  source, user_status, deleted, tz, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            tid, origin_visit, dest_visit, dep, arr, distance, mode_auto, mode_conf, mode_user, purpose, poly,
            has_gap, 0.95, "inferred", user_status, deleted, TZ, notes, self.now, self.now)
        if segments is None and route:
            segments = [(0.0, 1.0, mode_auto, mode_user)]
        for seq, (f0, f1, s_auto, s_user) in enumerate(segments or []):
            i0, i1 = round(f0 * (len(route) - 1)), round(f1 * (len(route) - 1))
            seg_route = route[i0:i1 + 1]
            self.run(
                """INSERT INTO trip_segments (id, trip_id, seq, start_ts, end_ts, mode_auto, mode_confidence, mode_user,
                                              distance_m, route_polyline) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                uid(), tid, seq, dep + (arr - dep) * f0, dep + (arr - dep) * f1, s_auto, mode_conf if s_auto else None,
                s_user, path_length(seg_route), encode_polyline(seg_route) if poly else None)
        if raw_points and route:
            n = len(route) - 1
            for i, (lat, lon) in enumerate(route):
                if has_gap and 0.3 < i / n < 0.7:
                    continue  # the recording gap
                t = dep + (arr - dep) * i / n
                speed = distance / (arr - dep) if distance else None
                self.run(
                    """INSERT INTO raw_location_points (ts, lat, lon, h_accuracy, altitude, v_accuracy, speed, speed_accuracy,
                                                        course, source, collector_mode, tz, inserted_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    t, lat + rng.uniform(-2e-5, 2e-5), lon + rng.uniform(-2e-5, 2e-5), 10.0, 12.0, 8.0, speed, 1.0,
                    None, "gps", "moving", TZ, t + 1)
        return tid

    def stay_points(self, place_key: str, start: float, minutes: int = 3):
        """A few fixes at the start of a stay, then the collector goes quiet (stationary marker)."""
        _, _, lat, lon = PLACES[place_key]
        t = start
        for _ in range(minutes * 2):
            self.run(
                """INSERT INTO raw_location_points (ts, lat, lon, h_accuracy, speed, source, collector_mode, tz, inserted_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                t, lat + rng.uniform(-1e-4, 1e-4), lon + rng.uniform(-1e-4, 1e-4), 15.0, 0.0, "gps", "moving", TZ, t + 1)
            t += 30
        self.run(
            """INSERT INTO raw_location_points (ts, lat, lon, h_accuracy, speed, source, collector_mode, tz, inserted_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            t, lat, lon, 15.0, 0.0, "stationary_marker", "stationary", TZ, t + 1)

    def motion(self, t: float, activity: str, confidence: int = 2):
        self.run("INSERT OR IGNORE INTO motion_activities (ts, activity, confidence) VALUES (?,?,?)", t, activity, confidence)

    def audit(self, t: float, entity_type: str, entity_id: str, action: str, field=None, old=None, new=None):
        self.run("INSERT INTO audit_log (ts, entity_type, entity_id, action, field, old_value, new_value) VALUES (?,?,?,?,?,?,?)",
                 t, entity_type, entity_id, action, field, old, new)


def coords(key: str):
    return PLACES[key][2], PLACES[key][3]


def build_day(b: Builder, *, gps: bool, day: str = "2026-09-15", full: bool = True):
    """The DAY described in the module docstring. gps=False drops every raw point and polyline."""
    for k in ("home", "penn", "lunch", "grocery", "friend"):
        b.place(k)
    if full and b.versions >= 2:
        old = b.place("old_cafe", merged_into=None)
        b.run("UPDATE places SET merged_into = ? WHERE id = ?", b.place_ids["penn"], old)

    v_home1 = b.visit("home", ts(day, "00:00") - 3600 * 5, ts(day, "08:00"), user_status="confirmed")
    v_penn1 = b.visit("penn", ts(day, "08:27"), ts(day, "12:10"))
    v_lunch = b.visit("lunch", ts(day, "12:22"), ts(day, "13:05"), purpose="meal")
    v_penn2 = b.visit("penn", ts(day, "13:18"), ts(day, "18:00"))
    v_groc = b.visit("grocery", ts(day, "18:35"), ts(day, "19:00"))
    v_home2 = b.visit("home", ts(day, "19:20"), ts(day, "23:40"))
    v_friend = b.visit("friend", ts(day, "00:05", plus_days=1), None, purpose="social")  # ongoing at export

    if gps:
        for key, start in (("home", ts(day, "00:00") - 3600 * 5), ("penn", ts(day, "08:27")), ("lunch", ts(day, "12:22")),
                           ("penn", ts(day, "13:18")), ("grocery", ts(day, "18:35")), ("home", ts(day, "19:20"))):
            b.stay_points(key, start)
            b.motion(start, "stationary")

    # 1 bicycle, polyline + raw points, user corrected walk -> bicycle
    r1 = path(coords("home"), coords("penn"), 40)
    if gps:
        b.motion(ts(day, "08:00"), "cycling")
    t1 = b.trip(v_home1, v_penn1, ts(day, "08:00"), ts(day, "08:27"), r1 if gps else None, mode_auto="walk",
                mode_conf=0.85, mode_user="bicycle", user_status="edited", raw_points=gps, polyline=gps)
    b.audit(b.now - 3600, "trip", t1, "set_mode", "mode_user", None, "bicycle")
    # 2 walk
    r2 = path(coords("penn"), coords("lunch"), 12)
    b.trip(v_penn1, v_lunch, ts(day, "12:10"), ts(day, "12:22"), r2 if gps else None, mode_auto="walk", mode_conf=0.9,
           raw_points=gps, polyline=gps)
    # 3 walk back with a GPS gap in the middle, polyline only
    r3 = path(coords("lunch"), coords("penn"), 12, wobble=-0.0004)
    b.trip(v_lunch, v_penn2, ts(day, "13:05"), ts(day, "13:18"), r3 if gps else None, mode_auto="walk", mode_conf=0.6,
           has_gap=1 if gps else 0, raw_points=False, polyline=gps)
    # 4 multimodal walk / subway / walk
    r4 = path(coords("penn"), coords("grocery"), 30, wobble=-0.002)
    b.trip(v_penn2, v_groc, ts(day, "18:00"), ts(day, "18:35"), r4 if gps else None, mode_auto="subway", mode_conf=0.7,
           raw_points=gps, polyline=gps,
           segments=[(0.0, 0.2, "walk", None), (0.2, 0.8, "subway", None), (0.8, 1.0, "walk", None)] if gps else None)
    # 5 car, endpoints only (no polyline, no raw points), still has a distance
    t5 = b.trip(v_groc, v_home2, ts(day, "19:00"), ts(day, "19:20"), None, mode_auto="car", mode_conf=0.55)
    b.run("UPDATE trips SET distance_m = ? WHERE id = ?", haversine(coords("grocery"), coords("home")), t5)
    # 6 taxi, crosses midnight: belongs to `day` because it departs on `day`
    r6 = path(coords("home"), coords("friend"), 20)
    b.trip(v_home2, v_friend, ts(day, "23:40"), ts(day, "00:05", plus_days=1), r6 if gps else None, mode_auto="car",
           mode_conf=0.6, mode_user="taxi", user_status="edited", raw_points=gps, polyline=gps)

    if full:
        # a soft-deleted auto trip the engine once produced inside the Penn stay: must never be displayed
        b.trip(v_penn1, v_penn1, ts(day, "10:00"), ts(day, "10:08"), None, mode_auto="walk", mode_conf=0.3, deleted=1)
        if b.versions >= 3:
            b.run("""INSERT INTO stamps (id, ts, lat, lon, uncertainty_m, fix_accuracy_m, fix_age_s, visit_id, note, tz, deleted,
                                         created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  uid(), ts(day, "12:25"), 39.954, -75.201, 150.0, 12.0, 40.0, v_lunch, "quick stop", TZ, 0, b.now, b.now)
        if b.versions >= 6:
            b.run("""INSERT INTO expenses (id, ts, amount, currency, category, trip_id, visit_id, note, tz, deleted, created_at, updated_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                  uid(), ts(day, "12:22"), 14.5, "USD", "food", None, v_lunch, None, TZ, 0, b.now, b.now)
        if b.versions >= 2:
            b.run("""INSERT INTO life_phases (id, name, kind, start_date, end_date, notes, created_at, updated_at)
                     VALUES (?,?,?,?,?,?,?,?)""", uid(), "Fall semester", "semester", "2026-08-25", None, None, b.now, b.now)


def main(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    b = Builder(out_dir / "travel-sample.sqlite"); build_day(b, gps=True); b.finish()
    b = Builder(out_dir / "travel-empty.sqlite"); b.finish()
    b = Builder(out_dir / "travel-no-gps.sqlite"); build_day(b, gps=False); b.finish()
    b = Builder(out_dir / "travel-v1.sqlite", versions=1); build_day(b, gps=True, full=False); b.finish()
    b = Builder(out_dir / "travel-future-schema.sqlite"); build_day(b, gps=True, full=False); b.finish(user_version=99)

    p = out_dir / "not-triplibre.sqlite"
    if p.exists():
        p.unlink()
    c = sqlite3.connect(p)
    c.executescript("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT); INSERT INTO notes (body) VALUES ('hello');")
    c.execute("PRAGMA user_version = 3")
    c.commit(); c.close()

    (out_dir / "not-sqlite.sqlite").write_bytes(bytes(random.Random(7).getrandbits(8) for _ in range(4096)))

    for f in sorted(out_dir.glob("*.sqlite")):
        print(f"{f.name:32} {f.stat().st_size:>8} bytes")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "fixtures")
