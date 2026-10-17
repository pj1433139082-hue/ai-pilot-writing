# 04: Drift-Resistant Vault Synchronizer

**What to build:**
An adaptive synchronization module (`core/vault_sync.py`) supporting 4-tier cascading vault discovery (`--vault-path`, `PILOT_VAULT_PATH`, `.pilot.config.json`, default `D:\obsidian_work\...`). It uses SHA256 hashes and mtimes to prevent silent overwriting of in-situ edits in Obsidian, offering diff comparison and force-overwrite flags.

**Blocked by:** 02: Declarative Template Slot Engine & Template Standardization

**Status:** completed

- [x] Implement 4-tier vault directory resolution with local `.pilot.config.json` persistence.
- [x] Implement SHA256 content comparison between source templates and destination vault files.
- [x] Prevent overwriting destination files when destination is newer and content differs, unless `--overwrite` is specified.
- [x] Implement diff summary reporting to show exact template modifications before applying changes.
- [x] Add unit test suite `tests/test_vault_sync.py` covering new copy, match skip, conflict abort, and overwrite paths.
