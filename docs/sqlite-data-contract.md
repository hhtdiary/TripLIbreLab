# TripLibreLab — SQLite data contract

**Source of truth:** TripLibre 2.1.0, schema **v6**, read from the TripLibre repository
(`Packages/HHTCore/Sources/HHTCore/Database/Schema.swift`, `Export/Exporter.swift`, `Database/TravelStore.swift`,
`docs/data-model.md`, `docs/docs/data-dictionary.html`).
**Verification status:** every table, column, and convention below was taken from TripLibre's migration SQL and
exporter code, and checked against a synthetic `travel.sqlite` built from that same SQL
(`fixtures/`, see §11). It has **not yet been run against a real export from a phone**. Before the importer
ships, run `tools/inspect_export.py` on one real `travel.sqlite` (it prints structure and counts only) and
attach the output to this document.

Nothing in this document was invented: column names are copied from the migrations; behaviour claims cite the
TripLibre code they come from.

---

## 1. The file TripLibreLab imports

| Fact | Value | Source |
| --- | --- | --- |
| File | `travel.sqlite` inside `hht-export-YYYYMMDD-HHMMSS/` (Files › On My iPhone › TripLibre › Exports) | `Exporter.exportBundle` |
| How it is written | `VACUUM INTO` of the live database (`TravelStore.backup(to:)`) | `TravelStore.swift` |
| Consequence 1 | A single self-contained file in **rollback-journal mode** (header bytes 18–19 = 1), even though the live DB runs in WAL. No `-wal` / `-shm` sidecars are needed to open it. Verified on the fixture. | SQLite `VACUUM INTO` |
| Consequence 2 | It is **always the complete database**: the export's "last 30 days" range and "include raw GPS" switch do not apply to `travel.sqlite`. It includes **soft-deleted rows** and **all raw GPS points**. | data dictionary, "The export folder" |
| Schema version | `PRAGMA user_version` (1…6 today) | `Schema.migrate` |
| Other export files | `trips.csv`, `visits.csv`, `data.json`, `*.geojson`, … | **Not read by TripLibreLab** |

Because the file is a complete copy of someone's location history, TripLibreLab must treat it as sensitive from the
moment it is picked (§9).

## 2. Opening rules (Step A, "validate schema before querying")

Perform these in order; stop at the first failure with the listed user-facing reason.

| # | Check | Fail → message |
| --- | --- | --- |
| 1 | First 16 bytes are `SQLite format 3\0` | "This file is not a SQLite database." |
| 2 | Open with `SQLITE_OPEN_READONLY` and URI `?mode=ro&immutable=1` (the file is a copy in our sandbox; `immutable` avoids any lock or journal writes). Run `PRAGMA quick_check` = `ok`. | "The file could not be opened as a TripLibre database (damaged file)." |
| 3 | Tables `trips`, `visits`, `places` exist with every **required** column of §5 | "This SQLite file is not a TripLibre export (expected tables are missing)." |
| 4 | `PRAGMA user_version` ∈ 1…6 | version 0 or >6: see policy below |
| 5 | `SELECT COUNT(*) FROM trips WHERE deleted = 0` > 0 | "This diary contains no recorded trips." (empty-diary screen, not an error) |

**Version policy (recommended, needs sign-off, §12 Q1):** TripLibre migrations are append-only and codes are never
renamed (data dictionary, "Schema versioning"). So a **newer** `user_version` than TripLibreLab knows should import
with a non-blocking notice ("made by a newer TripLibre; checked up to schema v6"), as long as check 3 passes.
A **v0** file (no migrations ever applied) or a file failing check 3 is unsupported. Older versions (v1–v5) import;
columns added later (`places.deleted` v2, `places.category_custom` v5, tables `stamps` v3 and `expenses` v6) are
read only when present.

Never write to the file, never run `VACUUM`, `ANALYZE`, or migrations, and never copy it anywhere other than the
app's own container. Delete the private copy when the user removes the diary.

## 3. Conventions (apply to every table)

