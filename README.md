# AI 领航团写作脚手架与规范校验工具 (Pilot CLI)

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
在终端进入本项目根目录 `E:\beikong-code\ai-pilot-writing`，运行：

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
提示词已完整注入了领航团全部规范与排版要求，同事只需把业务痛点、系统截图和踩坑细节告诉 AI，即可自动输出符合骨架的初稿。

---

### 第三步：运行规范自检（终审硬门禁把关）
初稿完成后，在本地运行检查器：

```bash
# 场景 A：起草阶段自检（宽松模式，字数与槽位仅告警，便于排查格式）
python pilot.py check drafts/2026-10-16-water-agent.md

# 场景 B：终审发布阶段门禁（严格模式，未填槽位、字数不达标、隐私路径硬阻断）
python pilot.py check drafts/2026-10-16-water-agent.md --publish

# 以 Markdown 格式输出详细评审意见（可直接发给作者参考）
python pilot.py check drafts/2026-10-16-water-agent.md --md
```

#### 检查输出示例：
```text
=== AI 领航团文章规范检查报告 ===
目标文件: E:\beikong-code\ai-pilot-writing\drafts\2026-10-16-water-agent.md

✔ 完美通过！未发现任何 P0 阻断项或 P1 优化项。
--------------------------------------------------
结论: PASS (P0=0, P1=0) - 符合领航团硬门禁要求
```

若存在违规（如标题使用了「浅谈」或缺少避坑大表），终端会精准定位行号并给出具体的修改建议（例如：`💡 修复建议: 修改标题，禁止使用「浅谈」，改用具体名词短语`）。

---

## 🛠 更多常用命令

| 命令 | 说明 |
|---|---|
| `python pilot.py list` | 查看当前已收录的所有文章模板、AI 提示词清单与中央防重台账连接状态 |
| `python pilot.py sync-vault` | 一键将最新模板同步至 Obsidian 工作台（具备防冲保护与哈希防漂移） |
| `python pilot.py sync-vault --diff` | 预览本地工作台模板与脚手架源模板的逐行差异 (unified diff) |
| `python pilot.py sync-vault --overwrite` | 强制使用源模板覆盖工作台已有修改 |
| `python -m unittest discover tests` | 运行全量 89 项单元测试与 CLI 端到端集成测试套件 |

---

## 📁 目录结构说明

```text
E:\beikong-code\ai-pilot-writing\
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
├── tests/                   # 自动化测试套件 (89 tests, 100% PASS)
│   ├── test_linter.py       # 规则引擎单元测试
│   ├── test_renderer.py     # 模板引擎与插槽水化测试
│   ├── test_ledger.py       # 台账防重与选题核销测试
│   ├── test_vault_sync.py   # 工作台同步与冲突保护测试
│   └── test_cli.py          # CLI 端到端完整闭环测试
├── CONTEXT.md               # 项目领域词汇表与术语规范
└── README.md                # 快速上手指南（本文档）
```
