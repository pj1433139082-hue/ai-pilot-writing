# 03: Central Ledger Seam & Atomic Duplicate Prevention

**What to build:**
A robust ledger module (`core/ledger.py`) that abstracts interaction with `已写清单.md`. It performs similarity search across existing titles and the topic pool to warn of duplicate topics, atomically appends draft records upon creation, and falls back gracefully to a bundled snapshot (`data/ledger-snapshot.json`) when run in standalone environments.

**Blocked by:** None (can start immediately)

**Status:** completed

- [x] Implement `LedgerAdapter.search_duplicate(query, threshold=0.6)` comparing against written and pooled topics using Jaccard/bigram similarity.
- [x] Implement `LedgerAdapter.register_draft(title, file_name, author, date)` appending a `**draft** 新建` row to `已写清单.md` and removing claimed topics from `## 选题池`.
- [x] Implement offline fallback reading `data/ledger-snapshot.json` when the central vault is unreachable, emitting an explicit fallback notice.
- [x] Generate bundled baseline `data/ledger-snapshot.json` from the current vault ledger.
- [x] Add unit test suite `tests/test_ledger.py` verifying duplicate warnings, atomic registration, and fallback behavior.
