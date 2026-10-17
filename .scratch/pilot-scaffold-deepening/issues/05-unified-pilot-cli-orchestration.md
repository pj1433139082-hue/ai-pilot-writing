# 05: Unified Pilot CLI Integration & End-to-End Orchestration

**What to build:**
Refactor the top-level CLI (`pilot.py`) to wire together `TemplateRenderer`, `PilotLinter`, `LedgerAdapter`, and `VaultSyncAdapter`. Support commands `new` (with duplicate check and atomic registration), `check` (with `--mode draft|publish` and `--md`), `prompt`, `sync-vault`, and `list`.

**Blocked by:** 01: Canonical Rule Engine Consolidation & Backward Compatibility Seam, 02: Declarative Template Slot Engine & Template Standardization, 03: Central Ledger Seam & Atomic Duplicate Prevention, 04: Drift-Resistant Vault Synchronizer

**Status:** ready-for-agent

- [ ] Connect `pilot new` to `LedgerAdapter.search_duplicate` and `register_draft` (honoring `--no-register`).
- [ ] Connect `pilot check` to `PilotLinter.lint_file` supporting `--mode draft|publish` and formatted console/markdown reports.
- [ ] Connect `pilot sync-vault` to `VaultSyncAdapter.sync` with `--vault-path`, `--overwrite`, and `--diff`.
- [ ] Retain zero third-party dependencies (pure standard library).
- [ ] Add end-to-end integration test suite `tests/test_cli.py` testing all commands and options.
