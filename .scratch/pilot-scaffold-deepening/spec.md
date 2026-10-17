# Spec: AI领航团写作脚手架与规范校验工具集深度化

Status: ready-for-agent

## Problem Statement

一线水务业务与技术同事（如污水厂工艺工程师、大区运营技术员、数据分析专员）在撰写「AI 领航团」科普与实战文章时，面临多重摩擦：
1. **起草无从下手**：缺少针对水务实际业务场景（如进水冲击、投药测算、工艺仿真）的成熟写作范式，要么写成无结构的技术杂谈，要么套用通用大模型软文，充满浮夸套话（如“深度赋能”、“颠覆传统”），缺少可复用的实操步骤与真实负面踩坑清单。
2. **规则门禁多源分叉且隐蔽**：历史演化中存在多套并行的检查脚本，部分规则只在后台自动化流水线（Hermes）运行，部分规则只存在于零散的 Markdown 规约中。作者在本地自检通过的稿件，提交后常因“标题存在禁用词”、“字数不在 1500–2500 之间”、“叙述段冒号过多”、“包含作者开发机本地盘符”或“缺少真实避坑大表”被直接打回。
3. **创作与防重台账割裂**：领航团实行严格的“定题前必查重、开写即占位”纪律。目前作者在本地创建草稿与中央防重台账（`已写清单.md`）完全脱节，容易发生多人撞题或草稿写完却遗漏台账登记，导致后台统计将有效文章误判为积压或漏管。
4. **模板填空与跨环境同步脆弱**：模板占位符采用机械字符串替换，微调模板标点即导致替换静默失败；不同电脑的磁盘拓扑与 Obsidian 仓库路径各异，单向盲拷容易覆写本地工作台未提交的就地修改成果。

## Solution

在独立工程化代码库中构建一套**零外部依赖、深度内聚的领航团写作脚手架与双模规则校验引擎**：
1. **双标准体裁模板与两级模板插槽**：基于领航团已发表的标杆实战文章（如进水冲击 AI 顾问、7月工具选用指引），沉淀「业务实战型」与「工具避坑型」两套开箱即用的 Markdown 模板。插槽生命周期分为两级：创建草稿时自动水化基础元数据槽；正文业务指引槽保留为醒目占位，在草稿阶段作为待办提醒，在终审阶段若仍未填写则阻断。
2. **单源权威判据模块与双模式分流**：将全链路规则统一收敛至唯一的规则引擎核心深模块。对外提供单一接口，并支持两档模式：
   - `draft` 模式（日常草稿）：校验骨架完整性、标题合规、双 Callout、开篇三问、表格数量 ≥ 2 张、真实避坑大表与敏感密钥拦截，放宽字数区间与排版配额；
   - `publish` 模式（终审与后台门禁）：全量激活 1500–2500 字数硬指标、盘符外泄拦截与破折号加粗硬配额。
   后台调度器与工作台技能通过轻量动态适配器直接委托该单源模块，彻底消除多源分叉。
3. **原子化查重与台账生命周期闭环**：通过台账接缝（支持本地权威台账与轻量快照兜底），在执行新建草稿时，先针对选题池与历史已写记录执行相似度查重，警告撞题风险；确认后原子化完成草稿落盘并在台账追加新建登记（若命中选题池则自动将其移出），开写即占位。
4. **防漂移工作台同步器**：提供四级层叠路径探测（CLI 参数 > 环境变量 > 配置文件 > 默认探测），基于内容哈希（SHA256）与修改时间戳比对。当目标工作区存在就地修改时提供防冲拦截与差异比对，支持单向发布与反向保护。

## User Stories

