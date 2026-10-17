# -*- coding: utf-8 -*-
"""
AI 领航团规则引擎单元与双模式回归测试 (纯标准库)
验证 Draft / Publish 模式差异、红线拦截与向后兼容性
"""

from __future__ import annotations

import os
import sys
import unittest
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.linter import (
    PilotLinter,
    LintResult,
    Issue,
    lint_article,
    colon_heavy_paragraphs,
    keyword_stacking,
    find_unresolved_slots,
)

VAULT_DIR = Path(r"D:\obsidian_work\cangku\paper_work\工作台\AI领航团文章")


def create_sample_article(
    title: str = "水厂进水冲击处置AI顾问实录",
    body: str = "",
    chars_filler: int = 1600,
    slots: str = "",
    drives: str = "",
    internal_words: str = "",
    dashes: str = "",
    bolds: str = "",
    banned_word: str = "",
    has_abstract: bool = True,
    has_info: bool = True,
    has_questions: bool = True,
    has_two_tables: bool = True,
    has_pitfall_table: bool = True,
    author: str = "张工",
    status: str = "draft",
    residuals: str = "",
) -> str:
    """按规范构造一篇测试文章"""
    fm = f"---\ntitle: {title}\ncreated: 2026-10-17\nstatus: {status}\nauthor: {author}\n---\n\n"
    h1 = f"# {banned_word + title if banned_word else title}\n\n"
    abstract_block = "> [!abstract] 一句话定位\n> 本篇解决进水冲击处置中的决策延时痛点。\n\n" if has_abstract else ""
    info_block = "> [!info] 生产说明\n> 事实截止：2026-10-17\n\n" if has_info else ""
    questions = "开篇重点回答三个问题：1. **怎么做** 2. **踩什么坑** 3. **怎么用**\n\n" if has_questions else ""

    filler_text = ("工艺运行中的水质与水量平衡需要实时数据支撑与模型测算验证。" * 30)[:chars_filler]

    tables_block = ""
    if has_two_tables:
        tables_block = (
            "| 阶段 | 动作 |\n|---|---|\n| 预警 | 数据采集 |\n\n"
            "| 指标 | 阈值 |\n|---|---|\n| COD | 500 |\n\n"
        )

    pitfall_block = ""
    if has_pitfall_table:
        pitfall_block = (
            "### 踩坑清单与避坑指南\n\n"
            "| 踩坑现象 | 真实根因 | 应对建议 |\n|---|---|---|\n"
            "| 决策滞后 | 传感器延时 | 加权滤波对齐 |\n\n"
        )

    checklist = "- [x] 5分钟落地 Checklist\n"

    content = (
        fm + h1 + abstract_block + info_block + questions
        + body + "\n\n"
        + slots + "\n\n"
        + drives + "\n\n"
        + internal_words + "\n\n"
        + dashes + "\n\n"
        + bolds + "\n\n"
        + residuals + "\n\n"
        + filler_text + "\n\n"
        + tables_block
        + pitfall_block
        + checklist
    )
    return content


