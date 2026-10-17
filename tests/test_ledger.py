# -*- coding: utf-8 -*-
"""
AI 领航团文章台账适配器单元测试 (纯标准库 unittest)
覆盖防重查重、原子草稿登记、选题池核销与离线快照兜底
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.ledger import (
    LedgerAdapter,
    cjk_bigrams,
    cjk_bigram_similarity,
    is_matching_topic,
    parse_markdown_ledger,
    DEFAULT_SNAPSHOT_PATH
)

MOCK_VAULT_LEDGER = """---
title: AI领航团文章-已写清单
tags: [kind/index, topic/ai-pilot]
aliases: [文章防重表, 选题池]
created: 2026-09-23
updated: 2026-10-17
related_notes:
  - "[[00-格式规范]]"
---

# 已写清单 / 选题池

## 已写（按日期倒序）

| 日期 | 标题 | 来源 | 状态 | 文件 | 发布后反馈 |
|---|---|---|---|---|---|
| 2026-10-09 | 多 Agent 跑不顺，缺的不是 Agent，是任务状态外置 | 一手核查 | **published** | `2026-10-09-multi-agent-sessionstore.md` | — |
| 2026-10-09 | AI 输出的工艺数据核验三步法 | 领航团文档 | **ready** | `2026-10-09-ai-output-data-verify.md` | — |

## 选题池（待写）

| 优先级 | 题目 | 素材源 | 切入角 | 已占主题 | 同主题上次发布 |
|---|---|---|---|---|---|
| 中 | univer：可编程表格运行时能不能替 SED 台账取数 | 当日信号 | demo | 台账取数 | — |
| 中 | open-webui：企业内网可自部署的本地模型统一 Web 面板 | 当日信号 | demo | — | — |

## 已弃选题（写明原因，避免重复考虑）