| Topic | Rule | Source |
| --- | --- | --- |
| `*_ts`, `ts` | **UTC Unix seconds, REAL** | `data-model.md` |
| `created_at`, `updated_at`, `inserted_at` | UTC Unix seconds; bookkeeping only | data dictionary |
| `tz` | IANA zone of the phone **when that record was made** (e.g. `America/New_York`); may be NULL on old/imported rows. Local dates and clock times are computed with **the record's own `tz`**, so travel across zones stays right. | `Analytics.dayKey`, `localCalendar` |
| Coordinates | WGS84 decimal degrees, `lat` / `lon` columns | `data-model.md` |
| Distances | metres, great-circle along the recorded path; straight line across a data gap | `data-model.md` |
| IDs | lowercase UUID strings (`TEXT`) for places/visits/trips/segments; integer autoincrement for raw points | `data-model.md` |
| `route_polyline` | **Google encoded polyline, precision 1e-5, (lat, lon)**, Douglas–Peucker-simplified at 8 m. **Carries no timestamps.** | `Polyline.encode`, `InferenceConfig` |
| Booleans | `INTEGER` 0 / 1 | schema |
| Soft delete | `deleted = 1` rows are kept; **always filter `deleted = 0`** | schema, data dictionary |
| Missing values | SQL `NULL`; no sentinels like `-1` | data dictionary |
| Final mode | `COALESCE(mode_user, mode_auto, 'unknown')` | `Trip.mode`, `v_trips.mode_final` |

## 4. Tables in the file and what TripLibreLab does with them

| Table (schema v) | Rows | TripLibreLab use |
| --- | --- | --- |
| `trips` (v1) | one per trip, visit → visit | **Required.** Source of `Trip`. |
| `visits` (v1) | one per stay | **Required.** Source of `Stay`. |
| `places` (v1; `deleted` v2; `category_custom` v5) | personal place database | **Required.** Names/categories for stays and trip ends. |
| `trip_segments` (v1) | single-mode parts of a trip, `seq` from 0 | Optional. Mode labels for multimodal trips; per-segment polylines. |
| `raw_location_points` (v1) | every GPS fix, append-only | Optional. Source of timestamped `TrackPoint`s for replay. |
| `motion_activities` (v1) | CoreMotion episodes | Not used in V0.1. |
| `flights`, `journeys`, `journey_members`, `life_phases`, `airports` (v1) | long-distance / reference data | Not used in V0.1 (airplane trips still appear as trips). |
| `stamps` (v3) | one-tap self-reports | Not used in V0.1 (candidate marker later). |
| `expenses` (v6) | costs | Not used. |
| `audit_log` (v1) | every user correction, old → new values as text | **Never read.** Can contain place names and free text. |
| `app_meta` (v1) | key/value | Not used. |
| `sqlite_sequence` | SQLite internal | — |
| Views `v_trips`, `v_visits` (v1, `v_trips` redefined v4) | non-deleted rows + `mode_final`, `purpose_final`, `duration_s`, `origin_place_final`, `destination_place_final` | Convenient, but §5 queries the base tables so a file whose views were dropped or changed still imports. `v_trips.purpose_final` logic is reproduced in §5.2. |

## 5. Field map: source columns → normalized models

The normalized models are `DiaryDay`, `Trip`, `Stay`, `TrackPoint`, plus a small `Place`. Types are Swift.

### 5.1 `Place` ← `places`

Required columns: `id, name, lat, lon, category, merged_into`. Optional: `deleted` (v2+), `category_custom` (v5+),
`code`, `city`, `country`.

| Model field | Source | Notes |
| --- | --- | --- |
| `id: String` | `places.id` | |
| `name: String?` | `places.name` | NULL = unnamed place. TripLibre then shows `"Place 39.9540, -75.2009"`; **TripLibreLab must not** put raw coordinates in a share card by default (§9). |
| `category: String?` | `places.category` | one of the codes in §8; `category_custom` is only a label for `other` |
| `coordinate` | `places.lat`, `places.lon` | |
| `isHome: Bool` | `places.category = 'home'` | drives default redaction |
| `isWorkOrSchool: Bool` | `places.category = 'work_school'` | drives default redaction |
| `mergedInto: String?` | `places.merged_into` | tombstone; TripLibre repoints all visits to the target, so resolve `place_id` through `merged_into` once as a safety net |
| (excluded) | `places.deleted = 1` | if the column exists; a deleted place's visits are soft-deleted too |
| (never loaded) | `address, notes, favorite, radius_m, source, created_at, updated_at` | address and notes are personal |