class TestPilotLinterRules(unittest.TestCase):
    def setUp(self):
        self.linter = PilotLinter()

    def test_banned_title_prefixes_trigger_p0(self):
        """测试标题禁用词 (浅谈、初探、关于、浅析、探讨) 触发 P0"""
        for banned in ["浅谈", "初探", "关于", "浅析", "探讨"]:
            text = create_sample_article(banned_word=banned)
            res = self.linter.lint_text(text)
            p0_codes = [i.code for i in res.p0_issues]
            self.assertIn("P0_TITLE_BANNED_WORD", p0_codes, f"未拦截禁用词: {banned}")
            self.assertFalse(res.is_valid)

    def test_missing_pitfall_table_triggers_p0(self):
        """测试缺少真实避坑章节或大表触发 P0"""
        # 1. 完全没有避坑章节
        text_no_sec = create_sample_article(has_pitfall_table=False)
        res_no_sec = self.linter.lint_text(text_no_sec)
        p0_codes_no_sec = [i.code for i in res_no_sec.p0_issues]
        self.assertIn("P0_PITFALL_SECTION_MISSING", p0_codes_no_sec)
        self.assertFalse(res_no_sec.is_valid)

        # 2. 有避坑章节但缺少表格
        text_no_tbl = create_sample_article(
            body="### 踩坑清单与避坑指南\n\n这里只有纯文本描述，没有提供 Markdown 表格。\n\n### 下一小节\n\n继续正文。",
            has_pitfall_table=False
        )
        res_no_tbl = self.linter.lint_text(text_no_tbl)
        p0_codes_no_tbl = [i.code for i in res_no_tbl.p0_issues]
        self.assertIn("P0_PITFALL_TABLE_MISSING", p0_codes_no_tbl)
        self.assertFalse(res_no_tbl.is_valid)

    def test_table_count_requirement_triggers_p0(self):
        """测试 Markdown 表格不足 2 张触发 P0_TABLE_COUNT_LOW"""
        text = create_sample_article(has_two_tables=False, has_pitfall_table=False)
        res = self.linter.lint_text(text)
        p0_codes = [i.code for i in res.p0_issues]
        self.assertIn("P0_TABLE_COUNT_LOW", p0_codes)
        self.assertFalse(res.is_valid)

    def test_secret_leak_triggers_p0(self):
        """测试敏感 API Key 与明文密码外泄触发 P0_SECRET_LEAK"""
        # 测试 OpenAI Key
        text1 = create_sample_article(body="测试配置: sk-1234567890abcdef1234567890abcdef")
        res1 = self.linter.lint_text(text1)
        p0_codes1 = [i.code for i in res1.p0_issues]
        self.assertIn("P0_SECRET_LEAK", p0_codes1)

        # 测试密码配置
        text2 = create_sample_article(body="数据库配置: password = 'my_secret_password_123'")
        res2 = self.linter.lint_text(text2)
        p0_codes2 = [i.code for i in res2.p0_issues]
        self.assertIn("P0_SECRET_LEAK", p0_codes2)

        # 测试 GitHub Token
        text3 = create_sample_article(body="TOKEN: ghp_1234567890abcdef1234567890abcdef123456")
        res3 = self.linter.lint_text(text3)
        p0_codes3 = [i.code for i in res3.p0_issues]
        self.assertIn("P0_SECRET_LEAK", p0_codes3)

    def test_narrative_colon_density_triggers_p1(self):
        """测试叙述段冒号密度 ≥3 触发 P1_COLON_DENSITY_HIGH，而表格/列表不误报"""
        # 叙述段冒号连用
        colon_narrative = "参数A：取值0.5。参数B：取值1.0。参数C：取值1.5。这三个参数必须严格对齐。"
        text = create_sample_article(body=colon_narrative)
        res = self.linter.lint_text(text)
        p1_codes = [i.code for i in res.p1_issues]
        self.assertIn("P1_COLON_DENSITY_HIGH", p1_codes)

        # 验证表格行和列表不计入冒号密集段
        table_colon = "| 键 | 解释 |\n|---|---|\n| 参数A：取值0.5 | 解释1 |\n| 参数B：取值1.0 | 解释2 |\n| 参数C：取值1.5 | 解释3 |"
        text_table = create_sample_article(body=table_colon)
        res_table = self.linter.lint_text(text_table)
        p1_codes_table = [i.code for i in res_table.p1_issues]
        self.assertNotIn("P1_COLON_DENSITY_HIGH", p1_codes_table)

    def test_keyword_clustering_triggers_p1(self):
        """测试 100 字窗口内同一核心词 ≥4 次出现触发 P1_WORD_STACKING"""
        # 局部高密度堆叠
        stacked = "进水 进水 进水 进水 " + "中" * 80 + " 其他正常描述内容"
        text = create_sample_article(body=stacked, title="进水水质冲击处置指南")
        res = self.linter.lint_text(text, keywords="进水")
        p1_codes = [i.code for i in res.p1_issues]
        self.assertIn("P1_WORD_STACKING", p1_codes)

        # 全文分散不堆叠
        spread = "进水。" + "中" * 99 + "进水。" + "中" * 99 + "进水。" + "中" * 99 + "进水。"
        text_spread = create_sample_article(body=spread, title="进水水质冲击处置指南")
        res_spread = self.linter.lint_text(text_spread, keywords="进水")
        p1_codes_spread = [i.code for i in res_spread.p1_issues]
        self.assertNotIn("P1_WORD_STACKING", p1_codes_spread)


