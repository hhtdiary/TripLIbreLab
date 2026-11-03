"""
Contract tests for the Python tooling. Run: python3 -m unittest discover -s tools/tests -v   (or `make test`).

They check that the committed fixtures have the same content as what make_fixtures.py produces, that inspect_export.py
gives the verdict the data contract promises for every fixture, and that the sample fixture has the shape
docs/sqlite-data-contract.md describes (the same facts the Swift importer's tests will assert later).
"""

from __future__ import annotations

import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check_fixtures  # noqa: E402
import inspect_export  # noqa: E402
import make_fixtures  # noqa: E402

FIXTURES = ROOT / "fixtures"
EXPECTED_VERDICT = {  # exit status of inspect_export: 0 = supported, 2 = unsupported
    "travel-sample.sqlite": 0,
    "travel-empty.sqlite": 0,
    "travel-no-gps.sqlite": 0,
    "travel-v1.sqlite": 0,
    "travel-future-schema.sqlite": 0,
    "not-triplibre.sqlite": 2,
    "not-sqlite.sqlite": 2,
}


def inspect(name: str, *args: str) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = inspect_export.main([str(FIXTURES / name), *args])
    return code, out.getvalue()


class FixturesAreReproducible(unittest.TestCase):
    def test_committed_fixtures_match_generator(self):
        # Compared by content, not bytes: SQLite writes its own version number into the file header, so the same
        # generator gives different bytes on a machine with a different SQLite build (that is what broke CI first).
        with tempfile.TemporaryDirectory() as d:
            with redirect_stdout(io.StringIO()):
                make_fixtures.main(Path(d))
            built = {p.name for p in Path(d).glob("*.sqlite")}
            self.assertEqual(built, set(EXPECTED_VERDICT), "fixture list drifted from the test table")
            self.assertEqual(built, {p.name for p in FIXTURES.glob("*.sqlite")}, "fixtures/ has a different file list")
            for name in sorted(built):
                with self.subTest(fixture=name):
                    diffs = check_fixtures.same(FIXTURES / name, Path(d) / name)
                    self.assertEqual(diffs, [], f"{name} is out of date: run python3 tools/make_fixtures.py and commit")

    def test_content_comparison_ignores_header_version_but_not_data(self):
        sample = FIXTURES / "travel-sample.sqlite"
        with tempfile.TemporaryDirectory() as d:
            restamped = Path(d) / "restamped.sqlite"
            raw = bytearray(sample.read_bytes())
            raw[96:100] = (3045000).to_bytes(4, "big")  # pretend another SQLite build wrote it
            restamped.write_bytes(raw)
            self.assertEqual(check_fixtures.same(sample, restamped), [])
            edited = Path(d) / "edited.sqlite"
            edited.write_bytes(sample.read_bytes())
            con = sqlite3.connect(edited)
            con.execute("UPDATE trips SET distance_m = distance_m + 1 WHERE rowid = 1")
            con.commit(); con.close()
            self.assertTrue(any(d.startswith("table trips") for d in check_fixtures.same(sample, edited)))

    def test_exports_are_rollback_journal_files(self):
        # VACUUM INTO output opens read-only without -wal/-shm sidecars (contract §1).
        for name in ("travel-sample.sqlite", "travel-v1.sqlite", "travel-empty.sqlite"):
            hdr = (FIXTURES / name).read_bytes()[:100]
            self.assertTrue(hdr.startswith(b"SQLite format 3\x00"), name)
            self.assertEqual((hdr[18], hdr[19]), (1, 1), f"{name} is not in rollback-journal mode")


class InspectorVerdicts(unittest.TestCase):
    def test_every_fixture_gets_the_promised_verdict(self):
        for name, expected in EXPECTED_VERDICT.items():
            with self.subTest(fixture=name):
                code, out = inspect(name)
                self.assertEqual(code, expected, out)

    def test_unsupported_reasons_match_the_contract(self):
        self.assertIn("not a SQLite database", inspect("not-sqlite.sqlite")[1])
        self.assertIn("required tables/columns missing", inspect("not-triplibre.sqlite")[1])

    def test_newer_schema_imports_with_a_notice(self):
        code, out = inspect("travel-future-schema.sqlite")
        self.assertEqual(code, 0)
        self.assertIn("newer than tested", out)

    def test_empty_diary_is_supported_but_has_no_days(self):
        code, out = inspect("travel-empty.sqlite", "--days")
        self.assertEqual(code, 0)
        self.assertIn("diary days:      0", out)

    def test_schema_v1_has_no_versioned_columns(self):
        _, out = inspect("travel-v1.sqlite")
        self.assertIn("places.deleted           absent", out)
        self.assertIn("places.category_custom   absent", out)


