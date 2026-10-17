# -*- coding: utf-8 -*-
"""
AI 领航团统一 CLI 端到端集成测试 (tests/test_cli.py)
覆盖 pilot.py top-level CLI 的 new / check / sync-vault / prompt / list 全指令、参数及 exit code。
纯 Python 3 标准库 unittest 与 subprocess 实现。
"""

import os
import sys
import time
import shutil
import itertools
import tempfile
import unittest
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PILOT_PY = BASE_DIR / "pilot.py"
TEMPLATES_DIR = BASE_DIR / "templates"
PROMPTS_DIR = BASE_DIR / "prompts"

MOCK_VAULT_LEDGER = """---
title: AI领航团文章-已写清单
tags: [kind/index, topic/ai-pilot]
aliases: [文章防重表, 选题池]
created: 2026-09-23
updated: 2026-10-17
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
"""


def run_cli(*args, env=None):
    """运行 pilot.py CLI 命令并捕获返回结果"""
    cmd = [sys.executable, str(PILOT_PY)] + list(args)
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(BASE_DIR),
        env=proc_env
    )


class TestCliNew(unittest.TestCase):
    """测试 pilot.py new 命令"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

        # 构造 mock vault 及其台账
        self.vault_dir = self.work_dir / "mock_vault"
        self.ledger_file = self.vault_dir / "工作台" / "AI领航团文章" / "已写清单.md"
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_file.write_text(MOCK_VAULT_LEDGER, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_new_business_draft_creation(self):
        """测试创建业务实战型草稿并验证元数据插槽水化"""
        out_draft = self.work_dir / "test-biz-draft.md"
        res = run_cli(
            "new",
            "-t", "business",
            "-T", "污水厂进水负荷冲击处置AI实录",
            "-s", "water-biz",
            "-a", "张工",
            "-o", str(out_draft),
            "--no-register",
            "--vault-path", str(self.vault_dir)
        )
        self.assertEqual(res.returncode, 0, f"CLI stderr: {res.stderr}")
        self.assertTrue(out_draft.exists())

        content = out_draft.read_text(encoding="utf-8")
        self.assertIn("污水厂进水负荷冲击处置AI实录", content)
        self.assertIn("张工", content)
        self.assertIn("water-biz", content)
        self.assertIn("> [!abstract] 一句话定位", content)
        self.assertIn("> [!info] 生产说明", content)
        self.assertIn("✔ 成功创建文章草稿", res.stdout)
        self.assertIn("[--no-register] 跳过中央台账登记", res.stdout)

    def test_new_tool_guide_draft_creation(self):
        """测试创建工具避坑型草稿"""
        out_draft = self.work_dir / "test-tool-draft.md"
        res = run_cli(
            "new",
            "-t", "tool",
            "-T", "行业大模型与办公提效工具选型指引",
            "-s", "tool-guide",
            "-a", "李工",
            "-o", str(out_draft),
            "--no-register",
            "--vault-path", str(self.vault_dir)
        )
        self.assertEqual(res.returncode, 0, f"CLI stderr: {res.stderr}")
        self.assertTrue(out_draft.exists())

        content = out_draft.read_text(encoding="utf-8")
        self.assertIn("行业大模型与办公提效工具选型指引", content)
        self.assertIn("李工", content)
        self.assertIn("tool-guide", content)

    def test_new_duplicate_warning_emitted(self):
        """测试当标题与历史已写文章相似时输出防重警告框"""
        out_draft = self.work_dir / "dup-draft.md"
        # 故意传入与已写清单高度相似的标题
        res = run_cli(
            "new",
            "-t", "business",
            "-T", "多 Agent 跑不顺，缺的不是 Agent",
            "-o", str(out_draft),
            "--no-register",
            "--vault-path", str(self.vault_dir)
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("[防重提醒]", res.stdout)
        self.assertIn("已写清单", res.stdout)
        self.assertIn("相似度:", res.stdout)
        self.assertIn("多 Agent 跑不顺，缺的不是 Agent，是任务状态外置", res.stdout)

    def test_new_respects_no_register_flag(self):
        """测试 --no-register 参数确保不对中央台账进行写入"""
        initial_ledger = self.ledger_file.read_text(encoding="utf-8")
        out_draft = self.work_dir / "unregistered-draft.md"

        res = run_cli(
            "new",
            "-t", "business",
            "-T", "纯临时本地草稿不入台账",
            "-o", str(out_draft),
            "--no-register",
            "--vault-path", str(self.vault_dir)
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue(out_draft.exists())
        # 台账内容应毫发无损
        self.assertEqual(self.ledger_file.read_text(encoding="utf-8"), initial_ledger)

    def test_new_atomic_registration_and_pool_removal(self):
        """测试不带 --no-register 时自动将草稿登记入台账并核销选题池"""
        out_draft = self.work_dir / "registered-draft.md"
        target_title = "univer：可编程表格运行时能不能替 SED 台账取数"

        res = run_cli(
            "new",
            "-t", "tool",
            "-T", target_title,
            "-a", "王工",
            "-o", str(out_draft),
            "--vault-path", str(self.vault_dir)
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("✔ 已在中央防重台账中登记草稿", res.stdout)
        self.assertIn("已从选题池中移出命中条目", res.stdout)

        # 检查台账文件实际更新
        updated_ledger = self.ledger_file.read_text(encoding="utf-8")
        self.assertIn(f"| {target_title} | 本地草稿（王工） | **draft** 新建 |", updated_ledger)
        # 选题池中的 univer 条目已被剔除，但 open-webui 依然保留
        lines_under_pool = updated_ledger.split("## 选题池（待写）")[1]
        self.assertNotIn("univer：可编程表格运行时", lines_under_pool)
        self.assertIn("open-webui：企业内网可自部署", lines_under_pool)

    def test_new_snapshot_fallback_notice_when_vault_absent(self):
        """测试当工作台路径不可达时触发快照兜底提示"""
        out_draft = self.work_dir / "fallback-draft.md"
        non_existent_vault = self.work_dir / "non_existent_vault"

        res = run_cli(
            "new",
            "-t", "business",
            "-T", "离线环境生成测试草稿",
            "-o", str(out_draft),
            "--vault-path", str(non_existent_vault)
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue(out_draft.exists())
        self.assertIn("快照兜底", res.stdout)

    def test_new_force_flag_prevents_and_allows_overwrite(self):
        """测试已存在文件时必须通过 --force 方可覆盖"""
        out_draft = self.work_dir / "existing-draft.md"
        out_draft.write_text("原有内容", encoding="utf-8")

        # 无 --force 时报错退出 1
        res1 = run_cli(
            "new",
            "-t", "business",
            "-T", "覆盖测试",
            "-o", str(out_draft),
            "--no-register",
            "--vault-path", str(self.vault_dir)
        )
        self.assertEqual(res1.returncode, 1)
        self.assertIn("文件已存在", res1.stdout)
        self.assertEqual(out_draft.read_text(encoding="utf-8"), "原有内容")

        # 加 --force 成功覆盖
        res2 = run_cli(
            "new",
            "-t", "business",
            "-T", "覆盖测试",
            "-o", str(out_draft),
            "-f",
            "--no-register",
            "--vault-path", str(self.vault_dir)
        )
        self.assertEqual(res2.returncode, 0)
        self.assertIn("覆盖测试", out_draft.read_text(encoding="utf-8"))


class TestCliCheck(unittest.TestCase):
    """测试 pilot.py check 命令及 draft/publish 模式退出码"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_scaffolded_draft(self) -> Path:
        """从模板渲染一个初建草稿（包含未解析槽位且字数小于 1500）"""
        draft_p = self.work_dir / "scaffolded_draft.md"
        run_cli(
            "new",
            "-t", "business",
            "-T", "水厂进水异常应急处置实录",
            "-s", "water-abnormal",
            "-a", "赵工",
            "-o", str(draft_p),
            "--no-register"
        )
        return draft_p

    def test_check_draft_mode_exit_code_zero_on_incomplete_draft(self):
        """草稿模式下对未补齐字数与槽位的草稿容忍，退出码为 0"""
        draft_p = self._create_scaffolded_draft()

        # 默认模式为 draft
        res_default = run_cli("check", str(draft_p))
        self.assertEqual(res_default.returncode, 0, f"Check draft mode failed: {res_default.stdout}")
        self.assertIn("PASS", res_default.stdout)

        # 显式 --mode draft
        res_explicit = run_cli("check", str(draft_p), "--mode", "draft")
        self.assertEqual(res_explicit.returncode, 0)
        self.assertIn("PASS", res_explicit.stdout)

    def test_check_publish_mode_exit_code_one_on_incomplete_draft(self):
        """终审模式下对未补齐字数与槽位的草稿进行阻断，退出码为 1"""
        draft_p = self._create_scaffolded_draft()

        # 显式 --mode publish
        res_mode_pub = run_cli("check", str(draft_p), "--mode", "publish")
        self.assertEqual(res_mode_pub.returncode, 1)
        self.assertIn("REJECT", res_mode_pub.stdout)
        self.assertIn("P0 阻断项", res_mode_pub.stdout)

        # 快捷方式 --publish
        res_flag_pub = run_cli("check", str(draft_p), "--publish")
        self.assertEqual(res_flag_pub.returncode, 1)
        self.assertIn("REJECT", res_flag_pub.stdout)

    def test_check_directory_recursively(self):
        """测试对目录递归检查多个 markdown 文件"""
        sub_dir = self.work_dir / "articles"
        sub_dir.mkdir(parents=True, exist_ok=True)

        d1 = sub_dir / "draft1.md"
        d2 = sub_dir / "draft2.md"
        run_cli("new", "-t", "business", "-T", "业务实战稿件一", "-o", str(d1), "--no-register")
        run_cli("new", "-t", "tool", "-T", "工具避坑稿件二", "-o", str(d2), "--no-register")

        res = run_cli("check", str(sub_dir), "--mode", "draft")
        self.assertEqual(res.returncode, 0)
        self.assertIn("draft1.md", res.stdout)
        self.assertIn("draft2.md", res.stdout)

    def test_check_directory_quiet_mode_prints_summary_only(self):
        """--quiet 目录检查：每个文件只输出一行结论 + 一行汇总，不再刷完整报告"""
        sub_dir = self.work_dir / "articles_quiet"
        sub_dir.mkdir(parents=True, exist_ok=True)

        run_cli("new", "-t", "business", "-T", "业务实战稿件一", "-o", str(sub_dir / "draft1.md"), "--no-register")
        run_cli("new", "-t", "tool", "-T", "工具避坑稿件二", "-o", str(sub_dir / "draft2.md"), "--no-register")

        res = run_cli("check", str(sub_dir), "--quiet")
        self.assertEqual(res.returncode, 0)

        lines = [ln for ln in res.stdout.strip().splitlines() if ln.strip()]
        self.assertEqual(
            len(lines), 3,
            f"--quiet 应只输出 2 行结论 + 1 行汇总，实际输出:\n{res.stdout}"
        )
        self.assertTrue(lines[0].startswith("PASS  P0=0"), f"实际首行: {lines[0]}")
        self.assertTrue(lines[1].startswith("PASS  P0=0"), f"实际第二行: {lines[1]}")
        self.assertIn("汇总: 共检查 2 个文件，通过 2 个，未通过 0 个。", lines[2])
        self.assertNotIn("=== AI 领航团文章规范检查报告 ===", res.stdout)

    @unittest.skipUnless(sys.platform == "win32", "目录联结仅在 Windows 上存在")
    def test_check_directory_skips_junction_loop(self):
        """目录联结指回上层时不能被跟随，否则文件数会被放大数十倍"""
        sys.path.insert(0, str(BASE_DIR))
        from pilot import _iter_md_files

        root = self.work_dir / "junc_root"
        root.mkdir(parents=True, exist_ok=True)
        (root / "art-1.md").write_text("# 只有一篇\n\n正文\n", encoding="utf-8")

        link = root / "loop"
        made = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if made.returncode != 0:
            self.skipTest(f"当前环境无法创建目录联结: {made.stdout}{made.stderr}")
        try:
            # 用 islice 封顶：即使防护失效也不会把整个测试拖成十几分钟
            found = list(itertools.islice(_iter_md_files(root), 0, 50))
        finally:
            subprocess.run(["cmd", "/c", "rd", str(link)], capture_output=True)

        self.assertEqual(
            [p.name for p in found], ["art-1.md"],
            f"应只枚举到 art-1.md，实际枚举到 {len(found)} 个: {[str(p) for p in found[:5]]}"
        )

    def test_check_markdown_output_format(self):
        """测试 --md 导出 Markdown 格式审查报告"""
        draft_p = self._create_scaffolded_draft()
        res = run_cli("check", str(draft_p), "--md")
        self.assertEqual(res.returncode, 0)
        self.assertIn("# 文章评审报告：✅ 通过", res.stdout)
        self.assertIn("## 一、P0 阻断项（硬指标，发布前必须清零）", res.stdout)
        self.assertIn("## 二、P1 优化建议（文风去 AI 味与结构打磨）", res.stdout)

    def test_check_nonexistent_file_returns_error(self):
        """测试检查不存在的文件返回退出码 1"""
        res = run_cli("check", str(self.work_dir / "nonexistent.md"))
        self.assertEqual(res.returncode, 1)
        self.assertIn("目标文件或目录不存在", res.stdout)


