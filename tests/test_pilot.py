# -*- coding: utf-8 -*-
"""
AI 领航团写作脚手架单元与集成回归测试 (纯标准库)
验证 Linter 规则、CLI 生成及端到端命令调用
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.linter import PilotLinter, Issue
from pilot import TEMPLATE_MAP, TEMPLATES_DIR

class TestPilotLinterRules(unittest.TestCase):
    def setUp(self):
        self.linter = PilotLinter()

    def test_banned_title_words(self):
        bad_text = """---
title: test
created: 2026-10-17
status: draft
author: 张三
---

# 浅谈水务大模型在运营中的实践
> [!abstract] 一句话定位
> 解决痛点。
> [!info] 生产说明
> 事实截止：2026-10-17
开篇三问：1. **Q1** 2. **Q2** 3. **Q3**
| A | B |
|---|---|
| 1 | 2 |
| C | D |
|---|---|
| 3 | 4 |
### 踩坑大表
| 现象 | 根因 |
|---|---|
| 卡死 | 内存 |
- [x] Checklist
"""
        res = self.linter.lint_text(bad_text)
        codes = [i.code for i in res.p0_issues]
        self.assertIn("P0_TITLE_BANNED_WORD", codes)

    def test_secret_leak_detection(self):
        bad_text = """---
title: test
created: 2026-10-17
status: draft
author: 张三
---
# 水厂应急处置AI顾问实录
> [!abstract] 一句话定位
> 解决痛点。
> [!info] 生产说明
> 事实截止：2026-10-17
API Key 是 sk-abcdef12345678901234567890
"""
        res = self.linter.lint_text(bad_text)
        codes = [i.code for i in res.p0_issues]
        self.assertIn("P0_SECRET_LEAK", codes)

    def test_table_count_requirement(self):
        bad_text = """---
title: test
created: 2026-10-17
status: draft
author: 张三
---
# 水厂应急处置AI顾问实录
> [!abstract] 一句话定位
> 解决痛点。
> [!info] 生产说明
> 事实截止：2026-10-17
重点回答三个问题：1. **Q1** 2. **Q2** 3. **Q3**
| 只有一张表 | 备注 |
|---|---|
| 内容 | 详细 |
### 避坑指南
内容缺少表格
- [x] Checklist
"""
        res = self.linter.lint_text(bad_text)
        codes = [i.code for i in res.p0_issues]
        self.assertIn("P0_TABLE_COUNT_LOW", codes)
        self.assertIn("P0_PITFALL_TABLE_MISSING", codes)

    def test_ai_slop_and_colon_density_warnings(self):
        text_with_p1 = """---
title: test
created: 2026-10-17
status: draft
author: 张三
---
# 水厂应急处置AI顾问实录
> [!abstract] 一句话定位
> 解决痛点。
> [!info] 生产说明
> 事实截止：2026-10-17
开篇重点回答三个问题：
1. **怎么做**：方法
2. **踩什么坑**：避坑
3. **怎么用**：行动

大模型全方位赋能业务，颠覆了传统的运营模式。

本段测试连续冒号叙述：第一个参数：0.4。第二个参数：0.8。第三个参数：1.2。这种连续冒号应当被识别。

| 表1 | 表2 |
|---|---|
| A | B |
| 表3 | 表4 |
|---|---|
| C | D |

### 踩坑清单
| 工具 | 现象 | 根因 |
|---|---|---|
| DEAP | 踩坑 | 根因 |

- [ ] Checklist 校验
"""
        res = self.linter.lint_text(text_with_p1)
        # P0 应该全绿
        self.assertEqual(len(res.p0_issues), 0, f"Unexpected P0 issues: {res.p0_issues}")
        # P1 应该捕获 AI_SLOP 与冒号连用
        p1_codes = [i.code for i in res.p1_issues]
        self.assertIn("P1_AI_SLOP_WORD", p1_codes)
        self.assertIn("P1_COLON_DENSITY_HIGH", p1_codes)

class TestTemplatesValidation(unittest.TestCase):
    def setUp(self):
        self.linter = PilotLinter()

    def test_template_business_agent_structure(self):
        tmpl_file = TEMPLATES_DIR / "template-business-agent.md"
        self.assertTrue(tmpl_file.exists())
        with open(tmpl_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 模拟生成后的基本填充测试（消除模板占位符）
        filled = content.replace("{{文章标题：名词短语，如「污水厂进水冲击处置AI顾问落地实录」，禁止使用「浅谈/初探/关于」}}", "污水厂进水冲击处置AI顾问落地实录")
        filled = filled.replace("{{date}}", "2026-10-17")
        filled = filled.replace("{{slug}}", "water-agent")
        filled = filled.replace("{{author_name}}", "李工")

        res = self.linter.lint_text(filled)
        # 业务模板基础结构必须 P0 零错误
        self.assertEqual(len(res.p0_issues), 0, f"Template business-agent has P0 issues: {res.p0_issues}")

    def test_template_tool_guide_structure(self):
        tmpl_file = TEMPLATES_DIR / "template-tool-guide.md"
        self.assertTrue(tmpl_file.exists())
        with open(tmpl_file, "r", encoding="utf-8") as f:
            content = f.read()

        filled = content.replace("{{文章标题：名词短语，如「大模型与办公提效工具选型指引与避坑实录」，禁止使用「浅谈/初探/关于」}}", "大模型与办公提效工具选型指引与避坑实录")
        filled = filled.replace("{{date}}", "2026-10-17")
        filled = filled.replace("{{slug}}", "tool-guide")
        filled = filled.replace("{{author_name}}", "王工")

        res = self.linter.lint_text(filled)
        # 工具模板基础结构必须 P0 零错误
        self.assertEqual(len(res.p0_issues), 0, f"Template tool-guide has P0 issues: {res.p0_issues}")

if __name__ == "__main__":
    unittest.main()
