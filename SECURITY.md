# 安全政策与零泄漏守则 (Security Policy & Zero-Leakage)

`ai-pilot-writing` 是北控水务 AI 领航团写作脚手架与自动化工具集。我们高度重视运行安全性、数据隔离与防信息外泄。

## 支持的版本 (Supported Versions)

我们仅针对最新主分支（`main`）提供持续的安全修复与规则审计：

| 版本 / 分支 | 状态 | 说明 |
| :--- | :--- | :--- |
| `main` | :white_check_mark: 支持 | 当前稳定开发分支，要求 Python >= 3.8 |

---

## 零泄漏安全红线 (Zero-Leakage Policy)

**本工具集的设计原则是：标准规范与脚手架工具公开透明，真实内部机密与敏感凭证物理隔离。**

1. **绝对禁止提交与推送的内容**：
   - 真实企业内部系统密码、连接串或未公开网关；
   - 真实第三方平台的 API Token、Key（如 `sk-...`）、Webhook URL（如包含 `access_token` 的机器人地址）；
   - 包含未脱敏真实员工身份证号、私人手机号、涉密资产的真实文章草稿；
   - 本地私有配置文件（如包含私有绝对路径的 `.pilot.config.json` 或 `.env*`）。
2. **规范规则内置拦截**：
   - 脚手架内置的 `core/linter.py` 已包含对常见 Token、Webhook 地址与绝对路径的静态扫描，请在起草和提交时主动运行 `python pilot.py check <draft> --publish` 提前自检。

---

## 漏洞报告 (Reporting a Vulnerability)

如果您在本项目中发现了安全隐患或意外凭证泄露，请**不要**公开发布 Issue。请通过维护者 GitHub 个人主页私信联系，或提交安全通报。维护团队将在 24 小时内介入核实并在主分支合入修复。
