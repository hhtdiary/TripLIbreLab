#!/usr/bin/env python3
"""
Inspect a TripLibre `travel.sqlite` and check it against TripLibreLab's data contract
(docs/sqlite-data-contract.md). Read-only: the file is opened with mode=ro and never modified.

Usage:  python3 tools/inspect_export.py path/to/travel.sqlite [--days] [--day YYYY-MM-DD]

Prints only structure and counts by default, no coordinates, place names or notes, so the output of a
real export can be shared. `--days` lists diary days with trip counts (dates only). `--day` prints the
normalized timeline of one day with place names and coordinates: for your own eyes, do not paste it.

Exit status 0 = supported, 2 = unsupported or unreadable.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# ---- the contract ----------------------------------------------------------------------------------
# Schema versions TripLibreLab has been checked against (PRAGMA user_version). Migrations are append-only,
# so a newer version is reported as "newer than tested" and import continues if the required columns exist.
TESTED_VERSIONS = range(1, 7)

REQUIRED = {
    "trips": ["id", "origin_visit_id", "destination_visit_id", "origin_place_id", "destination_place_id",
              "departure_ts", "arrival_ts", "distance_m", "mode_auto", "mode_user", "purpose", "route_polyline",
              "has_gap", "user_status", "deleted", "tz"],
    "visits": ["id", "place_id", "arrival_ts", "departure_ts", "lat", "lon", "purpose", "user_status", "deleted", "tz"],
    "places": ["id", "name", "lat", "lon", "category", "merged_into"],
}
OPTIONAL = {
    "trip_segments": ["id", "trip_id", "seq", "start_ts", "end_ts", "mode_auto", "mode_user", "distance_m", "route_polyline"],
    "raw_location_points": ["ts", "lat", "lon", "h_accuracy", "speed", "course", "source", "tz"],
}
# Columns added by later migrations; absent in older exports and read only when present.
VERSIONED = {("places", "deleted"): 2, ("places", "category_custom"): 5}
NEVER_EXPORT = ["places.address", "places.notes", "visits.notes", "trips.notes", "stamps.note", "expenses.note",
                "audit_log.old_value", "audit_log.new_value", "flights.booking_reference", "flights.seat"]


def fail(msg: str) -> int:
    print(f"UNSUPPORTED: {msg}")
    return 2


def day_key(ts: float, tz: str | None) -> str:
    try:
        zone = ZoneInfo(tz) if tz else timezone.utc
    except Exception:
        zone = timezone.utc
    return datetime.fromtimestamp(ts, zone).strftime("%Y-%m-%d")


def hm(ts: float | None, tz: str | None) -> str:
    if ts is None:
        return "  …  "
    try:
        zone = ZoneInfo(tz) if tz else timezone.utc
    except Exception:
        zone = timezone.utc
    return datetime.fromtimestamp(ts, zone).strftime("%H:%M")


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 1
    path = Path(argv[0])
    want_days = "--days" in argv
    want_day = argv[argv.index("--day") + 1] if "--day" in argv else None

    # 1. Is it a SQLite database at all? (header check before any SQL)
    try:
        header = path.open("rb").read(100)
    except OSError as e:
        return fail(f"cannot read file: {e}")
    if not header.startswith(b"SQLite format 3\x00"):
        return fail("not a SQLite database (bad header)")
    journal = {1: "rollback", 2: "WAL"}.get(header[18], f"unknown({header[18]})")
    print(f"file:            {path.name}  ({path.stat().st_size} bytes, header journal mode = {journal})")

    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        ok = con.execute("PRAGMA quick_check").fetchone()[0]
    except sqlite3.DatabaseError as e:
        return fail(f"SQLite could not open it: {e}")
    if ok != "ok":
        return fail(f"integrity check failed: {ok}")

    # 2. Schema version and tables
    version = con.execute("PRAGMA user_version").fetchone()[0]
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    views = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'view'")}
    print(f"user_version:    {version}" + ("" if version in TESTED_VERSIONS else "   <- newer than tested" if version > max(TESTED_VERSIONS) else "   <- not a TripLibre version"))
    print(f"tables:          {len(tables)}  views: {sorted(views)}")
    if version == 0 and not tables & set(REQUIRED):
        return fail("empty database or not a TripLibre export (user_version 0, no trips/visits/places tables)")

    def columns(t: str) -> list[str]:
        return [r[1] for r in con.execute(f"PRAGMA table_info({t})")]

    missing = []
    for t, cols in REQUIRED.items():
        if t not in tables:
            missing.append(f"table {t}")
            continue
        have = set(columns(t))
        missing += [f"{t}.{c}" for c in cols if c not in have]
    if missing:
        return fail("required tables/columns missing: " + ", ".join(missing))
    print("required:        trips, visits, places with all contract columns  OK")
    for t, cols in OPTIONAL.items():
        if t in tables:
            have = set(columns(t))
            lost = [c for c in cols if c not in have]
            print(f"optional:        {t:22} present" + (f", missing {lost}" if lost else ""))
        else:
            print(f"optional:        {t:22} ABSENT (import continues without it)")
    for (t, c), v in VERSIONED.items():
        present = c in columns(t)
        print(f"versioned:       {t}.{c:17} {'present' if present else 'absent'} (added in schema v{v})")
    if version > max(TESTED_VERSIONS):
        print("note:            schema is newer than TripLibreLab was tested with; required columns are all present, importing anyway")

    # 3. Counts (no content)
    def count(sql: str) -> int:
        return con.execute(sql).fetchone()[0]

    has_place_deleted = "deleted" in columns("places")
    print("counts:")
    print(f"  trips            {count('SELECT COUNT(*) FROM trips WHERE deleted = 0'):>7} active, {count('SELECT COUNT(*) FROM trips WHERE deleted = 1'):>5} soft-deleted")
    print(f"  visits           {count('SELECT COUNT(*) FROM visits WHERE deleted = 0'):>7} active, {count('SELECT COUNT(*) FROM visits WHERE deleted = 1'):>5} soft-deleted, {count('SELECT COUNT(*) FROM visits WHERE deleted = 0 AND departure_ts IS NULL'):>3} ongoing")
    pl_del = count("SELECT COUNT(*) FROM places WHERE deleted = 1") if has_place_deleted else 0
    print(f"  places           {count('SELECT COUNT(*) FROM places WHERE merged_into IS NULL') - pl_del:>7} active, {count('SELECT COUNT(*) FROM places WHERE merged_into IS NOT NULL'):>5} merged tombstones, {pl_del:>3} deleted")
    if "trip_segments" in tables:
        print(f"  trip_segments    {count('SELECT COUNT(*) FROM trip_segments'):>7}")
    if "raw_location_points" in tables:
        print(f"  raw points       {count('SELECT COUNT(*) FROM raw_location_points'):>7}")
    print(f"  trips w/ polyline{count('SELECT COUNT(*) FROM trips WHERE deleted = 0 AND route_polyline IS NOT NULL AND route_polyline != \"\"'):>7}   with has_gap {count('SELECT COUNT(*) FROM trips WHERE deleted = 0 AND has_gap = 1'):>5}")
    print(f"  trips w/o visits {count('SELECT COUNT(*) FROM trips WHERE deleted = 0 AND (origin_visit_id IS NULL OR destination_visit_id IS NULL)'):>7}   (manual/imported history: fall back to *_place_id)")
    tzs = [r[0] for r in con.execute("SELECT DISTINCT tz FROM trips WHERE deleted = 0")]
    print(f"  time zones       {len(tzs)} distinct in trips" + ("  (includes NULL)" if None in tzs else ""))
    sources = [f"{r[0]}={r[1]}" for r in con.execute("SELECT source, COUNT(*) FROM trips WHERE deleted = 0 GROUP BY source")]
    status = [f"{r[0]}={r[1]}" for r in con.execute("SELECT user_status, COUNT(*) FROM trips WHERE deleted = 0 GROUP BY user_status")]
    print(f"  trip source      {', '.join(sources) or '-'}")
    print(f"  trip user_status {', '.join(status) or '-'}")
    print(f"sensitive fields never exported by Lab: {', '.join(NEVER_EXPORT)}")

    # 4. Diary days = local date of departure, in each trip's own tz
    trips = con.execute("""SELECT id, departure_ts, arrival_ts, tz, origin_visit_id, destination_visit_id,
                                  origin_place_id, destination_place_id, COALESCE(mode_user, mode_auto, 'unknown'),
                                  route_polyline IS NOT NULL AND route_polyline != '', has_gap, distance_m
                           FROM trips WHERE deleted = 0 ORDER BY departure_ts""").fetchall()
    days: dict[str, list] = {}
    for t in trips:
        days.setdefault(day_key(t[1], t[3]), []).append(t)
    print(f"diary days:      {len(days)}" + (f"  ({min(days)} … {max(days)})" if days else "  (no trips: empty diary)"))
    if want_days:
        for d, ts_ in sorted(days.items()):
            print(f"  {d}  {len(ts_):>3} trips")

    if want_day:
        if want_day not in days:
            print(f"no trips on {want_day}")
        else:
            print(f"\n--- {want_day} (contains personal detail) ---")
            place_name = {r[0]: (r[1], r[2]) for r in con.execute("SELECT id, name, category FROM places")}
            visit = {r[0]: r for r in con.execute("SELECT id, place_id, arrival_ts, departure_ts, lat, lon, tz FROM visits WHERE deleted = 0")}

            def end_label(vid, pid):
                v = visit.get(vid)
                pid = (v[1] if v else None) or pid
                name, cat = place_name.get(pid, (None, None))
                if name is None and v is not None:
                    name = f"Place {v[4]:.4f}, {v[5]:.4f}"
                return f"{name or '(no location)'}" + (f" [{cat}]" if cat else "")

            for t in days[want_day]:
                geom = "raw+polyline" if t[9] else "endpoints only"
                if t[9] and "raw_location_points" in tables:
                    n = count(f"SELECT COUNT(*) FROM raw_location_points WHERE ts BETWEEN {t[1]} AND {t[2]}")
                    geom = f"polyline, {n} raw pts" + (", GAP" if t[10] else "")
                print(f"  {hm(t[1], t[3])}-{hm(t[2], t[3])}  {t[8]:<14} {end_label(t[4], t[6])}  ->  {end_label(t[5], t[7])}   {geom}, {t[11] or 0:.0f} m")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
