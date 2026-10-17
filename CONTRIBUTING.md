# 贡献指南 (Contributing Guide)

感谢你对 **AI 领航团写作脚手架与规范校验工具 (Pilot CLI)** 的关注与贡献！

本项目为北控水务 AI 领航团的标准化文章写作、模板沉淀与双模门禁检查提供纯标准库脚手架支持。

在参与贡献前，请先阅读我们的 [行为准则 (CODE_OF_CONDUCT.md)](CODE_OF_CONDUCT.md) 与 [安全政策 (SECURITY.md)](SECURITY.md)。

---

## 1. 核心设计原则

在开发或提交代码前，请牢记以下四项架构约束：

1. **纯标准库零外部依赖**：
   - 核心模块 (`core/`) 和顶层 CLI (`pilot.py`) **仅允许使用 Python 3.8+ 标准库**；
   - 严禁引入任何需要 `pip install` 的第三方重型依赖，确保一线写作者开箱即用。
2. **两级校验与双模判定契约**：
   - 规则判定严格区分为 `P0`（硬阻断，必须清零）与 `P1`（软优化建议）；
   - 校验支持 `draft`（起草宽容模式，字数与槽位仅告警）与 `publish`（终审发布模式，槽位未填与字数不达标硬阻断）；
   - 保持 `core/linter.py` 作为规则唯一真理源 (SSOT)。
3. **中央台账解耦与快照兜底**：
   - 中央防重台账仅在目标 Obsidian 路径有效时进行原子登记与核销；
   - 离线或路径缺失时，必须降级使用本地 `data/ledger-snapshot.json` 快照，绝不可抛出未捕获异常。
4. **工作台同步防冲保护**：
   - 同步模板至本地 Obsidian 工作台时，必须通过 SHA256 哈希与时间戳检测本地修改，默认防冲保护不强制覆盖。

---

## 2. 本地开发与测试流程

### 2.1 克隆仓库

```bash
git clone https://github.com/pj1433139082-hue/ai-pilot-writing.git
cd ai-pilot-writing
```

### 2.2 运行全量自动化测试

在提交前，请在项目根目录运行纯标准库单元测试与 CLI 端到端测试：

```bash
python -m unittest discover tests -v
```

要求 89 项测试（含 Linter、Renderer、Ledger、VaultSync 及 CLI 集成）全绿通过（`OK`）。

### 2.3 CLI 冒烟验证

验证常用命令运行正常：

```bash
python pilot.py --help
python pilot.py list
python pilot.py prompt -t business
```

---

## 3. 提交与 PR 规范

1. **分支命名**：
   - 新特性：`feat/<feature-name>`
   - 缺陷修复：`fix/<bug-name>`
   - 文档/规范：`docs/<doc-name>`
2. **Commit 规范**：遵循常规提交信息格式，如 `feat(cli): add ...`、`fix(linter): resolve ...`、`docs(readme): update ...`。
3. **PR 关联**：
   - 关联并关闭 Issue：`Closes #12`
   - 仅引用参考而不关闭：`Refs #12`
4. **门禁检查**：提交 PR 后，GitHub Actions CI (`checks`) 将自动运行多版本 Python 测试。门禁转绿后方可合并。