```sql
SELECT id, name, lat, lon, category, merged_into
FROM places
-- add "WHERE deleted = 0" only when PRAGMA table_info(places) lists a 'deleted' column (schema >= 2)
```

### 5.2 `Trip` ← `trips` (+ `trip_segments`)

Required columns: `id, origin_visit_id, destination_visit_id, origin_place_id, destination_place_id, departure_ts,
arrival_ts, distance_m, mode_auto, mode_user, purpose, route_polyline, has_gap, user_status, deleted, tz`.

| Model field | Source | Notes |
| --- | --- | --- |
| `id: String` | `trips.id` | |
| `departure: Date` | `trips.departure_ts` | NOT NULL in schema |
| `arrival: Date` | `trips.arrival_ts` | NOT NULL; a trip's `arrival` may fall on the next local day |
| `timeZone: TimeZone?` | `trips.tz` | NULL → fall back to the origin stay's `tz`, then the device zone, and flag the day as "time zone unknown" |
| `originStayID`, `destinationStayID: String?` | `trips.origin_visit_id`, `destination_visit_id` | NULL for manual or imported history |
| `originPlaceID`, `destinationPlaceID: String?` | `COALESCE(origin_visit.place_id, trips.origin_place_id)` and likewise for destination | exactly `v_trips.origin_place_final` |
| `originCoordinate`, `destinationCoordinate: Coordinate?` | origin visit `lat, lon` → else origin place `lat, lon` → else first/last polyline vertex → else **nil** | same fallback order as `Exporter.tripRows`; nil must not crash (acceptance test) |
| `mode: String` | `COALESCE(mode_user, mode_auto, 'unknown')` | codes in §8 |
| `modeIsUserCorrected: Bool` | `mode_user IS NOT NULL` | |
| `segmentModes: [String]` | `trip_segments` ordered by `seq`, each `COALESCE(mode_user, mode_auto, 'unknown')`, consecutive repeats collapsed | TripLibre shows these only when there is more than one distinct mode (`Trip.displayModes`) |
| `purpose: String?` | `trips.purpose` → else destination visit `purpose` → else default for destination place category (table in §8) | this is `v_trips.purpose_final` |
| `distanceMeters: Double?` | `trips.distance_m` | may be NULL |
| `routeShape: [Coordinate]` | decode `trips.route_polyline` | **shape only, no timestamps**; empty when NULL |
| `hasRecordingGap: Bool` | `trips.has_gap` | 1 = GPS silent > 15 min during the trip; the polyline then contains a straight connector across the gap |
| `userStatus: String` | `trips.user_status` | `auto / confirmed / edited / manual` |
| (excluded) | `trips.deleted = 1` | |
| (never loaded) | `notes, auto_confidence, mode_confidence, source, created_at, updated_at` | notes are free text |

```sql
SELECT t.id, t.departure_ts, t.arrival_ts, t.tz,
       t.origin_visit_id, t.destination_visit_id,
       COALESCE(ov.place_id, t.origin_place_id)      AS origin_place_id,
       COALESCE(dv.place_id, t.destination_place_id) AS destination_place_id,
       ov.lat AS origin_lat, ov.lon AS origin_lon, dv.lat AS destination_lat, dv.lon AS destination_lon,
       COALESCE(t.mode_user, t.mode_auto, 'unknown') AS mode, t.mode_user IS NOT NULL AS mode_user_set,
       t.purpose AS purpose_explicit, dv.purpose AS purpose_visit, dp.category AS destination_category,
       t.distance_m, t.route_polyline, t.has_gap, t.user_status
FROM trips t
LEFT JOIN visits ov ON ov.id = t.origin_visit_id
LEFT JOIN visits dv ON dv.id = t.destination_visit_id
LEFT JOIN places dp ON dp.id = COALESCE(dv.place_id, t.destination_place_id)
WHERE t.deleted = 0
ORDER BY t.departure_ts;

SELECT trip_id, seq, start_ts, end_ts, COALESCE(mode_user, mode_auto, 'unknown') AS mode, distance_m, route_polyline
FROM trip_segments ORDER BY trip_id, seq;
```

### 5.3 `Stay` ← `visits`

