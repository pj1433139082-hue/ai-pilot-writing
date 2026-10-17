# 01: Canonical Rule Engine Consolidation & Backward Compatibility Seam

**What to build:**
A single authoritative rule module (`core/linter.py`) that unifies all formatting, structure, quotas, and security checks across the writing pipeline, featuring two verification modes (`draft` and `publish`). It exposes a transparent delegator in Hermes (`article_lint.py`) so all existing automated tools continue to function without rule divergence.

**Blocked by:** None (can start immediately)

**Status:** completed

- [x] Consolidate full P0 rules (H1 noun phrase title, abstract/info callouts, opening three questions, tables >= 2, structured pitfall table with negative feedback, and API secret leak detection).
- [x] Implement dual-mode checking: in `draft` mode, character counts and unresolved template slots are reported as warnings; in `publish` mode, 1500–2500 CJK characters, absolute drive path leaks, private internal jargon, and unresolved slots trigger P0 blocks.
- [x] Implement P1 diagnostics: narrative colon density (>=3 colons in narrative paragraphs) and 100-character keyword window clustering (>=4 occurrences).
- [x] Provide legacy delegation in `C:\Users\14331\AppData\Local\hermes\scripts\article_lint.py` delegating to `core.linter.lint_article`.
- [x] Verify `tests/test_linter.py` and `article_lint.test.py` pass with zero regressions against historical articles.
