# -*- coding: utf-8 -*-
"""
AI 领航团工作台防漂移同步器单元测试 (tests/test_vault_sync.py)
验证 4 级层叠工作台路径探测、首次创建、哈希匹配跳过、就地修改防冲保护、强制覆盖与 unified diff 生成
"""

import os
import sys
import json
import time
import shutil
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.vault_sync import VaultSyncAdapter, SyncStatus, diff_files, compute_sha256


class TestVaultPathDiscovery(unittest.TestCase):
    """测试 4 级层叠工作台路径探测机制"""

    def setUp(self):
        self._orig_env = os.environ.copy()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)
        self.temp_dir.cleanup()

    def test_tier1_explicit_path_precedence(self):
        """Tier 1: 显式参数具有最高优先级，覆盖环境变量、配置文件及默认值"""
        explicit = self.project_root / "explicit_vault"
        env_val = self.project_root / "env_vault"
        config_val = self.project_root / "config_vault"

        # 设置 Tier 2 环境变量
        os.environ[VaultSyncAdapter.ENV_VAR_NAME] = str(env_val)
        # 设置 Tier 3 配置文件
        VaultSyncAdapter.persist_vault_path(config_val, project_root=self.project_root)

        resolved, tier = VaultSyncAdapter.resolve_vault_path_with_tier(
            explicit_path=explicit,
            project_root=self.project_root,
        )
        self.assertEqual(resolved, explicit.resolve())
        self.assertEqual(tier, "explicit")

        # 直接调用 resolve_vault_path
        self.assertEqual(
            VaultSyncAdapter.resolve_vault_path(explicit_path=explicit, project_root=self.project_root),
            explicit.resolve(),
        )

    def test_tier2_env_var_precedence(self):
        """Tier 2: 无显式参数时，环境变量优先于配置文件与默认值"""
        env_val = self.project_root / "env_vault"
        config_val = self.project_root / "config_vault"

        os.environ[VaultSyncAdapter.ENV_VAR_NAME] = str(env_val)
        VaultSyncAdapter.persist_vault_path(config_val, project_root=self.project_root)

        resolved, tier = VaultSyncAdapter.resolve_vault_path_with_tier(
            explicit_path=None,
            project_root=self.project_root,
        )
        self.assertEqual(resolved, env_val.resolve())
        self.assertEqual(tier, "env")

    def test_tier3_config_file_precedence(self):
        """Tier 3: 无显式参数且无环境变量时，.pilot.config.json 优先于默认值"""
        config_val = self.project_root / "config_vault"
        if VaultSyncAdapter.ENV_VAR_NAME in os.environ:
            del os.environ[VaultSyncAdapter.ENV_VAR_NAME]

        VaultSyncAdapter.persist_vault_path(config_val, project_root=self.project_root)

        resolved, tier = VaultSyncAdapter.resolve_vault_path_with_tier(
            explicit_path=None,
            project_root=self.project_root,
        )
        self.assertEqual(resolved, config_val.resolve())
        self.assertEqual(tier, "config")

    def test_tier3_config_file_alternative_keys(self):
        """Tier 3: 支持 .pilot.config.json 中的不同键名 (vault, vaultPath)"""
        if VaultSyncAdapter.ENV_VAR_NAME in os.environ:
            del os.environ[VaultSyncAdapter.ENV_VAR_NAME]

        config_file = self.project_root / VaultSyncAdapter.CONFIG_FILE_NAME
        config_file.write_text(json.dumps({"vault": str(self.project_root / "alt_vault")}), encoding="utf-8")

        resolved, tier = VaultSyncAdapter.resolve_vault_path_with_tier(
            explicit_path=None,
            project_root=self.project_root,
        )
        self.assertEqual(resolved, (self.project_root / "alt_vault").resolve())
        self.assertEqual(tier, "config")

    def test_tier4_default_path_fallback(self):
        """Tier 4: 无任何配置时回退至系统默认 D:\\obsidian_work\\cangku\\paper_work"""
        if VaultSyncAdapter.ENV_VAR_NAME in os.environ:
            del os.environ[VaultSyncAdapter.ENV_VAR_NAME]

        # 确保 project_root 下无配置文件
        config_file = self.project_root / VaultSyncAdapter.CONFIG_FILE_NAME
        if config_file.exists():
            config_file.unlink()

        # 使用一个干净的临时空目录作为 project_root
        empty_temp = tempfile.TemporaryDirectory()
        try:
            resolved, tier = VaultSyncAdapter.resolve_vault_path_with_tier(
                explicit_path=None,
                project_root=empty_temp.name,
            )
            # 无论在什么操作系统，默认路径必须与常量一致
            self.assertEqual(resolved, VaultSyncAdapter.DEFAULT_VAULT_PATH)
            self.assertEqual(tier, "default")
        finally:
            empty_temp.cleanup()

    def test_persist_vault_path(self):
        """测试将工作台路径写入 .pilot.config.json"""
        target_path = self.project_root / "saved_vault"
        saved_file = VaultSyncAdapter.persist_vault_path(target_path, project_root=self.project_root)

        self.assertTrue(saved_file.is_file())
        with open(saved_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("vault_path"), str(target_path))