Required columns: `id, place_id, arrival_ts, departure_ts, lat, lon, purpose, user_status, deleted, tz`.

| Model field | Source | Notes |
| --- | --- | --- |
| `id: String` | `visits.id` | |
| `placeID: String?` | `visits.place_id` | NULL = stay not matched to a place |
| `arrival: Date` | `visits.arrival_ts` | NOT NULL |
| `departure: Date?` | `visits.departure_ts` | **NULL = still there at export time** (common for the last stay). Show as "ongoing", never invent an end. |
| `coordinate: Coordinate` | `visits.lat`, `visits.lon` | observed centroid of the stay (NOT NULL); differs slightly from the place's coordinate |
| `timeZone: TimeZone?` | `visits.tz` | |
| `purpose: String?` | `visits.purpose` → else destination-category default (§8) | |
| `userStatus: String` | `visits.user_status` | |
| (excluded) | `visits.deleted = 1` | "this wasn't a stop" |
| (never loaded) | `notes, point_count, auto_confidence, source, created_at, updated_at` | |

Stays for a diary day are those **overlapping** the local day, which is exactly TripLibre's own window query:

```sql
SELECT id, place_id, arrival_ts, departure_ts, lat, lon, purpose, user_status, tz
FROM visits
WHERE arrival_ts <= :day_end_utc AND (departure_ts IS NULL OR departure_ts >= :day_start_utc) AND deleted = 0
ORDER BY arrival_ts;    -- TravelStore.visits(overlapping:)
```

### 5.4 `TrackPoint` ← `raw_location_points`

Optional table. Columns used: `ts, lat, lon, h_accuracy, speed, course, source`. There is **no foreign key from
raw points to trips**; the only link is time. TripLibre itself has no per-trip point list; routes are stored
pre-simplified as `route_polyline`.

| Model field | Source | Notes |
| --- | --- | --- |
| `timestamp: Date` | `ts` | |
| `coordinate` | `lat`, `lon` | |
| `horizontalAccuracy: Double?` | `h_accuracy` | metres; NULL when iOS reported invalid |
| `speed: Double?` | `speed` | m/s; NULL when invalid |
| `course: Double?` | `course` | degrees; NULL when invalid |
| `source: String` | `source` | `gps, significant_change, region_exit, visit_arrival, visit_departure, stationary_marker, imported_gpx` |
| (never loaded) | `altitude, v_accuracy, speed_accuracy, collector_mode, inserted_at, tz` | |

```sql
SELECT ts, lat, lon, h_accuracy, speed, course, source
FROM raw_location_points
WHERE ts >= :trip_departure_ts AND ts <= :trip_arrival_ts
ORDER BY ts;              -- index idx_raw_ts makes this cheap
```

Points at the exact boundaries are stay fixes; drop points whose `source = 'stationary_marker'` and, if the
polyline exists, points more than ~100 m from it (jitter). Keep that filter display-only, as TripLibre's
`RouteDisplay` does.

### 5.5 `DiaryDay` ← derived

| Model field | Rule | Source |
| --- | --- | --- |
| `date: String` (`YYYY-MM-DD`) | local calendar date of **`trips.departure_ts` in that trip's own `tz`** | `Analytics.dayKey`, `trips.csv.person_day_id` |
| `timeZone` | the `tz` shared by the day's trips; if they differ (travel day) keep per-trip zones and label the day with the first | |
| `trips: [Trip]` | all non-deleted trips whose day key equals `date`, ordered by `departure_ts`; `tripSequence` = 1, 2, … | `Exporter.tripRows` |
| `stays: [Stay]` | §5.3 window query for the local day, plus the origin stay of the first trip and destination stay of the last trip if they fall outside the window | |
| `tripCount: Int` | `trips.count` | shown in the Day Picker |
| `startsBeforeMidnight / endsAfterMidnight` | first stay arrival < day start / last trip or stay end > day end | timeline axis extends accordingly |
| `geometryLevel` | `.measured` if any trip has track points, `.shape` if only polylines, `.schematic` if neither | §6 |

**Which days are listed:** TripLibre's definition of a person-day counts a date with at least one trip *or* visit.
first-step.md asks for "days with available travel records" and a trip count, so V0.1 lists only dates with
≥ 1 non-deleted trip (§12 Q2). A date with no rows is not evidence of no travel (collection may have been off);
the Day Picker should say "no recorded trips" rather than "no travel".