class TestDraftVsPublishModes(unittest.TestCase):
    def setUp(self):
        self.linter = PilotLinter()

    def test_char_count_draft_warning_vs_publish_p0(self):
        """测试字数在 draft 下仅提示 P1，在 publish 下阻断 P0"""
        # 短文本 (仅 500 字)
        short_text = create_sample_article(chars_filler=500)

        # Draft 模式: P0 为空，P1 包含字数提示
        res_draft = self.linter.lint_text(short_text, mode="draft")
        self.assertEqual(len(res_draft.p0_issues), 0)
        self.assertTrue(res_draft.is_valid)
        self.assertIn("P1_CHAR_COUNT", [i.code for i in res_draft.p1_issues])

        # Publish 模式: 触发 P0 阻断
        res_publish = self.linter.lint_text(short_text, mode="publish")
        self.assertIn("P0_CHAR_COUNT", [i.code for i in res_publish.p0_issues])
        self.assertFalse(res_publish.is_valid)

    def test_unresolved_slots_draft_warning_vs_publish_p0(self):
        """测试未填写模板槽位在 draft 下提示 P1，在 publish 下阻断 P0"""
        slot_text = create_sample_article(slots="在这里填写具体的 {{业务痛点描述}}")

        # Draft 模式: P1 提醒，不阻断
        res_draft = self.linter.lint_text(slot_text, mode="draft")
        self.assertEqual(len(res_draft.p0_issues), 0)
        self.assertTrue(res_draft.is_valid)
        self.assertIn("P1_UNRESOLVED_SLOTS", [i.code for i in res_draft.p1_issues])

        # Publish 模式: P0 阻断
        res_publish = self.linter.lint_text(slot_text, mode="publish")
        self.assertIn("P0_UNRESOLVED_SLOTS", [i.code for i in res_publish.p0_issues])
        self.assertFalse(res_publish.is_valid)

    def test_drive_paths_and_internal_jargon_draft_vs_publish(self):
        """测试本地盘符与内部词在 draft 下为 P1，在 publish 下为 P0"""
        leak_text = create_sample_article(
            drives=r"本地脚本保存在 D:\obsidian_work\scripts\run.ps1",
            internal_words="本文参考了内部资料库与智能体管家的定义，依赖 Hermes 自动化。"
        )

        # Draft 模式: P1 告警，不阻断
        res_draft = self.linter.lint_text(leak_text, mode="draft")
        self.assertEqual(len(res_draft.p0_issues), 0)
        self.assertTrue(res_draft.is_valid)
        draft_p1_codes = [i.code for i in res_draft.p1_issues]
        self.assertIn("P1_LOCAL_PATH", draft_p1_codes)
        self.assertIn("P1_INTERNAL_WORD", draft_p1_codes)

        # Publish 模式: P0 阻断
        res_publish = self.linter.lint_text(leak_text, mode="publish")
        publish_p0_codes = [i.code for i in res_publish.p0_issues]
        self.assertIn("P0_LOCAL_PATH", publish_p0_codes)
        self.assertIn("P0_INTERNAL_WORD", publish_p0_codes)
        self.assertFalse(res_publish.is_valid)

    def test_publish_residuals_trigger_p0(self):
        """测试发布稿残留语法 (双链 [[]]、本地图片 ![]()、额外 callout) 触发 P0"""
        res_text = create_sample_article(
            residuals="详见 [[00-格式规范]] 与本地图片 ![](assets/photo.png) 以及 > [!warning] 额外提醒"
        )
        res_publish = self.linter.lint_text(res_text, mode="publish")
        publish_p0_codes = [i.code for i in res_publish.p0_issues]
        self.assertIn("P0_PUBLISH_RESIDUAL", publish_p0_codes)
        self.assertFalse(res_publish.is_valid)

    def test_publish_typography_quotas_trigger_p0(self):
        """测试发布模式下的排版配额（破折号过多、单节多处加粗、不是A是B）"""
        # 破折号过多 (字数约 1600 字，配额 limit=1，出现 3 处)
        dashes_text = create_sample_article(dashes="—— 第一点 —— 第二点 —— 第三点")
        res_dashes = self.linter.lint_text(dashes_text, mode="publish")
        p0_codes = [i.code for i in res_dashes.p0_issues]
        self.assertIn("P0_DASH_OVERUSE", p0_codes)

        # 单节多处加粗
        bold_text = create_sample_article(bolds="**重点一** 紧接着还有 **重点二** 在同一大节")
        res_bold = self.linter.lint_text(bold_text, mode="publish")
        p0_codes = [i.code for i in res_bold.p0_issues]
        self.assertIn("P0_BOLD_OVERUSE", p0_codes)

        # 「不是A是B」句式过多
        not_a_but_b_text = create_sample_article(
            body="这篇不是常规科普，而是实战操作。后面的方法不在理论，在现场执行。"
        )
        res_pats = self.linter.lint_text(not_a_but_b_text, mode="publish")
        p0_codes = [i.code for i in res_pats.p0_issues]
        self.assertIn("P0_NOT_A_BUT_B", p0_codes)


