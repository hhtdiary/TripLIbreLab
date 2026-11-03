#!/usr/bin/env python3
"""
Compare two sets of fixtures by content: python3 tools/check_fixtures.py <committed_dir> <freshly_built_dir>

A SQLite file records the version of the library that wrote it (header offset 96), and page layout can differ
between SQLite builds, so byte-for-byte comparison is wrong across machines. Two database fixtures count as the same
when they have the same user_version, the same journal-mode header bytes (18 and 19), the same schema SQL for every
table, index and view, and the same rows in every table. A non-database fixture (random bytes) must match exactly.

Exit status 0 when every committed fixture matches the fresh build, 1 otherwise, with one line per difference.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SQLITE_HEADER = b"SQLite format 3\x00"


def db_content(path: Path) -> dict:
    header = path.read_bytes()[:100]
    con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    try:
        schema = con.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        rows = {}
        for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{name}")')]
            order = ", ".join(f'"{c}"' for c in cols)
            rows[name] = con.execute(f'SELECT * FROM "{name}" ORDER BY {order}').fetchall()
        return {
            "user_version": con.execute("PRAGMA user_version").fetchone()[0],
            "journal_header": (header[18], header[19]),
            "schema": schema,
            "rows": rows,
        }
    finally:
        con.close()


def same(a: Path, b: Path) -> list[str]:
    """Differences between fixture files a (committed) and b (fresh), as human-readable lines."""
    ba, bb = a.read_bytes(), b.read_bytes()
    is_db_a, is_db_b = ba.startswith(SQLITE_HEADER), bb.startswith(SQLITE_HEADER)
    if not is_db_a or not is_db_b:
        return [] if ba == bb else ["bytes differ"]
    ca, cb = db_content(a), db_content(b)
    out = []
    for key in ("user_version", "journal_header", "schema"):
        if ca[key] != cb[key]:
            out.append(f"{key} differs")
    for table in sorted(set(ca["rows"]) | set(cb["rows"])):
        ra, rb = ca["rows"].get(table), cb["rows"].get(table)
        if ra != rb:
            out.append(f"table {table}: {len(ra or [])} committed rows vs {len(rb or [])} fresh rows, or different values")
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    committed, fresh = Path(argv[0]), Path(argv[1])
    names_c = {p.name for p in committed.glob("*.sqlite")}
    names_f = {p.name for p in fresh.glob("*.sqlite")}
    bad = 0
    for name in sorted(names_c | names_f):
        if name not in names_f:
            print(f"::error::{committed / name} is not produced by make_fixtures.py any more; delete it or update the generator")
            bad += 1
            continue
        if name not in names_c:
            print(f"::error::{name} is produced by make_fixtures.py but missing from {committed}/. Run 'make fixtures' and commit it.")
            bad += 1
            continue
        diffs = same(committed / name, fresh / name)
        if diffs:
            print(f"::error::{committed / name} is out of date ({'; '.join(diffs)}). Run 'make fixtures' and commit it.")
            bad += 1
        else:
            print(f"ok  {name}")
    if not bad:
        print(f"fixtures are up to date ({len(names_c)} files, compared by content; SQLite {sqlite3.sqlite_version})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
