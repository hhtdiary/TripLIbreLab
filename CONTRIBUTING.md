# Contributing to TripLibreLab

Thanks for helping. TripLibreLab is early: the design documents and the TripLibre data contract exist, the iOS app
does not yet. The [developer guide](https://triplibrelab.hhtdiary.org/docs/developer.html) explains how the project is
built and in what order.

1. **Set up.** Python 3.10+ for the tools; Node 22 for the docs linters (`npm ci`); `ruff` for Python linting
   (`pipx run ruff check`, or `pip install ruff`). Nothing else is needed yet.
2. **Design before code.** If a change is not covered by `design/`, update the design document first or open an issue.
3. **Run what CI runs** before opening a pull request against `main`: `make ci`. Individually: `make lint`,
   `make a11y`, `make fixtures-check`, `make test`, `make contract-check`. `make help` lists everything.
4. **Keep the contract in step.** A change to `docs/sqlite-data-contract.md` updates the HTML version
   (`docs/docs/data-contract.html`), the fixtures (`make fixtures`, then commit) and `tools/inspect_export.py` in the
   same pull request.
5. **Never commit a real `travel.sqlite`.** Use the synthetic fixtures or extend `tools/make_fixtures.py`.
6. **Mark what is not built.** On the website, anything not yet built and tested is labelled Pending, and there are no
   screenshots until the interface exists.

Small, complete pull requests, one topic each. Questions about recording and exporting belong to
[TripLibre](https://github.com/hhtdiary/TripLibre).
