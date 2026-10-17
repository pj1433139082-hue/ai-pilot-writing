# 04: Drift-Resistant Vault Synchronizer

**What to build:**
An adaptive synchronization module (`core/vault_sync.py`) supporting 4-tier cascading vault discovery (`--vault-path`, `PILOT_VAULT_PATH`, `.pilot.config.json`, default `D:\obsidian_work\...`). It uses SHA256 hashes and mtimes to prevent silent overwriting of in-situ edits in Obsidian, offering diff comparison and force-overwrite flags.

**Blocked by:** 02: Declarative Template Slot Engine & Template Standardization

**Status:** ready-for-agent

- [ ] Implement 4-tier vault directory resolution with local `.pilot.config.json` persistence.
- [ ] Implement SHA256 content comparison between source templates and destination vault files.
- [ ] Prevent overwriting destination files when destination is newer and content differs, unless `--overwrite` is specified.
- [ ] Implement diff summary reporting to show exact template modifications before applying changes.
- [ ] Add unit test suite `tests/test_vault_sync.py` covering new copy, match skip, conflict abort, and overwrite paths.