| 题目 | 弃用原因 | 弃用日期 |
|---|---|---|
| Excel 里用上 AI | 撞题 | 2026-10-11 |
"""


class TestLedgerSimilarity(unittest.TestCase):
    """测试 CJK Bigram Jaccard 相似度计算与匹配"""

    def test_exact_match_score(self):
        t1 = "多 Agent 跑不顺，缺的不是 Agent，是任务状态外置"
        t2 = "多 Agent 跑不顺，缺的不是 Agent，是任务状态外置"
        score = cjk_bigram_similarity(t1, t2)
        self.assertEqual(score, 1.0)

    def test_space_insensitivity(self):
        t1 = "多 Agent 跑不顺"
        t2 = "多Agent跑不顺"
        score = cjk_bigram_similarity(t1, t2)
        self.assertEqual(score, 1.0)

    def test_punctuation_insensitivity(self):
        t1 = "多 Agent 跑不顺，缺的不是 Agent，是任务状态外置"
        t2 = "多 Agent 跑不顺：缺的不是 Agent：是任务状态外置"
        score = cjk_bigram_similarity(t1, t2)
        self.assertEqual(score, 1.0)

    def test_partial_match_score(self):
        query = "AI 输出的工艺数据核验"
        target = "AI 输出的工艺数据核验三步法"
        score = cjk_bigram_similarity(query, target)
        self.assertGreaterEqual(score, 0.6)
        self.assertLess(score, 1.0)

    def test_unrelated_match_score(self):
        query = "水务现场加药泵故障排查与应急预案"
        target = "多 Agent 跑不顺，缺的不是 Agent，是任务状态外置"
        score = cjk_bigram_similarity(query, target)
        self.assertEqual(score, 0.0)

    def test_empty_string_handling(self):
        self.assertEqual(cjk_bigram_similarity("", "测试标题"), 0.0)
        self.assertEqual(cjk_bigram_similarity("", ""), 1.0)


class TestLedgerParsing(unittest.TestCase):
    """测试 Markdown 表格解析"""

    def test_parse_markdown_tables(self):
        data = parse_markdown_ledger(MOCK_VAULT_LEDGER)
        written = data["written"]
        pool = data["pool"]

        self.assertEqual(len(written), 2)
        self.assertEqual(written[0]["title"], "多 Agent 跑不顺，缺的不是 Agent，是任务状态外置")
        self.assertEqual(written[0]["date"], "2026-10-09")
        self.assertEqual(written[0]["status"], "**published**")
        self.assertEqual(written[1]["title"], "AI 输出的工艺数据核验三步法")

        self.assertEqual(len(pool), 2)
        self.assertEqual(pool[0]["title"], "univer：可编程表格运行时能不能替 SED 台账取数")
        self.assertEqual(pool[0]["priority"], "中")
        self.assertEqual(pool[1]["title"], "open-webui：企业内网可自部署的本地模型统一 Web 面板")


class TestLedgerDuplicateSearch(unittest.TestCase):
    """测试重复标题搜索功能"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ledger_file = Path(self.temp_dir.name) / "已写清单.md"
        self.ledger_file.write_text(MOCK_VAULT_LEDGER, encoding="utf-8")
        self.adapter = LedgerAdapter(ledger_path=self.ledger_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_duplicate_search_exact_match(self):
        matches = self.adapter.search_duplicate("多 Agent 跑不顺，缺的不是 Agent，是任务状态外置")
        self.assertTrue(len(matches) >= 1)
        top = matches[0]
        self.assertEqual(top["score"], 1.0)
        self.assertEqual(top["title"], "多 Agent 跑不顺，缺的不是 Agent，是任务状态外置")
        self.assertEqual(top["table"], "written")
        self.assertEqual(top["details"]["date"], "2026-10-09")

    def test_duplicate_search_partial_match(self):
        matches = self.adapter.search_duplicate("工艺数据核验三步法", threshold=0.5)
        self.assertTrue(len(matches) >= 1)
        self.assertIn("工艺数据核验", matches[0]["title"])
        self.assertGreaterEqual(matches[0]["score"], 0.5)
        self.assertEqual(matches[0]["table"], "written")

    def test_duplicate_search_matches_pool(self):
        matches = self.adapter.search_duplicate("univer 可编程表格运行时", threshold=0.5)
        self.assertTrue(len(matches) >= 1)
        top = matches[0]
        self.assertIn("univer", top["title"])
        self.assertEqual(top["table"], "pool")
        self.assertEqual(top["details"]["priority"], "中")

    def test_duplicate_search_no_match(self):
        matches = self.adapter.search_duplicate("完全不相干的自来水漏损控制实战", threshold=0.5)
        self.assertEqual(len(matches), 0)


class TestLedgerRegisterDraft(unittest.TestCase):
    """测试登记草稿与选题池核销"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ledger_file = Path(self.temp_dir.name) / "已写清单.md"
        self.ledger_file.write_text(MOCK_VAULT_LEDGER, encoding="utf-8")
        self.adapter = LedgerAdapter(ledger_path=self.ledger_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_register_draft_and_remove_from_pool(self):
        draft_title = "univer：可编程表格运行时能不能替 SED 台账取数"
        file_name = "2026-10-18-univer-sed.md"
        res = self.adapter.register_draft(
            title=draft_title,
            file_name=file_name,
            author="张三",
            date="2026-10-18"
        )

        self.assertTrue(res["success"])
        self.assertTrue(res["registered"])
        self.assertFalse(res["snapshot_fallback"])
        self.assertIn(draft_title, res["removed_from_pool"])

        # 读取写回后的 Markdown 验证
        content = self.ledger_file.read_text(encoding="utf-8")

        # 1. 验证 frontmatter updated 更新
        self.assertIn("updated: 2026-10-18", content)

        # 2. 验证已写表首行追加
        expected_row = f"| 2026-10-18 | {draft_title} | 本地草稿（张三） | **draft** 新建 | `{file_name}` | — |"
        self.assertIn(expected_row, content)

        # 验证新插入行位于原有第一行之前
        idx_new = content.find(expected_row)
        idx_old = content.find("多 Agent 跑不顺")
        self.assertLess(idx_new, idx_old)

        # 3. 验证选题池已移除 univer，但保留 open-webui
        parsed = self.adapter.parse_ledger()
        pool_titles = [p["title"] for p in parsed["pool"]]
        self.assertNotIn(draft_title, pool_titles)
        self.assertIn("open-webui：企业内网可自部署的本地模型统一 Web 面板", pool_titles)

        # 4. 验证已写表条目数变为 3
        self.assertEqual(len(parsed["written"]), 3)
        self.assertEqual(parsed["written"][0]["title"], draft_title)

    def test_register_draft_not_in_pool(self):
        draft_title = "进水负荷冲击下的反硝化碳源投加控制实战"
        file_name = "2026-10-18-carbon-source-control.md"
        res = self.adapter.register_draft(
            title=draft_title,
            file_name=file_name,
            author="李四",
            date="2026-10-18"
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["removed_from_pool"], [])

        parsed = self.adapter.parse_ledger()
        self.assertEqual(len(parsed["written"]), 3)
        self.assertEqual(len(parsed["pool"]), 2)  # 选题池数量保持未变

    def test_register_draft_defaults_and_backtick_file_name(self):
        # 验证默认作者、默认日期与文件名自带反引号时的处理
        res = self.adapter.register_draft(
            title="新默认作者测试文章",
            file_name="`2026-10-18-default-author.md`"
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["author"], "领航团成员")
        self.assertEqual(res["file_name"], "2026-10-18-default-author.md")
        self.assertIn("`2026-10-18-default-author.md`", res["row"])
        self.assertNotIn("``", res["row"])  # 没有双重反引号
        self.assertIn("本地草稿（领航团成员）", res["row"])

    def test_register_draft_removes_from_pool_by_substring(self):
        # 选题池原题目为 "open-webui：企业内网可自部署的本地模型统一 Web 面板"
        # 用户标题为 "open-webui：企业内网可自部署"（子串）
        draft_title = "open-webui：企业内网可自部署"
        res = self.adapter.register_draft(
            title=draft_title,
            file_name="open-webui-test.md",
            author="王五",
            date="2026-10-18"
        )
        self.assertTrue(res["success"])
        self.assertEqual(len(res["removed_from_pool"]), 1)
        self.assertIn("open-webui", res["removed_from_pool"][0])

    def test_export_snapshot(self):
        out_snap = Path(self.temp_dir.name) / "exported_snap.json"
        res_path = self.adapter.export_snapshot(out_snap)
        self.assertTrue(res_path.exists())
        with open(res_path, "r", encoding="utf-8") as f:
            snap_data = json.load(f)
        self.assertIn("written", snap_data)
        self.assertIn("pool", snap_data)
        self.assertEqual(len(snap_data["written"]), 2)
        self.assertEqual(len(snap_data["pool"]), 2)


class TestLedgerSnapshotFallback(unittest.TestCase):
    """测试中央台账不可达时的离线快照兜底机制"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.non_existent_vault = Path(self.temp_dir.name) / "not_found" / "已写清单.md"
        self.adapter = LedgerAdapter(
            ledger_path=self.non_existent_vault,
            snapshot_path=DEFAULT_SNAPSHOT_PATH
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_vault_not_available_flag(self):
        self.assertFalse(self.adapter.is_vault_available)

    def test_search_duplicate_using_snapshot(self):
        # 依赖打包在 data/ledger-snapshot.json 中的基线数据
        matches = self.adapter.search_duplicate("AI 输出的工艺数据核验", threshold=0.5)
        self.assertTrue(len(matches) >= 1)
        self.assertIn("AI 输出的工艺数据核验", matches[0]["title"])
        self.assertEqual(matches[0]["table"], "written")
        self.assertGreaterEqual(matches[0]["score"], 0.7)

    def test_register_draft_fallback_notice(self):
        res = self.adapter.register_draft(
            title="离线测试草稿",
            file_name="offline-test.md",
            author="离线工程师",
            date="2026-10-18"
        )

        self.assertTrue(res["success"])
        self.assertFalse(res["registered"])
        self.assertTrue(res["snapshot_fallback"])
        self.assertIn("快照兜底模式", res["notice"])
        self.assertEqual(len(self.adapter.memory_drafts), 1)
        self.assertEqual(self.adapter.memory_drafts[0]["title"], "离线测试草稿")


if __name__ == "__main__":
    unittest.main()
