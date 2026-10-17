# 02: Declarative Template Slot Engine & Template Standardization

**What to build:**
A declarative template rendering module (`core/renderer.py`) that scans `{{slot_name}}` placeholders, hydratable metadata fields, and unresolved slots. Standardize both `template-business-agent.md` and `template-tool-guide.md` with uniform placeholder keys, replacing brittle hard-coded string `.replace()` chains.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Implement `TemplateRenderer.render(template_content, context)` to hydrate metadata keys (`date`, `slug`, `author`, `topic`, `title`, `alias_1`, `alias_2`).
- [ ] Implement `TemplateRenderer.find_unresolved_slots(content)` to detect any lingering `{{...}}` tags for linter inspection.
- [ ] Refactor `templates/template-business-agent.md` and `templates/template-tool-guide.md` with standard slot names.
- [ ] Add unit test suite `tests/test_renderer.py` asserting clean rendering, multi-slot hydration, and unresolved slot reporting.
