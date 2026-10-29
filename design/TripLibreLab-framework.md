# TripLibreLab — Product Framework

**Organization:** HHTdiary  
**Product:** TripLibreLab  
**Status:** Concept / early planning  
**Tagline:** Replay. Simulate. Explore.

## 1. Vision

TripLibreLab is a companion app to TripLibre that turns recorded travel diaries into interactive experiences and, eventually, a personal mobility experimentation and advisory environment.

TripLibre captures what happened. TripLibreLab helps users replay it, explore what could have happened, and compare alternatives—without prescribing a single “optimal” lifestyle.

## 2. Product principles

- **User agency:** Present choices and trade-offs; do not dictate behavior.
- **Local-first:** Process imported travel diaries on-device where practical.
- **Privacy by default:** No automatic uploading or public sharing of raw trajectories; provide controls to hide sensitive places and times before sharing.
- **Transparent modeling:** Clearly distinguish observed records, replayed records, synthetic scenarios, and model-based estimates.
- **Small, complete releases:** Each version should deliver a useful standalone experience.
- **Research-compatible, user-friendly:** Maintain a path toward reproducible mobility analysis without requiring technical knowledge from users.

## 3. Ecosystem and scope

| Product | Primary responsibility |
| --- | --- |
| **TripLibre** | Record, organize, and export travel diary data. |
| **TripLibreLab** | Import, visualize, replay, share, simulate, and compare diary-based mobility scenarios. |
| **HHTdiary** | Umbrella organization and broader research/software ecosystem. |

TripLibreLab should not duplicate TripLibre's data collection interface or become a turn-by-turn navigation app.

## 4. Product roadmap

### Phase 1 — Replay & Share

- Import a TripLibre SQLite export through the iOS Files picker.
- Validate supported database/schema versions and show readable errors.
- Select a recorded day and display its trips, stops, and timeline.
- Replay the day on a map using recorded geometry when available.
- Pause, resume, and scrub through the timeline.
- Generate a shareable visual summary (start with a static card; video export can follow).
- Preview and redact sensitive locations before exporting or sharing.

**Outcome:** A useful, standalone travel diary storytelling app.

### Phase 2 — Reconstruct & Simulate

- Create alternative versions of a recorded day.
- Adjust departure times, stop durations, activity order, and selected travel assumptions.
- Introduce explicitly parameterized agent-based or stochastic simulation.
- Label all generated journeys as synthetic, not observed behavior.
- Compare simulated scenarios against the original diary.

**Outcome:** An interactive mobility sandbox.

### Phase 3 — Advisory & Comparison

- Allow users to choose objectives: time, distance, cost, emissions, convenience, or custom priorities.
- Respect activity schedules and other user-specified constraints.
- Include **Do Nothing / Keep Original Diary** as a baseline.
- Explain assumptions, uncertainty, and trade-offs behind recommendations.
- Avoid claims of real-world savings without validated inputs and models.

**Outcome:** A user-directed mobility decision-support app, not an automatic life optimizer.

## 5. Initial technical direction

- **Platform:** iOS, using SwiftUI.
- **Mapping:** MapKit, subject to actual location/geometry availability in imported data.
- **Storage/import:** Read user-selected TripLibre SQLite exports locally, using a read-only import path where possible.
- **Architecture:** Separate data import/normalization, diary domain models, replay engine, and presentation/export layers.
- **Data contract:** Confirm TripLibre's actual SQLite schema, versioning, timestamps, coordinate conventions, trip/stay relationships, and export behavior before implementation.
- **Permissions:** Avoid unnecessary permissions; importing a file should not require background location tracking.

## 6. Success criteria

For the initial release, a user can import a supported diary, select a day, understand its timeline, replay its recorded movements, and share a privacy-reviewed summary without an account or backend.

A secondary experiment is to document App Store review timing for this independently useful app. Review duration alone cannot establish why Apple's queue differs from TripLibre's.

## 7. Open decisions

- Which TripLibre SQLite export schema and versions will be supported?
- Are trip polylines stored, or only endpoints / sampled GPS points?
- What constitutes a complete day when records are missing or incomplete?
- Should the first share format be an image, video, or both?
- What location-redaction defaults are appropriate?
- Should the public-facing subtitle emphasize storytelling or mobility research?

---

**Next document:** `first-step.md` — executable first-release scope and acceptance criteria.