1. As an 一线业务工程师（作者）, I want to run a single command to scaffold a new business-agent article draft, so that I get a fully structured, ready-to-fill Markdown file with correct frontmatter and required sections.
2. As an 一线业务工程师（作者）, I want to specify the article title, author name, and slug during creation, so that the metadata is automatically populated without manual string edits.
3. As an 一线业务工程师（作者）, I want to choose between a business-agent archetype and a tool-guide archetype, so that the generated skeleton matches my specific article topic.
4. As an 一线业务工程师（作者）, I want the scaffold tool to search existing articles and topic pools before creating a draft, so that I am immediately warned if my proposed topic duplicates previous work.
5. As an 一线业务工程师（作者）, I want my newly created draft to be automatically registered into the central ledger as a draft, so that my teammates and automated bots know the topic is claimed.
6. As an 一线业务工程师（作者）, I want a `--no-register` option when creating a draft, so that I can experiment with temporary throwaway drafts without polluting the team ledger.
7. As an 一线业务工程师（作者）, I want the tool to work seamlessly on a standalone machine without access to the private Obsidian vault, so that it falls back to a bundled ledger snapshot and does not crash.
8. As an 一线业务工程师（作者）, I want to export ready-to-use AI drafting system prompts for my chosen archetype, so that I can feed raw field notes into an LLM and receive a compliant initial draft.
9. As an 一线业务工程师（作者）, I want to run a local check command on my in-progress draft, so that I can identify formatting and structural omissions before submitting for review.
10. As an 一线业务工程师（作者）, I want the draft-mode check to tolerate incomplete word counts while pointing out missing required sections, so that I am not prematurely blocked during early drafting.
11. As an 一线业务工程师（作者）, I want to see clear, actionable line-number feedback when my title uses forbidden words like "浅谈" or "初探", so that I know exactly how to revise it into a noun phrase.
12. As an 一线业务工程师（作者）, I want to be warned if I accidentally paste a real API key or plain text password, so that company credentials never enter documentation.
13. As an 一线业务工程师（作者）, I want to be alerted if my draft includes author-specific local drive paths (e.g. `D:\...`), so that readers on other computers do not encounter dead, inaccessible paths.
14. As an 一线业务工程师（作者）, I want to be alerted when a narrative paragraph piles up 3 or more colons in consecutive explanations, so that I can break down robotic "bullet-like" speech into natural sentences.
15. As an 一线业务工程师（作者）, I want to be alerted when a core technical term is clustered 4 or more times within a 100-character window, so that I can eliminate repetitive word stuffing.
16. As an 一线业务工程师（作者）, I want to be reminded if my draft lacks a reader-facing Checklist or single actionable item, so that my article always delivers concrete practical value.
17. As an 文章终审把关人（Reviewer / Editor-in-Chief）, I want to run the checker in publish mode against candidate articles, so that all hard quotas (1500–2500 words, dash quota, bold quota, leak checks) are strictly enforced.
18. As an 文章终审把关人（Reviewer / Editor-in-Chief）, I want publish mode to block any draft that still contains unresolved template slot placeholders (`{{...}}`), so that unfinished boilerplate is never published.
19. As an 文章终审把关人（Reviewer / Editor-in-Chief）, I want to generate a Markdown review report from the CLI, so that I can paste detailed, structured feedback directly into team chat or PR reviews.
20. As an 自动化运维与后台调度器（Hermes cron）, I want the triage script (`article-triage.py`) to invoke the canonical rule module through a dynamic adapter, so that scheduled inspections use identical criteria without rule divergence.
21. As an 自动化运维与后台调度器（Hermes cron）, I want the publish gate (`quality_check.py`) to invoke the canonical rule module in publish mode, so that gating logic is shared 100% with the local CLI tool.
22. As an 知识库维护者（Vault Maintainer）, I want to run a sync command to publish updated templates to the Obsidian vault, so that authors using Obsidian Templater always have access to the latest templates.
23. As an 知识库维护者（Vault Maintainer）, I want the sync command to compute SHA256 hashes and compare modification times, so that local edits in the Obsidian vault are not silently overwritten.
24. As an 知识库维护者（Vault Maintainer）, I want a `--diff` option during sync, so that I can inspect exact template differences between the code repository and the Obsidian vault before committing changes.
25. As an 工程维护开发者, I want the CLI and all core modules to depend exclusively on the Python standard library, so that any colleague on Windows, macOS, or Linux can clone and run immediately without `pip install`.
26. As an 工程维护开发者, I want an end-to-end regression test suite that verifies P0 invariants across all published and draft articles, so that rule optimizations never introduce false negatives or regressions.

## Implementation Decisions

### 1. Modules and Interfaces

