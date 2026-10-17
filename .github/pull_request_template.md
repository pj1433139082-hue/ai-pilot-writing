## 变更描述 (Summary & Motivation)

<!-- 请简要说明此 PR 解决的问题、引入的新特性或技术方案。包含相关的背景动机与实现细节。 -->

## 关联 Issue (Related Issue)

<!-- 
提示：
- 若此 PR 完成并需要关闭对应 Issue，请写：Closes #N 或 Fixes #N
- 若此 PR 仅引用、关联或部分推进，请写：Refs #N（避免提前误关工单）
-->
- Refs #

## 变更类型 (Type of Change)

- [ ] 🐛 **Bug fix** (修复脚手架、规则判定、台账或同步器缺陷)
- [ ] ✨ **New feature** (新增 CLI 命令、模板体裁或规则能力)
- [ ] 📝 **Documentation / Spec** (文档、规范、上下文术语或架构记录更新)
- [ ] ♻️ **Refactoring** (代码重构与性能优化，零破坏公开契约)
- [ ] 🧪 **Tests** (新增或强化单元测试、端到端集成测试)
- [ ] 🔧 **CI / Infrastructure** (GitHub Actions 工作流或仓库配置维护)

## 变更自查清单 (Checklist)

在提交此 Pull Request 之前，请确认已逐项完成本地自检：

- [ ] **零依赖纯标准库约束**：核心代码与 CLI 仅依赖 Python 3.8+ 标准库，无新增第三方依赖。
- [ ] **全量自动化测试通过**：本地执行 `python -m unittest discover tests -v` 100% 绿灯通过。
- [ ] **CLI 冒烟验证通过**：本地执行 `python pilot.py --help` 及相关子命令正常。
- [ ] **🛡️ 零泄漏与安全红线**：
  - [ ] 确认绝无任何真实企业内部凭证、API Key（如 `sk-...`）、Webhook Token；
  - [ ] 确认绝无私有敏感配置文件提交（如 `.pilot.config.json`）；
  - [ ] 测试用例与模板插槽均为脱敏合成内容。
- [ ] **双模契约与向后兼容**：规则改动未破坏 `draft` 与 `publish` 双模判定契约。
