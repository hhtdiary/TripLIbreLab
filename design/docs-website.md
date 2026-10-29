# TripLibreLab — Documentation Website Plan

## 1. Purpose

Build the public documentation website for **TripLibreLab**, an HHTdiary project. The website should follow the existing TripLibre website's overall information architecture, visual language, and navigation conventions wherever practical.

**Scope of this document:** website structure and content requirements only. This is not an HTML/CSS/JavaScript implementation plan and does not authorize building the iOS app.

**Reference:** https://triplibre.hhtdiary.org

Before implementation, inspect the current TripLibre website/repository and map its actual navigation, page templates, and components. Do not assume that the proposed sections below already exist in TripLibre.

## 2. Positioning

- **Product:** TripLibreLab
- **Organization:** HHTdiary
- **Tagline:** Replay. Simulate. Explore.
- **Description:** A personal mobility laboratory that turns exported travel diaries into interactive replay experiences, and eventually supports scenario simulation and decision-oriented exploration.
- **Relationship:** TripLibre records and manages travel diaries; TripLibreLab works with exported diary data to visualize and explore them.

## 3. Website Principles

1. **Consistency:** Reuse TripLibre's actual header, footer, typography, spacing, color system, responsive behavior, and documentation patterns after reviewing them.
2. **Clear product boundary:** TripLibreLab is a separate companion app, not a replacement for TripLibre.
3. **Version clarity:** Separate features available in the first release from future concepts.
4. **Research transparency:** Clearly distinguish observed trips, reconstructed/replayed paths, synthetic agent trajectories, and advisory scenarios.
5. **Privacy first:** Explain local data handling and the risks of sharing precise travel histories; do not make unverified security claims.
6. **Simple navigation:** Favor a small number of pages over placeholder-heavy documentation.

## 4. Proposed Information Architecture

```text
TripLibreLab Website
├── Home
│   ├── Hero / product introduction
│   ├── How it works: Import → Replay → Share
│   ├── Feature overview
│   ├── Relationship to TripLibre and HHTdiary
│   └── Download / release status
├── Documentation
│   ├── Overview
│   ├── Getting Started
│   ├── Importing a TripLibre SQLite Export
│   ├── Replaying a Travel Diary
│   ├── Sharing a Replay
│   ├── Data & Privacy
│   └── FAQ / Troubleshooting
├── Roadmap
│   ├── Phase 1: Replay & Share
│   ├── Phase 2: ReShape / Agent Simulation
│   └── Phase 3: Advisory / Scenario Comparison
└── About
    ├── HHTdiary Ecosystem
    ├── Open Source / Repository
    └── Contact / Acknowledgments
```

The final page names and navigation hierarchy should be adjusted to match TripLibre's actual website structure rather than creating unnecessary new navigation patterns.

## 5. Page Content Requirements

### Home

- State what TripLibreLab does in one sentence.
- Show the primary workflow: export a diary from TripLibre, import it into TripLibreLab, replay a selected day, and share an output.
- Present **Replay & Share** as the initial scope.
- Label agent simulation and advisory features as **planned**, not released.
- Link to TripLibre and the HHTdiary organization.
- Display an accurate release status; do not imply App Store availability before approval.

### Documentation — Getting Started

- Prerequisites and supported platforms (to be confirmed).
- How to obtain a compatible TripLibre export.
- How to import a file into TripLibreLab.
- How to choose a day, replay it, and create a shareable output.
- Screenshots only after the actual interface exists.

### Documentation — Data Format

- Document the verified SQLite schema and export version after inspecting TripLibre's implementation.
- Identify required timestamps, coordinates, trip/stay relationships, and optional attributes.
- Describe missing-data behavior, unsupported exports, and compatibility errors.
- Never invent table or column names.

### Documentation — Replay & Share

- Explain how the timeline and map relate to observed diary records.
- Distinguish actual recorded points from any interpolated visual movement.
- Document playback controls and supported export/share formats once implemented.
- Explain location privacy precautions, including optional redaction if supported.

### Roadmap

- **Phase 1 — Replay & Share:** local SQLite import, daily diary visualization, replay, and sharing.
- **Phase 2 — ReShape:** agent-based exploration and synthetic alternatives under explicit model assumptions.
- **Phase 3 — Advisory:** user-defined objectives and constraints; compare alternatives against the unchanged original diary.
- Future features are proposals, not product commitments.

### About

- HHTdiary is the umbrella organization.
- TripLibre is the data collection and diary management app.
- TripLibreLab is the companion exploration and visualization app.
- Include repository, license, acknowledgments, and contact details only when verified.

## 6. Content and Navigation Rules

- Use consistent naming: **TripLibreLab**, **TripLibre**, **HHTdiary**.
- Prefer clear user-facing language; explain terms such as SQLite, agent-based simulation, and travel diary.
- Avoid claiming that a synthetic diary is a prediction of an individual's future behavior.
- Preserve a visible link back to TripLibre and HHTdiary.
- Keep mobile navigation accessible and concise.
- Avoid empty links, fake download buttons, and speculative feature screenshots.

## 7. Suggested Documentation Source Layout

```text
docs/
├── README.md
├── docs-website.md
├── overview.md
├── getting-started.md
├── importing-data.md
├── replay-and-share.md
├── data-and-privacy.md
├── faq.md
├── roadmap.md
└── about.md
```

This is a content-source proposal, not a requirement to change the existing TripLibre site's framework or directory layout.

## 8. First Website Milestone

The first published website should contain:

- A clear homepage and product identity.
- A concise description of the initial Import → Replay → Share workflow.
- A Getting Started page, with unfinished instructions marked as pending until tested.
- A privacy/data-handling explanation grounded in actual implementation.
- A roadmap distinguishing current and future capabilities.
- Working links to the official TripLibre and HHTdiary websites.

**Acceptance criteria:** the site resembles the established TripLibre web experience, communicates what TripLibreLab actually does, contains no unsupported availability claims, and remains usable on desktop and mobile.

## 9. Open Decisions

- Exact TripLibre navigation and page structure to mirror.
- TripLibreLab website hostname and deployment repository.
- Confirmed SQLite export schema and supported versions.
- Exact replay sharing format (image, video, or both).
- App Store availability and final download link.
- Repository/license/contact links.