- **`PilotCLI` Entry Point**:
  The primary user interface. Exposes commands:
  - `new`: parses archetype, title, author, slug; orchestrates ledger check, template rendering, and file persistence.
  - `check`: executes lint engine in either `draft` or `publish` mode, format results for terminal or markdown.
  - `prompt`: outputs archetype-specific drafting instructions or audit guidelines.
  - `sync-vault`: orchestrates hash-based synchronization with Obsidian workspace.
  - `list`: lists available archetypes, prompts, and current ledger snapshot status.

- **`TemplateRenderer` Deep Module**:
  Responsible for slot discovery, metadata hydration, and unresolved slot diagnostics.
  - Interface: `render(template_text: str, context: dict) -> str`
  - Interface: `find_unresolved_slots(content: str) -> list[str]`
  - Internal behavior: uses regex to identify all `{{slot_name}}` patterns. Replaces provided context keys during initialization. Leaves business slots intact during drafting, but flags them during linting.

- **`LedgerAdapter` Seam**:
  Decouples article creation from the physical Obsidian file layout while preserving the single-ledger invariant.
  - Interface: `search_duplicate(query: str, threshold: float = 0.6) -> list[LedgerMatch]`
  - Interface: `register_draft(title: str, file_name: str, author: str, date: str) -> bool`
  - Implementations / Fallback:
    - `VaultLedgerAdapter`: directly parses and atomic-updates `已写清单.md` using table regex matching.
    - `SnapshotLedgerAdapter`: reads bundled `data/ledger-snapshot.json` when the vault is absent, providing read-only duplicate search and emitting a warning that ledger registration was deferred.

- **`PilotLinter` Deep Module**:
  The single canonical source of truth for pilot article rules.
  - Interface: `lint_file(path: str, mode: str = "draft", keywords: str = "") -> LintResult`
  - Interface: `lint_text(text: str, mode: str = "draft", keywords: str = "") -> LintResult`
  - Two-tier mode behavior:
    - Both modes enforce P0 structural invariants (H1 noun phrase title, abstract callout, info callout, opening questions, ≥2 tables, structured pitfall table with negative feedback, API key leak detection).
    - `publish` mode additionally enforces P0 publish gates (1500–2500 CJK characters, absolute drive letter leaks, internal private jargon, unfilled slot placeholders) and P0 typography quotas (dash frequency, bold per section, anti-patterns).
    - In `draft` mode, character counts and unfilled slots emit informational or P1 advisory diagnostics.

- **`VaultSyncAdapter` Seam**:
  Handles template distribution and drift protection.
  - Interface: `sync(source_dir: Path, target_dir: Path, overwrite: bool = False, show_diff: bool = False) -> SyncSummary`
  - Internal behavior: calculates SHA256 of source and destination files. If destination is missing, creates it. If destination exists and differs, inspects mtime. If destination is newer and overwrite is False, reports conflict with diff preview.

### 2. Backward Compatibility with Existing Backing Scripts

- `C:\Users\14331\AppData\Local\hermes\scripts\article_lint.py`:
  Becomes a transparent delegator:
  ```python
  # Dynamic adapter pattern
  try:
      from core.linter import PilotLinter, lint_article
  except ImportError:
      # Injects E:\beikong-code\ai-pilot-writing into sys.path
      ...
  ```
  Exposes the identical legacy function signature `lint_article(path, *, publish=False, keywords="")` so `quality_check.py` and `article-triage.py` require zero modifications.

### 3. File Layout within `E:\beikong-code\ai-pilot-writing`

```text
E:\beikong-code\ai-pilot-writing\
├── pilot.py                    # Top-level CLI entry point
├── core/
│   ├── __init__.py
│   ├── linter.py               # Canonical two-tier rule engine
│   ├── renderer.py             # Declarative template renderer & slot analyzer
│   ├── ledger.py               # Local-first ledger adapter & snapshot reader
│   ├── vault_sync.py           # Hash-based drift-resistant sync adapter
│   └── reporter.py             # ANSI console & markdown review reporter
├── templates/
│   ├── template-business-agent.md
│   └── template-tool-guide.md
├── prompts/
│   ├── draft-business-agent.md
│   ├── draft-tool-guide.md
│   └── audit-pilot-article.md
├── data/
│   └── ledger-snapshot.json    # Bundled fallback ledger snapshot
├── drafts/                     # Default output directory for generated drafts
├── tests/
│   ├── test_linter.py          # Linter behavioral unit & regression tests
│   ├── test_renderer.py        # Template slot rendering tests
│   ├── test_ledger.py          # Ledger duplicate search & fallback tests
│   └── test_cli.py             # End-to-end pilot CLI integration tests
├── CONTEXT.md                  # Project domain glossary
└── README.md                   # Colleague 3-minute quickstart guide
```

