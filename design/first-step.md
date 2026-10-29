# TripLibreLab — First Step

**Milestone:** V0.1 / First usable iOS release  
**Goal:** Import a TripLibre diary, replay one day, and share a privacy-reviewed summary.

## 1. Definition of done

A user with a supported TripLibre SQLite export can:

1. Open TripLibreLab and choose the SQLite file from Files.
2. See whether the file is supported and, if not, why.
3. Select a day with available travel records.
4. View its trips and stops in chronological order.
5. Play, pause, and scrub through a map-based replay.
6. Preview and export a static day-summary image after reviewing potentially sensitive locations.

All of this works locally, without an account, backend, or TripLibre running at the same time.

## 2. Immediate prerequisite: inspect the real data contract

Before building the importer, examine a **non-sensitive sample** of an actual TripLibre SQLite export. Document:

- Table names, keys, relationships, and schema/version metadata.
- Trip and stay start/end timestamps, time zones, and missing values.
- Latitude/longitude fields and whether recorded routes are stored as points, polylines, or only endpoints.
- How diary days are represented and how incomplete trips are marked.
- Any personally identifying or sensitive fields that must never appear in shared output.

**Deliverable:** `docs/sqlite-data-contract.md`, with a field map from source tables to normalized `DiaryDay`, `Trip`, `Stay`, and `TrackPoint` models. Do not invent column names before inspecting the export.

## 3. V0.1 user flow

```text
Launch
  ↓
Import SQLite from Files
  ↓
Validate and normalize
  ↓
Select day
  ↓
Timeline + map replay
  ↓
Preview share card + privacy controls
  ↓
Share image using iOS share sheet
```

## 4. Minimum screens

| Screen | Minimum behavior |
| --- | --- |
| Welcome / Import | Select file, explain local processing, show import errors. |
| Day Picker | List recorded days with a trip count. |
| Replay | Map, timeline, play/pause, scrubber, trip/stop labels. |
| Share Preview | Show image, hide or generalize sensitive places, export via share sheet. |

## 5. Implementation order

### Step A — Data import

- Create a minimal SwiftUI iOS project.
- Add Files-based SQLite import and safe temporary/local access.
- Open database read-only; validate schema before querying.
- Normalize dates and locations into internal models.
- Handle empty, unsupported, and partially recorded diaries gracefully.

### Step B — Replay

- Display a chronological diary timeline.
- Draw the available recorded route or, when only endpoints exist, clearly label the connection as schematic rather than a measured path.
- Animate progress along recorded points or segments.
- Implement play, pause, restart, and scrub.

### Step C — Share

- Render a day-summary image from the selected diary.
- Add controls to omit exact timestamps and hide/generalize start/end locations.
- Show the exact output before sharing.
- Use the native iOS share sheet; never upload automatically.

### Step D — QA and release

- Test on Simulator and a physical device where available.
- Test a valid sample, empty diary, missing GPS, malformed SQLite, and unsupported schema.
- Confirm no sensitive location data appears in screenshots or default exports.
- Prepare accurate App Store metadata, privacy disclosures, screenshots, and a functional demo path for review.
- Submit only once the app is independently functional and complies with App Review requirements.
- Record submission, In Review, and final decision timestamps for the review-time experiment.

## 6. Explicitly out of scope for V0.1

- Agent-based modeling or synthetic diary generation.
- Counterfactual travel behavior prediction.
- Route optimization and personalized recommendations.
- Accounts, cloud sync, social feed, or server processing.
- General-purpose SQLite editing.
- Complex video export (candidate for V0.2).

## 7. Acceptance tests

- [ ] A supported SQLite file imports successfully without modifying the original.
- [ ] An unsupported or corrupt file produces an understandable error.
- [ ] Day selection and trip chronology match the imported records.
- [ ] Replay never presents interpolated paths as measured GPS tracks.
- [ ] Missing location data does not crash the app.
- [ ] The user can review and redact location detail before sharing.
- [ ] The exported image contains only the intended, previewed content.
- [ ] No login or network connection is required for the core flow.
- [ ] App Store listing accurately describes implemented features.

## 8. First engineering task

**Obtain and inspect one sanitized TripLibre SQLite export.** Establish the data contract, then implement the importer against that verified schema. This is the only critical dependency before replay UI development.
