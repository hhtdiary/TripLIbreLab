# TripLIbreLab

Your Personal mobility laboratory. Transform your travel diary into interactive journeys, explore alternative travel patterns, and understand your mobility choices

## Status

Concept and planning. See `design/TripLibreLab-framework.md` (product framework), `design/first-step.md`
(V0.1 scope) and `docs/sqlite-data-contract.md` (the TripLibre `travel.sqlite` schema the importer is built
against). Synthetic test databases live in `fixtures/`; `tools/inspect_export.py` checks any export against the
contract without modifying it, and `make ci` runs the same lint, accessibility and contract checks as GitHub Actions.
The documentation website in `docs/` has a
[developer guide](https://triplibrelab.hhtdiary.org/docs/developer.html) explaining how the project is built.