## Testing Decisions

### 1. Testing Philosophy
- Tests must target external module behavior through their highest public seams (`pilot.py` CLI invocation and public methods of `core` modules), never testing private regular expressions or internal helper functions directly.
- All tests must be 100% hermetic and offline, using Python standard library `unittest` and `tempfile`. No live network calls or unmanaged file writes outside temporary directories.

### 2. Tested Seams and Test Suites
- **CLI Seam (`tests/test_cli.py`)**:
  - `test_new_command_creates_valid_draft`: runs `pilot.py new` in a temp dir and asserts generated file passes baseline structural checks.
  - `test_check_command_draft_vs_publish_exit_codes`: runs `pilot.py check` on an incomplete draft, asserting exit code 0 in draft mode and exit code 1 in publish mode.
  - `test_sync_vault_avoids_overwriting_newer_destination`: writes a mutated file to mock vault, runs sync without `--overwrite`, and asserts file was preserved.
- **Rule Engine Seam (`tests/test_linter.py`)**:
  - `test_banned_title_prefixes_trigger_p0`: asserts titles with "浅谈" or "关于" produce `P0_TITLE_BANNED_WORD`.
  - `test_missing_pitfall_table_triggers_p0`: asserts article without negative feedback table triggers `P0_PITFALL_TABLE_MISSING`.
  - `test_secret_leak_triggers_p0`: asserts simulated API keys trigger `P0_SECRET_LEAK`.
  - `test_narrative_colon_density_triggers_p1`: asserts prose paragraph with ≥3 colons triggers `P1_COLON_DENSITY_HIGH`, while markdown tables and bullet lists do not.
  - `test_keyword_clustering_triggers_p1`: asserts 4 occurrences within 100 characters trigger `P1_WORD_STACKING`, while scattered occurrences do not.
  - `test_legacy_real_articles_invariant`: runs against all existing articles in vault (if present), asserting zero P0 regressions against historical baselines.
- **Ledger Seam (`tests/test_ledger.py`)**:
  - `test_duplicate_topic_warning`: feeds exact and fuzzy matching titles, asserting duplicate warning is emitted.
  - `test_offline_snapshot_fallback`: runs in environment where vault path does not exist, asserting snapshot is used and warning emitted.

### 3. Prior Art
- Inspired by `article_lint.test.py` and `aar-write-product.test.py` located in `C:\Users\14331\AppData\Local\hermes\scripts`, which use self-contained temp environments, mock fixtures, and assert strict exit codes without external dependencies.

## Out of Scope

1. **Automatic Publishing to DingTalk Docs / Group Push**:
   Writing to the remote DingTalk knowledge base (`dws doc +doc-append`) or posting robot messages to internal groups remains strictly subject to explicit, separate human authorization. This tool only manages local drafting, formatting, linting, and synchronization.
2. **Third-Party Natural Language Processing Dependencies**:
   Third-party tokenizers (such as `jieba`) or embedding models are strictly excluded. All text analysis, keyword clustering, and similarity scoring must run on standard library regex and string operations.
3. **Multi-User Real-Time Collaborative Lock**:
   Does not implement distributed locks for the central ledger. Ledger conflict detection relies on Git version control and sequential atomic writes.

## Further Notes

- **Compliance with Explanation Text Limit**:
  Any micro-copy or helper text displayed in CLI reports or template headers adheres to the project guideline: informational notes must belong to recognized categories and remain concise (≤12 Chinese characters where applicable).
- **Zero-Token Local Execution**:
  The CLI, linter, renderer, and synchronization tools run entirely locally on CPU, consuming zero LLM API tokens or network bandwidth.