class TestLintResultAndConvenienceInterface(unittest.TestCase):
    def test_lint_result_dict_indexing_and_compat(self):
        """测试 LintResult 字典式索引与 legacy article_lint.py 输出格式兼容"""
        valid_text = create_sample_article()
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as f:
            f.write(valid_text)
            tmp_path = f.name

        try:
            # 兼容 publish=False
            res = lint_article(tmp_path, publish=False)
            self.assertTrue(isinstance(res, LintResult))
            self.assertTrue(res.is_valid)

            # 字典式访问
            self.assertIn("path", res)
            self.assertIn("chars", res)
            self.assertIn("p0", res)
            self.assertIn("p1", res)
            self.assertIn("facts", res)

            self.assertEqual(res["path"], tmp_path)
            self.assertTrue(isinstance(res["chars"], int))
            self.assertTrue(isinstance(res["p0"], list))
            self.assertTrue(isinstance(res["p1"], list))
            self.assertTrue(isinstance(res["facts"], dict))

            # to_dict 兼容
            d = res.to_dict()
            self.assertEqual(d["path"], tmp_path)
            self.assertEqual(d["p0"], [])

            # 测试 publish=True 参数自动映射为 publish 模式
            short_text = create_sample_article(chars_filler=500)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(short_text)

            res_pub = lint_article(tmp_path, publish=True)
            self.assertFalse(res_pub.is_valid)
            self.assertIn("P0_CHAR_COUNT", [i.code for i in res_pub.p0_issues])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestLegacyRealArticlesInvariant(unittest.TestCase):
    def test_legacy_real_articles_zero_regression(self):
        """对真实生产 Obsidian 文章进行全量对拍回归：历史已写文章在 draft 模式下 P0 零新增"""
        if not VAULT_DIR.exists():
            self.skipTest(f"Obsidian 仓库目录不存在: {VAULT_DIR}")

        articles = sorted(VAULT_DIR.glob("2026-*.md"))
        if not articles:
            self.skipTest("未在工作台找到 2026-*.md 文章")

        linter = PilotLinter()
        for art in articles:
            res = linter.lint_file(str(art), mode="draft")
            # 历史生产稿件在 draft 模式下不能出现阻断性 P0
            self.assertEqual(
                len(res.p0_issues), 0,
                f"历史文章 {art.name} 在 draft 模式下存在意外 P0 阻断: {[i.message for i in res.p0_issues]}"
            )


if __name__ == "__main__":
    unittest.main()