Midnight example from the fixture: a taxi trip 23:40 → 00:15 belongs to the 15th (its departure date); the
following stay, which starts at 00:15 on the 16th with `departure_ts NULL`, is attached to the 15th as its final
destination stay and also appears on the 16th if that day has trips.

## 6. Geometry fidelity: what replay may show as "measured"

| Level | Data available | Replay rule | Label |
| --- | --- | --- | --- |
| **Measured** | ≥ 2 `raw_location_points` inside the trip window | animate point to point using real timestamps; draw the polyline (or the points) as the path | "Recorded GPS" |
| **Recorded shape** | `route_polyline` only (no raw points, or too few) | draw the stored shape; animate along it at **uniform speed** between `departure_ts` and `arrival_ts` | "Recorded route, timing interpolated" |
| **Schematic** | neither; only origin/destination coordinates | draw a **dashed straight line**; animate at uniform speed | "Schematic: no GPS track" |
| **Gap** | `has_gap = 1` | the polyline includes a straight connector across the silence; draw that leg dashed (TripLibre's `RouteDisplay.splitAtGapJumps` heuristic: a leg ≥ 1 km and ≥ 8× the median leg) | "Recording gap" |
| **No location** | trip ends have no coordinates at all | keep on timeline, omit from map | — |

This satisfies the acceptance test "Replay never presents interpolated paths as measured GPS tracks".

## 7. Edge cases the importer must survive (all present in the fixtures)

| Case | Where it comes from | Handling |
| --- | --- | --- |
| Trip crossing local midnight | late departures | belongs to departure date; timeline axis extends past 24:00 |
| Ongoing stay (`departure_ts NULL`) | the user is still at the last place when exporting | duration runs to the export time; show "ongoing" |
| Soft-deleted trips / visits / places | user corrections | filter `deleted = 0` everywhere (`places.deleted` only if the column exists) |
| Merged place tombstone (`merged_into` set) | duplicate places merged | resolve to target |
| Trip with no polyline and no raw points | hand-made or imported trips, GPS off | schematic |
| Trip with polyline but `has_gap = 1` | GPS silent > 15 min | gap connector dashed |
| Trip without visits (`*_visit_id NULL`) | imported CSV history, manual trips | use `*_place_id`; if that is NULL too, no map, timeline only |
| Unnamed place (`name NULL`) | stays the user never labelled | show category label ("Restaurant", "Place") not coordinates |
| `tz NULL` | very old or imported rows | fall back (§5.2); mark the day |
| Trips in several zones on one date | travel days | per-record zones; `departure_ts` ordering still works because it is UTC |
| Multimodal trip with `trip_segments` | walk/subway/walk | label "Walk · Subway · Walk" |
| Schema v1 file | pre-2026 installs | no `places.deleted`, no `stamps`; imports |
| Newer schema | future TripLibre | notice, import if required columns present (§2) |
| Empty database | fresh install exported | "no recorded trips" screen |
| Not SQLite / corrupt / unrelated SQLite | wrong file picked | the three messages in §2 |
| Large files | the file always holds all raw points (hundreds of thousands of rows after months) | never `SELECT * FROM raw_location_points`; always query by trip window |

## 8. Code lists (verbatim from `Enums.swift`; never renamed between versions)

**Modes** `walk run bicycle ebike scooter car car_driver car_passenger taxi bus subway light_rail commuter_rail
intercity_rail coach shuttle ferry airplane other unknown`
Mode groups (`hht.py MODE_GROUP`): active = walk run bicycle ebike scooter · car = car car_driver car_passenger taxi ·
transit = bus subway light_rail commuter_rail ferry shuttle · long_distance = intercity_rail coach airplane · other.

**Purposes** `home work school meal shopping recreation social personal_business medical travel transfer escort other`

**Place categories** `home work_school restaurant cafe grocery shopping recreation entertainment airport rail_station
transit_station hotel friend_family medical other` + (v4) `stadium event_venue museum library convenience_store
gas_station bar gym pharmacy bank civic religious parking`

**Default purpose by destination category** (`v_trips` v4 CASE; used for `purpose_final`):
home→home · work_school→work · restaurant, cafe→meal · grocery, shopping, convenience_store, gas_station→shopping ·
recreation, entertainment, stadium, event_venue, museum, library, gym→recreation · airport, rail_station, hotel→travel ·
transit_station, parking→transfer · friend_family, bar, religious→social · medical, pharmacy→medical ·
bank, civic→personal_business · other and NULL→NULL.

**User status** `auto confirmed edited manual` · **Source** `inferred manual imported_csv imported_gpx`

Unknown codes (from a newer TripLibre) must be displayed as their raw string, not rejected.

## 9. Sensitive fields and sharing defaults

The whole file is sensitive, but these columns are personal text or identifiers that **TripLibreLab never loads
into memory**: `places.address`, `places.notes`, `visits.notes`, `trips.notes`, `stamps.note`, `expenses.note`,
`audit_log.old_value`, `audit_log.new_value`, `flights.booking_reference`, `flights.seat`, `places.city/region/country`
(not needed), `raw_location_points` outside a selected trip window.

What can reach a **share card** (Step C) is only what the preview shows. Recommended defaults (§12 Q3):

| Element | Default | Control |
| --- | --- | --- |
| Stays at `home` or `work_school` places | shown as the category word ("Home", "Work"), **map pin hidden and the first/last 300 m of adjoining routes trimmed** | per-day toggle to reveal |
| Other named places | name shown | toggle to show category only |
| Unnamed places | category only; **never coordinates** | — |
| Exact clock times | shown to the minute | toggle: round to 15 min or hide |
| Map base layer | shown at a zoom that covers the day | toggle: hide map, keep timeline only |
| Polylines / GPS tracks | drawn | toggle: schematic lines |
| Date | shown | toggle: weekday only |

## 10. Schema version history and TripLibre app versions

| `user_version` | Migration | Effect on TripLibreLab |
| --- | --- | --- |
| 1 | initial schema (all tables of §4 except stamps/expenses) | baseline |
| 2 | `places.deleted` | filter deleted places when present |
| 3 | `stamps` table | ignored in V0.1 |
| 4 | `v_trips` view redefined with more categories | §8 default-purpose table |
| 5 | `places.category_custom` | label only |
| 6 | `expenses` table (TripLibre 2.1.0, current) | ignored |

TripLibre's public data dictionary says "describes schema version 5" while the code and its own history line list v6;
the code wins. Re-extract `tools/triplibre_schema.sql` whenever TripLibre appends a migration and add a row here.

## 11. Fixtures and tools in this repository

| Path | What |
| --- | --- |
| `tools/triplibre_schema.sql` | TripLibre's six migrations, copied verbatim (Apache-2.0) |
| `tools/make_fixtures.py` | builds every fixture below from that SQL, finishing with `VACUUM INTO` like TripLibre |
| `fixtures/travel-sample.sqlite` | schema v6, one synthetic Philadelphia day: 6 trips covering measured / shape / schematic / gap / multimodal / midnight-crossing, 7 stays incl. one ongoing, a deleted trip, a merged place, a stamp, an expense |
| `fixtures/travel-no-gps.sqlite` | same day, no raw points, no polylines |
| `fixtures/travel-empty.sqlite` | schema only |
| `fixtures/travel-v1.sqlite` | schema v1 only |
| `fixtures/travel-future-schema.sqlite` | v6 tables, `user_version = 99` |
| `fixtures/not-triplibre.sqlite`, `fixtures/not-sqlite.sqlite` | unrelated SQLite; random bytes |
| `tools/inspect_export.py` | read-only contract check for any `travel.sqlite`; prints structure and counts (safe to share), `--days` for dates, `--day` for one timeline (private) |

These map one-to-one onto the Step D test list: valid sample, empty diary, missing GPS, malformed SQLite,
unsupported schema.

## 12. Decisions still needed

1. **Version policy** for `user_version` newer than 6: import with a notice (recommended) or refuse?
2. **Day Picker membership:** only dates with ≥ 1 trip (recommended for V0.1) or also stay-only dates, as TripLibre's
   person-day definition does?
3. **Redaction defaults** in §9: agree, or start more conservative (hide all place names by default)?
4. **Real-export check:** who runs `tools/inspect_export.py` on a real export and pastes the counts output here?
