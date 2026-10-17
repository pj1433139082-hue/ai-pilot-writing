# AI 领航团写作脚手架与规范校验工具 (Pilot CLI)

[![Repository checks](https://github.com/pj1433139082-hue/ai-pilot-writing/actions/workflows/checks.yml/badge.svg)](https://github.com/pj1433139082-hue/ai-pilot-writing/actions/workflows/checks.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)

> **为北控水务 AI 领航团量身定制的标准化写作工具集**  
> 抽取领航团标杆实战稿件（如《利用DEAP构建大区风险问答智能体》、《7月议题知识沉淀-AI工具选用指引》）的核心骨架，内置严格的评审红线规则，帮助一线同事 10 分钟快速起草出符合发表标准的高质量业务实操文章。

---

## 🌟 核心特性

1. **两套标准体裁模板**：
   - **业务实战型 (`business`)**：以真实业务痛点为靶心，聚焦实操六步法、关键配置速查、角色五段式提示词、真实踩坑大表与落地 Checklist。
   - **工具避坑型 (`tool`)**：直面工具选型边界，聚焦场景分工对照大表、真实踩坑与负面反馈大表、拿来即用 Prompt 与 5 分钟单一行动项。
2. **纯标准库零依赖**：基于 Python 3.8+ 标准库实现，**无需安装任何第三方库**（免 `pip install`），开箱即用。
3. **两级校验门禁 (P0/P1)**：
   - **P0 级硬阻断（必须清零）**：标题禁用词（杜绝「浅谈/初探/关于」）、开头双 Callout 必填、开篇自述三问引导、Markdown 表格数量 ≥ 2 张、真实踩坑大表包含负面反馈、API 密钥与凭证外泄拦截。
   - **P1 级软优化（建议打磨）**：AI 浮夸套话识别（去 AI 味）、叙述段落冒号连用密度排查、100 字短窗口核心词局部堆叠排查、读者落地物料完整度。
4. **双向融合生态**：CLI 既可独立运行，也可一键同步模板至本地 Obsidian 工作台。

---

## 🚀 三步快速上手指南

### 第一步：一键初始化文章草稿
先 `git clone` 本仓库，在终端进入仓库根目录（即 `pilot.py` 所在目录，后续命令都在此目录执行），运行：

```bash
# 场景 A：起草「业务实战与智能体落地」文章（默认）
python pilot.py new -t business -T "污水厂进水冲击处置AI顾问落地实录" -a "张工/某大区" -s water-agent

# 场景 B：起草「工具选型与避坑测评」文章
python pilot.py new -t tool -T "水务大模型与办公提效工具选型避坑实录" -a "李工/运营部" -s water-tools
```
命令会自动在 `drafts/` 目录下生成带有标准元数据、双 Callout、结构化章节与填空占位符的 Markdown 草稿文件。

---

### 第二步：借助配套 AI 提示词辅助填空与起草
将领航团精炼的起草系统提示词喂给大模型（如网页版大模型、DSH、Cursor 或内部智能体）：

```bash
# 查看并复制业务实战型 System Prompt
python pilot.py prompt -t business

# 查看并复制工具选型型 System Prompt
python pilot.py prompt -t tool

# 查看并复制文章终审把关人 (Editor in Chief) 提示词
python pilot.py prompt -t audit
```

复制全部输出（含标题行）粘贴为大模型的 System Prompt 即可。提示词已按「单轮一次成稿」设计：

- **不会反问你**。贴一句话想法就能出完整初稿，不需要再回答追问；它会把缺失的素材写成 `【待确认: 具体缺什么】` 占位，你再逐个回填。
- **不会长时间空转**。提示词里没有「先问三个问题」「套用某模板文件」「写完自检表格数量」这类会导致模型反复思考的环节，直接出正文。
- **不依赖任何外部文件**。七章骨架已内联在提示词正文里，网页版大模型、DSH、Cursor、内部智能体都可用，不需要另外上传模板。

---

### 第三步：运行规范自检（终审硬门禁把关）
初稿完成后，在本地运行检查器：

```bash
# 文件名按 new 当天的日期生成；请把下面的文件名换成上一步实际生成的那份
# 场景 A：起草阶段自检（宽松模式，字数与槽位仅告警，便于排查格式）
python pilot.py check drafts/2026-10-17-water-agent.md

# 场景 B：终审发布阶段门禁（严格模式，未填槽位、字数不达标、隐私路径硬阻断）
python pilot.py check drafts/2026-10-17-water-agent.md --publish

# 以 Markdown 格式输出详细评审意见（可直接发给作者参考）
python pilot.py check drafts/2026-10-17-water-agent.md --md
```

#### 检查输出示例：

刚用 `new` 生成的空壳草稿必然带 P1（槽位未填、字数未到、还没有来源链接），这才是真实输出：

```text
=== AI 领航团文章规范检查报告 ===
目标文件: drafts\2026-10-17-water-agent.md

[P1 优化项] 发现 6 处文风与表达优化建议 (建议打磨):
  1. [P1_UNRESOLVED_SLOTS] 发现 3 处未填写的模板槽位: business_scene、所在项目/大区/部门、业务痛点
     💡 优化建议: 草稿撰写中，可在定稿前逐步补齐占位插槽
  2. [P1_CHAR_COUNT] 字数 2701 不在 1500–2500 (草稿阶段建议 1500-2500 字)
  3. [P1_AI_SLOP_WORD] 第 22 行出现浮夸/AI套话「领航」
  4. [P1_SRC_SEC_MISSING] 无正式来源小节
  5. [P1_NO_URL] 全文无外部链接
  6. [P1_FETCH_TIME_MISSING] 来源未标抓取/读取时间（B4#5）

--------------------------------------------------
结论: PASS (P0=0, P1=6) - 符合领航团硬门禁要求
```

P0 是硬阻断，草稿阶段也必须清零；P1 是打磨建议，逐条清干净即可定稿。

若存在违规（如标题使用了「浅谈」或缺少避坑大表），终端会精准定位行号并给出具体的修改建议（例如：`💡 修复建议: 修改标题，禁止使用「浅谈」，改用具体名词短语`）。

#### 对整个目录批量检查

`check` 的 target 可以直接给目录，会递归检查其中所有 `.md`：

```bash
# 逐份打印完整报告（文件多时输出很长）
python pilot.py check drafts

# 只看每份的结论 + 汇总（推荐用于几十份以上的目录）
python pilot.py check drafts --quiet
```

`--quiet` 每个文件只打印一行，例如：

```text
PASS  P0=0 P1=6  drafts\2026-10-17-water-agent.md

汇总: 共检查 1 个文件，通过 1 个，未通过 0 个。
```

**注意检查范围**：`check` 会递归检查目录下所有 `.md`，单个文件约 10–15 ms。指向文章目录即可（例如 Obsidian 里 `工作台/AI领航团文章`），**不要直接对整个笔记库根目录跑**——几万个文件会跑上十几分钟。目录枚举不跟随符号链接与 Windows 目录联结（junction），避免联结成环时文件数被放大。

---

## 🛠 更多常用命令

| 命令 | 说明 |
|---|---|
| `python pilot.py list` | 查看当前已收录的所有文章模板、AI 提示词清单与中央防重台账连接状态 |
| `python pilot.py sync-vault` | 一键将最新模板同步至 Obsidian 工作台（具备防冲保护与哈希防漂移） |
| `python pilot.py sync-vault --diff` | 预览本地工作台模板与脚手架源模板的逐行差异 (unified diff) |
| `python pilot.py sync-vault --overwrite` | 强制使用源模板覆盖工作台已有修改 |
| `python pilot.py check <目录> --quiet` | 批量检查整个目录时只输出每个文件的 PASS/FAIL 与汇总，避免刷屏 |
| `python -m unittest discover tests` | 运行全量 91 项单元测试与 CLI 端到端集成测试套件 |

---

## 📁 目录结构说明

```text
ai-pilot-writing/
├── pilot.py                 # 顶层 CLI 统一入口 (new/prompt/check/sync-vault/list)
├── core/
│   ├── linter.py            # 权威规则引擎 (draft/publish 双模、P0/P1 规范判定)
│   ├── renderer.py          # 声明式模板插槽水化与未填槽位静态扫描引擎
│   ├── ledger.py            # 中央台账防重适配器 (相似度模糊去重、原子入库、快照兜底)
│   ├── vault_sync.py        # 防漂移工作台同步器 (层叠路径探测、防冲保护、diff预览)
│   └── reporter.py          # 控制台彩色与 Markdown 评审报告输出器
├── data/
│   └── ledger-snapshot.json # 离线快照备份（台账无法直连时保底查重）
├── templates/
│   ├── template-business-agent.md  # 业务实战型标准模板
│   └── template-tool-guide.md      # 工具选型与避坑型标准模板
├── prompts/
│   ├── draft-business-agent.md     # 业务实战型 AI 起草 System Prompt
│   ├── draft-tool-guide.md         # 工具避坑型 AI 起草 System Prompt
│   └── audit-pilot-article.md      # 终审评估与打回把关 System Prompt
├── drafts/                  # 日常撰写草稿归档目录
├── tests/                   # 自动化测试套件 (91 tests, 100% PASS)
│   ├── test_linter.py       # 规则引擎单元测试
│   ├── test_renderer.py     # 模板引擎与插槽水化测试
│   ├── test_ledger.py       # 台账防重与选题核销测试
│   ├── test_vault_sync.py   # 工作台同步与冲突保护测试
│   └── test_cli.py          # CLI 端到端完整闭环测试
├── CONTEXT.md               # 项目领域词汇表与术语规范
└── README.md                # 快速上手指南（本文档）
```