class TestCliSyncVault(unittest.TestCase):
    """测试 pilot.py sync-vault 命令及 --overwrite / --diff 选项"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)
        self.mock_vault = self.work_dir / "mock_vault"
        self.mock_vault.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sync_vault_initial_creation(self):
        """首次同步在 mock vault 目录创建对应模板文件"""
        res = run_cli("sync-vault", "--vault-path", str(self.mock_vault))
        self.assertEqual(res.returncode, 0, f"sync-vault failed: {res.stdout}")
        self.assertIn("[首次创建]", res.stdout)

        biz_dst = self.mock_vault / "工作台" / "模板" / "AI领航团-业务实战型模板.md"
        tool_dst = self.mock_vault / "工作台" / "模板" / "AI领航团-工具避坑型模板.md"
        self.assertTrue(biz_dst.exists())
        self.assertTrue(tool_dst.exists())

    def test_sync_vault_avoids_overwriting_newer_destination(self):
        """工作台中就地修改的模板在不带 --overwrite 时受到防冲保护"""
        # 首次同步
        run_cli("sync-vault", "--vault-path", str(self.mock_vault))

        biz_dst = self.mock_vault / "工作台" / "模板" / "AI领航团-业务实战型模板.md"
        mutated_text = "# 就地修改的文章模板\n业务同事自定义了排查经验\n"
        biz_dst.write_text(mutated_text, encoding="utf-8")

        # 调整修改时间确保目标文件比源文件新
        src_mtime = (TEMPLATES_DIR / "template-business-agent.md").stat().st_mtime
        os.utime(biz_dst, (src_mtime + 50, src_mtime + 50))

        # 再次执行同步，不加 --overwrite
        res = run_cli("sync-vault", "--vault-path", str(self.mock_vault))
        self.assertEqual(res.returncode, 0)
        self.assertIn("[防冲保护]", res.stdout)

        # 核心断言：就地修改的文件未被冲掉
        self.assertEqual(biz_dst.read_text(encoding="utf-8"), mutated_text)

    def test_sync_vault_overwrite_flag(self):
        """添加 --overwrite 参数强制覆盖已就地修改的目标模板"""
        run_cli("sync-vault", "--vault-path", str(self.mock_vault))

        biz_dst = self.mock_vault / "工作台" / "模板" / "AI领航团-业务实战型模板.md"
        biz_dst.write_text("# 就地修改的内容", encoding="utf-8")
        src_mtime = (TEMPLATES_DIR / "template-business-agent.md").stat().st_mtime
        os.utime(biz_dst, (src_mtime + 50, src_mtime + 50))

        # 带 --overwrite 再次同步
        res = run_cli("sync-vault", "--vault-path", str(self.mock_vault), "--overwrite")
        self.assertEqual(res.returncode, 0)
        self.assertIn("[强制覆盖]", res.stdout)

        # 验证已被模板库内容覆盖
        orig_content = (TEMPLATES_DIR / "template-business-agent.md").read_text(encoding="utf-8")
        self.assertEqual(biz_dst.read_text(encoding="utf-8"), orig_content)

    def test_sync_vault_diff_flag(self):
        """添加 --diff 参数输出修改差异预览"""
        run_cli("sync-vault", "--vault-path", str(self.mock_vault))

        biz_dst = self.mock_vault / "工作台" / "模板" / "AI领航团-业务实战型模板.md"
        biz_dst.write_text("# 局部修改差异测试\n业务自定义段落\n", encoding="utf-8")
        src_mtime = (TEMPLATES_DIR / "template-business-agent.md").stat().st_mtime
        os.utime(biz_dst, (src_mtime + 50, src_mtime + 50))

        res = run_cli("sync-vault", "--vault-path", str(self.mock_vault), "--diff")
        self.assertEqual(res.returncode, 0)
        self.assertIn("差异预览", res.stdout)
        self.assertIn("---", res.stdout)
        self.assertIn("+++", res.stdout)


class TestCliPrompt(unittest.TestCase):
    """测试 pilot.py prompt 命令"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prompt_business_console_output(self):
        """测试查看业务实战型提示词"""
        res = run_cli("prompt", "-t", "business")
        self.assertEqual(res.returncode, 0)
        self.assertIn("AI 领航团文章起草系统提示词（业务实战型）", res.stdout)
        self.assertIn("结构与骨架硬约束", res.stdout)

    def test_prompt_tool_console_output(self):
        """测试查看工具避坑型提示词"""
        res = run_cli("prompt", "-t", "tool")
        self.assertEqual(res.returncode, 0)
        self.assertIn("AI 领航团文章起草系统提示词（工具避坑型）", res.stdout)

    def test_prompt_audit_console_output(self):
        """测试查看文章审核/终审提示词"""
        res = run_cli("prompt", "-t", "audit")
        self.assertEqual(res.returncode, 0)
        self.assertIn("AI 领航团文章终审评估提示词", res.stdout)

    def test_prompt_export_to_file(self):
        """测试将提示词导出至指定文件"""
        out_prompt = self.work_dir / "exported-prompt.md"
        res = run_cli("prompt", "-t", "business", "-o", str(out_prompt))
        self.assertEqual(res.returncode, 0)
        self.assertTrue(out_prompt.exists())
        self.assertIn("AI 领航团文章起草系统提示词（业务实战型）", out_prompt.read_text(encoding="utf-8"))
        self.assertIn("✔ 提示词已导出至:", res.stdout)

    def test_draft_prompts_are_single_round_and_self_contained(self):
        """起草提示词必须单轮自包含：不反问、不引用仓库模板文件、不要求自检

        历史回归：旧提示词要求「先用 3 个关键问题问清」「套用 templates/xxx.md」
        「检查表格数量是否 ≥ 2」，把模板文件路径当成可读附件贴给网页版大模型后，
        模型会在推理阶段反复猜模板内容并自我返工，表现为长时间「一直在思考」不出稿。
        """
        cases = {
            "business": "draft-business-agent.md",
            "tool": "draft-tool-guide.md",
        }
        for prompt_type, filename in cases.items():
            with self.subTest(prompt_type=prompt_type):
                text = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
                # 有输出契约，明确单轮直出
                self.assertIn("输出契约", text)
                self.assertIn("禁止反问", text)
                self.assertIn("禁止输出思考过程", text)
                # 不再把仓库内模板文件当成输入
                self.assertNotIn("templates/", text)
                self.assertNotIn("提问摸底", text)
                # 骨架已内联，章节硬约束仍在
                self.assertIn("结构与骨架硬约束", text)
                self.assertIn("> [!abstract] 一句话定位", text)
                self.assertIn("> [!info] 生产说明", text)

                # 通过 CLI 导出的内容与文件一致，保证同事复制到的是同一份
                res = run_cli("prompt", "-t", prompt_type)
                self.assertEqual(res.returncode, 0)
                self.assertIn("输出契约", res.stdout)

    def test_prompt_invalid_type(self):
        """测试未知提示词类型报错退出"""
        res = run_cli("prompt", "-t", "unknown_type")
        self.assertNotEqual(res.returncode, 0)


class TestCliList(unittest.TestCase):
    """测试 pilot.py list 命令"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_list_displays_templates_prompts_and_ledger_status(self):
        """测试 list 命令完整输出模板、提示词与台账状态"""
        res = run_cli("list")
        self.assertEqual(res.returncode, 0)
        self.assertIn("=== 可用文章模板 ===", res.stdout)
        self.assertIn("business", res.stdout)
        self.assertIn("tool", res.stdout)
        self.assertIn("=== 配套 AI 提示词 (prompts/) ===", res.stdout)
        self.assertIn("audit", res.stdout)
        self.assertIn("=== 中央防重台账状态 ===", res.stdout)

    def test_list_with_explicit_vault_path(self):
        """测试传入 --vault-path 时显示对应状态"""
        mock_vault = self.work_dir / "custom_vault"
        res = run_cli("list", "--vault-path", str(mock_vault))
        self.assertEqual(res.returncode, 0)
        self.assertIn("中央防重台账状态", res.stdout)


if __name__ == "__main__":
    unittest.main()
