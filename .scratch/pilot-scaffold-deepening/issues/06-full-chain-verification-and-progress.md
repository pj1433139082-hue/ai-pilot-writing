# 06: Full-Chain Verification, Vault Synchronization & Progress Documentation

**What to build:**
Run full-chain regression across all test suites, sync the standardized templates to the live Obsidian vault, and record all implementation details, test outputs, and evidence into `docs/project/progress.md`.

**Blocked by:** 05: Unified Pilot CLI Integration & End-to-End Orchestration

**Status:** ready-for-agent

- [ ] Execute `tests/test_linter.py`, `tests/test_renderer.py`, `tests/test_ledger.py`, `tests/test_vault_sync.py`, and `tests/test_cli.py`, asserting all pass with exit code 0.
- [ ] Run `python C:\Users\14331\AppData\Local\hermes\scripts\article_lint.test.py` and `eod-push-dingtalk.test.py`, asserting backward compatibility remains intact.
- [ ] Run `python pilot.py sync-vault` to publish final templates to Obsidian workspace `D:\obsidian_work\cangku\paper_work\工作台\模板`.
- [ ] Update `docs/project/progress.md` with ticket completion records, file paths, line numbers, and test execution evidence.