class TestVaultSyncDriftProtection(unittest.TestCase):
    """测试工作台防漂移同步核心逻辑：创建、哈希匹配跳过、防冲保护、强制覆盖、较新更新"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.templates_dir = self.base_path / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.vault_dir = self.base_path / "mock_vault"
        self.vault_dir.mkdir(parents=True, exist_ok=True)

        # 创建两份基准测试模板
        self.biz_template = self.templates_dir / "template-business-agent.md"
        self.biz_template.write_text("# 业务实战型模板基准内容 v1\n- 步骤1\n- 步骤2\n", encoding="utf-8")

        self.tool_template = self.templates_dir / "template-tool-guide.md"
        self.tool_template.write_text("# 工具避坑型模板基准内容 v1\n| 工具 | 现象 |\n", encoding="utf-8")

        # 目标文件在 vault 中的预期相对路径
        self.biz_dst = self.vault_dir / "工作台" / "模板" / "AI领航团-业务实战型模板.md"
        self.tool_dst = self.vault_dir / "工作台" / "模板" / "AI领航团-工具避坑型模板.md"

        self.adapter = VaultSyncAdapter(vault_path=self.vault_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_first_time_copy_created(self):
        """测试目标文件不存在时的首次创建 (CREATED)"""
        self.assertFalse(self.biz_dst.exists())
        self.assertFalse(self.tool_dst.exists())

        result = self.adapter.sync(self.templates_dir, vault_path=self.vault_dir)

        self.assertTrue(result["success"])
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["up_to_date"], 0)
        self.assertEqual(result["conflict_protected"], 0)

        # 验证文件落盘且内容一致
        self.assertTrue(self.biz_dst.is_file())
        self.assertTrue(self.tool_dst.is_file())
        self.assertEqual(self.biz_dst.read_text(encoding="utf-8"), self.biz_template.read_text(encoding="utf-8"))
        self.assertEqual(self.tool_dst.read_text(encoding="utf-8"), self.tool_template.read_text(encoding="utf-8"))

        self.assertEqual(result["template-business-agent.md"]["status"], SyncStatus.CREATED.value)
        self.assertEqual(result["template-tool-guide.md"]["status"], SyncStatus.CREATED.value)

    def test_matching_hash_skip_up_to_date(self):
        """测试目标文件存在且 SHA256 哈希完全一致时的跳过 (UP_TO_DATE)"""
        # 先执行首次同步
        self.adapter.sync(self.templates_dir, vault_path=self.vault_dir)

        # 再次执行同步，应全部为 UP_TO_DATE
        result2 = self.adapter.sync(self.templates_dir, vault_path=self.vault_dir)

        self.assertTrue(result2["success"])
        self.assertEqual(result2["created"], 0)
        self.assertEqual(result2["up_to_date"], 2)
        self.assertEqual(result2["conflict_protected"], 0)
        self.assertEqual(result2["updated"], 0)

        self.assertEqual(result2["template-business-agent.md"]["status"], SyncStatus.UP_TO_DATE.value)
        self.assertEqual(result2["template-tool-guide.md"]["status"], SyncStatus.UP_TO_DATE.value)

    def test_conflict_protection_when_destination_newer(self):
        """测试工作台目标文件被就地修改 (mtime > src) 时阻断覆盖 (CONFLICT_PROTECTED)"""
        # 首次同步
        self.adapter.sync(self.templates_dir, vault_path=self.vault_dir)

        # 模拟用户在 Obsidian 工作台中对业务模板进行就地补充修改
        time.sleep(0.01)
        obsidian_custom_content = "# 业务实战型模板基准内容 v1\n- 步骤1\n- 步骤2\n\n> 业务同事就地补充的排查经验\n"
        self.biz_dst.write_text(obsidian_custom_content, encoding="utf-8")

        # 显式确保 destination mtime 大于 source mtime
        src_mtime = self.biz_template.stat().st_mtime
        os.utime(self.biz_dst, (src_mtime + 50, src_mtime + 50))

        # 执行默认同步 (overwrite=False)
        result = self.adapter.sync(self.templates_dir, vault_path=self.vault_dir, overwrite=False)

        # 验证防冲保护触发
        self.assertEqual(result["conflict_protected"], 1)
        self.assertEqual(result["up_to_date"], 1)  # 工具模板未被修改，保持 UP_TO_DATE
        self.assertFalse(result["success"])  # 存在冲突保护项时视为未完全覆盖/需人工决策

        biz_record = result["template-business-agent.md"]
        self.assertEqual(biz_record["status"], SyncStatus.CONFLICT_PROTECTED.value)

        # 核心保证：目标文件的就地修改绝对没有被静默冲掉！
        self.assertEqual(self.biz_dst.read_text(encoding="utf-8"), obsidian_custom_content)

        # 附带 diff 预览信息
        self.assertTrue(len(biz_record["diff"]) > 0)
        self.assertIn("+> 业务同事就地补充的排查经验", biz_record["diff"])

    def test_force_overwrite_when_destination_newer(self):
        """测试当指定 overwrite=True 时，强制覆盖工作台中的就地修改 (OVERWRITTEN)"""
        # 首次同步
        self.adapter.sync(self.templates_dir, vault_path=self.vault_dir)

        # 目标文件就地修改且 mtime 更新
        obsidian_custom_content = "# 修改过的旧草稿\n"
        self.biz_dst.write_text(obsidian_custom_content, encoding="utf-8")
        src_mtime = self.biz_template.stat().st_mtime
        os.utime(self.biz_dst, (src_mtime + 50, src_mtime + 50))

        # 执行强制覆盖同步 (overwrite=True)
        result = self.adapter.sync(self.templates_dir, vault_path=self.vault_dir, overwrite=True)

        self.assertEqual(result["overwritten"], 1)
        self.assertEqual(result["conflict_protected"], 0)
        self.assertTrue(result["success"])

        biz_record = result["template-business-agent.md"]
        self.assertEqual(biz_record["status"], SyncStatus.OVERWRITTEN.value)

        # 目标文件内容已被代码库标准模板强制覆写
        self.assertEqual(self.biz_dst.read_text(encoding="utf-8"), self.biz_template.read_text(encoding="utf-8"))

    def test_updated_when_source_newer(self):
        """测试当代码库源模板更新 (dst mtime <= src mtime) 时的正常更新 (UPDATED)"""
        # 首次同步
        self.adapter.sync(self.templates_dir, vault_path=self.vault_dir)

        # 目标文件保留旧内容，并将其修改时间设为过去
        old_content = "# 旧版本内容\n"
        self.biz_dst.write_text(old_content, encoding="utf-8")
        src_mtime = self.biz_template.stat().st_mtime
        os.utime(self.biz_dst, (src_mtime - 100, src_mtime - 100))

        # 执行同步 (overwrite=False)
        result = self.adapter.sync(self.templates_dir, vault_path=self.vault_dir, overwrite=False)

        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["conflict_protected"], 0)
        self.assertTrue(result["success"])

        biz_record = result["template-business-agent.md"]
        self.assertEqual(biz_record["status"], SyncStatus.UPDATED.value)

        # 目标文件已被更新为源模板内容
        self.assertEqual(self.biz_dst.read_text(encoding="utf-8"), self.biz_template.read_text(encoding="utf-8"))


class TestDiffAndUtilities(unittest.TestCase):
    """测试 unified diff 生成辅助函数及摘要报告格式化"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_diff_files_identical(self):
        """内容相同的两文件 diff 为空字符串"""
        f1 = self.base_path / "f1.md"
        f2 = self.base_path / "f2.md"
        f1.write_text("Hello\nWorld\n", encoding="utf-8")
        f2.write_text("Hello\nWorld\n", encoding="utf-8")

        diff = diff_files(f1, f2)
        self.assertEqual(diff, "")

    def test_diff_files_different(self):
        """内容不同的文件生成标准的 unified diff 文本"""
        src = self.base_path / "src.md"
        dst = self.base_path / "dst.md"
        src.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
        dst.write_text("line 1\nline 2 modified\nline 3\nline 4\n", encoding="utf-8")

        diff = diff_files(src, dst)
        self.assertIn("---", diff)
        self.assertIn("+++", diff)
        self.assertIn("@@", diff)
        self.assertIn("-line 2", diff)
        self.assertIn("+line 2 modified", diff)
        self.assertIn("+line 4", diff)

    def test_compute_sha256(self):
        """测试 SHA256 哈希计算函数"""
        f = self.base_path / "hash_test.txt"
        f.write_text("test content", encoding="utf-8")
        h = compute_sha256(f)
        # "test content" 的 sha256 应该是已知固定值
        import hashlib
        expected = hashlib.sha256(b"test content").hexdigest()
        self.assertEqual(h, expected)

    def test_sync_show_diff_flag(self):
        """测试 show_diff=True 标志在同步结果中填充 diff"""
        templates_dir = self.base_path / "tmpl"
        templates_dir.mkdir()
        vault_dir = self.base_path / "vault"
        vault_dir.mkdir()

        src = templates_dir / "template-business-agent.md"
        src.write_text("base v1\n", encoding="utf-8")

        adapter = VaultSyncAdapter(
            vault_path=vault_dir,
            mapping={"template-business-agent.md": "target.md"},
        )
        # 首次同步
        adapter.sync(templates_dir, show_diff=True)

        # 修改源文件使 mtime 较新并形成差异
        time.sleep(0.01)
        src.write_text("base v2 updated\n", encoding="utf-8")

        res = adapter.sync(templates_dir, show_diff=True)
        self.assertEqual(res["updated"], 1)
        self.assertTrue(len(res["target.md"]["diff"]) > 0)
        self.assertIn("---", res["target.md"]["diff"])

    def test_format_summary(self):
        """测试 format_summary 输出正常可读报告文本"""
        mock_result = {
            "vault_path": "/mock/vault",
            "created": 1,
            "up_to_date": 1,
            "updated": 0,
            "conflict_protected": 0,
            "overwritten": 0,
            "files": [
                {"src": "t1.md", "dst": "d1.md", "relative_dst": "工作台/d1.md", "status": "CREATED", "diff": ""},
                {"src": "t2.md", "dst": "d2.md", "relative_dst": "工作台/d2.md", "status": "UP_TO_DATE", "diff": ""},
            ],
            "summary": {"created": 1, "up_to_date": 1, "updated": 0, "conflict_protected": 0, "overwritten": 0},
        }
        text = VaultSyncAdapter.format_summary(mock_result)
        self.assertIn("Obsidian 工作台模板同步报告", text)
        self.assertIn("[首次创建]", text)
        self.assertIn("[已是最新]", text)

    def test_class_sync_and_module_sync(self):
        """测试类方法调用与模块级 sync 函数调用"""
        from core.vault_sync import sync as module_sync

        templates_dir = self.base_path / "tmpl2"
        templates_dir.mkdir()
        vault_dir = self.base_path / "vault2"
        vault_dir.mkdir()

        (templates_dir / "template-business-agent.md").write_text("biz", encoding="utf-8")
        (templates_dir / "template-tool-guide.md").write_text("tool", encoding="utf-8")

        # 1. 类级别调用
        res_class = VaultSyncAdapter.sync(templates_dir, vault_path=vault_dir)
        self.assertEqual(res_class["created"], 2)

        # 2. 模块级调用
        res_module = module_sync(templates_dir, vault_path=vault_dir)
        self.assertEqual(res_module["up_to_date"], 2)

    def test_missing_templates_dir_raises_filenotfound(self):
        """测试模板目录不存在时抛出 FileNotFoundError"""
        with self.assertRaises(FileNotFoundError):
            VaultSyncAdapter.sync(self.base_path / "non_existent_dir", vault_path=self.base_path)

    def test_missing_source_file_marked_skipped(self):
        """测试映射中的源模板缺失时标记 SKIPPED_SOURCE_MISSING"""
        empty_tmpl = self.base_path / "empty_tmpl"
        empty_tmpl.mkdir()
        vault_dir = self.base_path / "vault3"

        res = VaultSyncAdapter.sync(
            empty_tmpl,
            vault_path=vault_dir,
            mapping={"missing-file.md": "target.md"},
        )
        self.assertEqual(res["missing"], 1)
        self.assertEqual(res["target.md"]["status"], SyncStatus.SKIPPED_SOURCE_MISSING.value)

    def test_real_repo_templates_sync(self):
        """测试使用仓库内真实 templates 目录同步到模拟工作台"""
        repo_templates = BASE_DIR / "templates"
        self.assertTrue(repo_templates.is_dir())
        mock_vault = self.base_path / "real_mock_vault"

        res = VaultSyncAdapter.sync(repo_templates, vault_path=mock_vault)
        self.assertEqual(res["created"], 2)
        self.assertTrue((mock_vault / "工作台" / "模板" / "AI领航团-业务实战型模板.md").exists())
        self.assertTrue((mock_vault / "工作台" / "模板" / "AI领航团-工具避坑型模板.md").exists())


if __name__ == "__main__":
    unittest.main()