class SampleDayMatchesTheContract(unittest.TestCase):
    """The facts about travel-sample.sqlite that the Swift importer tests will assert too."""

    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{FIXTURES / 'travel-sample.sqlite'}?mode=ro&immutable=1", uri=True)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def q(self, sql, *args):
        return self.con.execute(sql, args).fetchall()

    def test_schema_version_and_views(self):
        self.assertEqual(self.q("PRAGMA user_version")[0][0], 6)
        views = {r[0] for r in self.q("SELECT name FROM sqlite_master WHERE type = 'view'")}
        self.assertEqual(views, {"v_trips", "v_visits"})

    def test_required_columns_present(self):
        for table, cols in inspect_export.REQUIRED.items():
            have = {r[1] for r in self.q(f"PRAGMA table_info({table})")}
            self.assertTrue(set(cols) <= have, f"{table} missing {set(cols) - have}")

    def test_one_day_with_six_active_trips_and_one_deleted(self):
        self.assertEqual(self.q("SELECT COUNT(*) FROM trips WHERE deleted = 0")[0][0], 6)
        self.assertEqual(self.q("SELECT COUNT(*) FROM trips WHERE deleted = 1")[0][0], 1)
        rows = self.q("SELECT departure_ts, tz FROM trips WHERE deleted = 0")
        days = {inspect_export.day_key(ts, tz) for ts, tz in rows}
        self.assertEqual(days, {"2026-09-15"})

    def test_midnight_crossing_trip_belongs_to_departure_day(self):
        dep, arr, tz = self.q("SELECT departure_ts, arrival_ts, tz FROM trips WHERE deleted = 0 ORDER BY departure_ts DESC LIMIT 1")[0]
        self.assertEqual(inspect_export.day_key(dep, tz), "2026-09-15")
        self.assertEqual(inspect_export.day_key(arr, tz), "2026-09-16")

    def test_final_mode_and_purpose_resolution(self):
        modes = [r[0] for r in self.q("SELECT COALESCE(mode_user, mode_auto, 'unknown') FROM trips WHERE deleted = 0 ORDER BY departure_ts")]
        self.assertEqual(modes, ["bicycle", "walk", "walk", "subway", "car", "taxi"])
        purposes = [r[0] for r in self.q("SELECT purpose_final FROM v_trips ORDER BY departure_ts")]
        self.assertEqual(purposes, ["work", "meal", "work", "shopping", "home", "social"])

    def test_geometry_levels_are_all_present(self):
        rows = self.q("""SELECT route_polyline IS NOT NULL, has_gap,
                                (SELECT COUNT(*) FROM raw_location_points p WHERE p.ts > t.departure_ts AND p.ts < t.arrival_ts)
                         FROM trips t WHERE deleted = 0 ORDER BY departure_ts""")
        levels = {("measured" if n >= 2 else "shape" if poly else "schematic") + ("+gap" if gap else "") for poly, gap, n in rows}
        self.assertEqual(levels, {"measured", "shape+gap", "schematic"})

    def test_ongoing_stay_and_merged_place(self):
        self.assertEqual(self.q("SELECT COUNT(*) FROM visits WHERE deleted = 0 AND departure_ts IS NULL")[0][0], 1)
        self.assertEqual(self.q("SELECT COUNT(*) FROM places WHERE merged_into IS NOT NULL")[0][0], 1)

    def test_multimodal_trip_has_contiguous_segments(self):
        seg = self.q("""SELECT s.trip_id, s.seq, s.start_ts, s.end_ts, COALESCE(s.mode_user, s.mode_auto, 'unknown')
                        FROM trip_segments s JOIN trips t ON t.id = s.trip_id
                        WHERE t.deleted = 0 GROUP BY s.trip_id, s.seq HAVING COUNT(*) = 1 ORDER BY s.trip_id, s.seq""")
        by_trip: dict[str, list] = {}
        for trip_id, *rest in seg:
            by_trip.setdefault(trip_id, []).append(rest)
        multimodal = [segs for segs in by_trip.values() if len(segs) > 1]
        self.assertEqual(len(multimodal), 1)
        segs = multimodal[0]
        self.assertEqual([s[3] for s in segs], ["walk", "subway", "walk"])
        for a, b in zip(segs, segs[1:], strict=False):
            self.assertAlmostEqual(a[2], b[1], msg="segments must be contiguous")

    def test_polyline_round_trip(self):
        poly = self.q("SELECT route_polyline FROM trips WHERE route_polyline IS NOT NULL ORDER BY departure_ts LIMIT 1")[0][0]
        pts = make_fixtures.path(make_fixtures.coords("home"), make_fixtures.coords("penn"), 40)
        self.assertEqual(make_fixtures.encode_polyline(pts), poly)
        self.assertEqual(len(decode_polyline(poly)), 41)
        self.assertAlmostEqual(decode_polyline(poly)[0][0], 39.9526, places=5)


def decode_polyline(s: str):
    """Reference decoder (same algorithm as TripLibre's Polyline.decode) used only to check the encoder."""
    out, lat, lon, i, b = [], 0, 0, 0, s.encode()

    def nxt():
        nonlocal i
        res = shift = 0
        while i < len(b):
            v = b[i] - 63
            i += 1
            res |= (v & 0x1F) << shift
            shift += 5
            if v < 0x20:
                return ~(res >> 1) if res & 1 else res >> 1
        return None

    while i < len(b):
        dl, dn = nxt(), nxt()
        if dl is None or dn is None:
            break
        lat += dl
        lon += dn
        out.append((lat / 1e5, lon / 1e5))
    return out


if __name__ == "__main__":
    unittest.main()
