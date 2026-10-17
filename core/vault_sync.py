# -*- coding: utf-8 -*-
"""
AI 领航团工作台防漂移同步器 (Vault Sync Drift Protection Adapter)
支持四级层叠路径探测、SHA256 内容哈希比较、Obsidian 就地修改修改时间 (mtime) 冲突保护与统一差异比对。
纯 Python 3 标准库实现，零外部依赖。
"""

import os
import sys
import json
import shutil
import hashlib
import difflib
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple


class SyncStatus(str, Enum):
    """同步结果状态码枚举"""
    CREATED = "CREATED"                              # 目标不存在，首次同步创建
    UP_TO_DATE = "UP_TO_DATE"                        # 目标存在且内容哈希一致，跳过无需变更
    UPDATED = "UPDATED"                              # 目标存在但源模板较新 (mtime <= src)，已同步更新
    CONFLICT_PROTECTED = "CONFLICT_PROTECTED"        # 目标存在且在 Obsidian 中就地修改 (mtime > src)，阻断覆盖保护
    OVERWRITTEN = "OVERWRITTEN"                      # 强制覆盖模式下覆盖就地修改
    SKIPPED_SOURCE_MISSING = "SKIPPED_SOURCE_MISSING"# 源模板文件缺失


def compute_sha256(file_path: Union[str, Path]) -> str:
    """计算指定文件的 SHA256 哈希字符串 (小写十六进制)"""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for hash calculation: {file_path}")
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def diff_files(src: Union[str, Path], dst: Union[str, Path]) -> str:
    """
    使用 difflib.unified_diff 生成源文件 (src) 与目标文件 (dst) 之间的统一差异文本 (unified diff)。
    src 为源文件 (fromfile)，dst 为目标文件 (tofile)。
    若两文件内容完全一致，返回空字符串。
    """
    src_p = Path(src)
    dst_p = Path(dst)

    src_lines = (
        src_p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if src_p.is_file()
        else []
    )
    dst_lines = (
        dst_p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if dst_p.is_file()
        else []
    )

    diff = difflib.unified_diff(
        src_lines,
        dst_lines,
        fromfile=str(src_p),
        tofile=str(dst_p),
    )
    return "".join(diff)


class _SyncDescriptor:
    """支持 VaultSyncAdapter.sync 既可作为实例方法也可作为类方法调用"""

    def __get__(self, instance, owner):
        if instance is None:
            def class_sync(
                templates_dir: Union[str, Path, None] = None,
                vault_path: Optional[Union[str, Path]] = None,
                overwrite: bool = False,
                show_diff: bool = False,
                mapping: Optional[Dict[str, str]] = None,
            ) -> dict:
                adapter = owner(vault_path=vault_path)
                return adapter._sync_impl(
                    templates_dir=templates_dir,
                    vault_path=vault_path,
                    overwrite=overwrite,
                    show_diff=show_diff,
                    mapping=mapping,
                )
            return class_sync

        def bound_sync(
            templates_dir: Union[str, Path, None] = None,
            vault_path: Optional[Union[str, Path]] = None,
            overwrite: bool = False,
            show_diff: bool = False,
            mapping: Optional[Dict[str, str]] = None,
        ) -> dict:
            return instance._sync_impl(
                templates_dir=templates_dir,
                vault_path=vault_path,
                overwrite=overwrite,
                show_diff=show_diff,
                mapping=mapping,
            )
        return bound_sync


class VaultSyncAdapter:
    """
    Obsidian 工作台防漂移同步适配器
    实现 4 级层叠工作台路径探测、内容哈希对比与就地修改冲突保护。
    """

    # 4 级层叠默认配置
    DEFAULT_VAULT_PATH = Path(r"D:\obsidian_work\cangku\paper_work")
    ENV_VAR_NAME = "PILOT_VAULT_PATH"
    CONFIG_FILE_NAME = ".pilot.config.json"

    # 默认模板与工作台目标路径映射表
    DEFAULT_TEMPLATE_MAPPING: Dict[str, str] = {
        "template-business-agent.md": "工作台/模板/AI领航团-业务实战型模板.md",
        "template-tool-guide.md": "工作台/模板/AI领航团-工具避坑型模板.md",
    }

    # 静态工具方法暴露
    diff_files = staticmethod(diff_files)
    compute_sha256 = staticmethod(compute_sha256)

    def __init__(
        self,
        vault_path: Optional[Union[str, Path]] = None,
        project_root: Optional[Union[str, Path]] = None,
        mapping: Optional[Dict[str, str]] = None,
    ):
        """
        初始化同步适配器
        :param vault_path: 显式指定的 Obsidian 工作台路径 (Tier 1)
        :param project_root: 项目根目录 (用于定位 .pilot.config.json 及默认 templates/)
        :param mapping: 自定义模板映射表 (源文件名 -> 工作台相对路径)
        """
        self.explicit_path = Path(vault_path) if vault_path else None
        self.project_root = Path(project_root).resolve() if project_root else None
        self.mapping = dict(mapping) if mapping is not None else dict(self.DEFAULT_TEMPLATE_MAPPING)

    @classmethod
    def resolve_vault_path_with_tier(
        cls,
        explicit_path: Optional[Union[str, Path]] = None,
        project_root: Optional[Union[str, Path]] = None,
    ) -> Tuple[Path, str]:
        """
        4 级层叠工作台路径探测，并返回 (解析出的 Path, 命中层级 tier_name)
        Tier 1: explicit_path 参数
        Tier 2: 环境变量 PILOT_VAULT_PATH
        Tier 3: 本地配置文件 .pilot.config.json
        Tier 4: 默认路径 D:\\obsidian_work\\cangku\\paper_work
        """
        # Tier 1: explicit_path
        if explicit_path is not None:
            explicit_str = str(explicit_path).strip()
            if explicit_str:
                return Path(explicit_str).resolve(), "explicit"

        # Tier 2: 环境变量
        env_val = os.environ.get(cls.ENV_VAR_NAME)
        if env_val is not None and env_val.strip():
            return Path(env_val.strip()).resolve(), "env"

        # Tier 3: 配置文件 .pilot.config.json
        candidate_dirs: List[Path] = []
        if project_root is not None:
            candidate_dirs.append(Path(project_root).resolve())
        # 当前模块的上级目录 (即代码库根目录)
        candidate_dirs.append(Path(__file__).resolve().parent.parent)
        # 当前工作目录
        candidate_dirs.append(Path.cwd().resolve())

        for c_dir in candidate_dirs:
            config_file = c_dir / cls.CONFIG_FILE_NAME
            if config_file.is_file():
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        val = data.get("vault_path") or data.get("vault") or data.get("vaultPath")
                        if val and str(val).strip():
                            return Path(str(val).strip()).resolve(), "config"
                except Exception:
                    pass

        # Tier 4: 默认路径
        return cls.DEFAULT_VAULT_PATH, "default"

    @classmethod
    def resolve_vault_path(
        cls,
        explicit_path: Optional[Union[str, Path]] = None,
        project_root: Optional[Union[str, Path]] = None,
    ) -> Path:
        """4 级层叠工作台路径探测，返回最终解析得到的 Path"""
        path, _ = cls.resolve_vault_path_with_tier(explicit_path, project_root)
        return path

    @classmethod
    def persist_vault_path(
        cls,
        vault_path: Union[str, Path],
        project_root: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        将 vault_path 持久化存储至项目根目录的 .pilot.config.json 中
        :return: 配置文件的绝对路径
        """
        target_dir = Path(project_root).resolve() if project_root else Path(__file__).resolve().parent.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        config_path = target_dir / cls.CONFIG_FILE_NAME

        config_data = {}
        if config_path.is_file():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    config_data = data
            except Exception:
                config_data = {}

        config_data["vault_path"] = str(vault_path)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        return config_path

    def _sync_impl(
        self,
        templates_dir: Union[str, Path, None] = None,
        vault_path: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
        show_diff: bool = False,
        mapping: Optional[Dict[str, str]] = None,
    ) -> dict:
        """内部实际执行同步操作的实现"""
        resolved_vault = self.resolve_vault_path(
            explicit_path=vault_path or self.explicit_path,
            project_root=self.project_root,
        )

        # 确定模板源目录
        if templates_dir is None:
            if self.project_root and (self.project_root / "templates").is_dir():
                templates_path = self.project_root / "templates"
            else:
                templates_path = Path(__file__).resolve().parent.parent / "templates"
        else:
            templates_path = Path(templates_dir).resolve()
            if (templates_path / "templates").is_dir() and not (templates_path / "template-business-agent.md").exists():
                templates_path = templates_path / "templates"

        if not templates_path.exists():
            raise FileNotFoundError(f"Templates directory not found: {templates_path}")

        current_mapping = mapping if mapping is not None else self.mapping
        file_records: List[Dict[str, Any]] = []

        for src_name, rel_dst in current_mapping.items():
            # 候选源文件路径解析
            src_file = templates_path / src_name
            if not src_file.exists():
                alt_name = Path(src_name).name
                if (templates_path / alt_name).exists():
                    src_file = templates_path / alt_name

            dst_file = resolved_vault / rel_dst

            if not src_file.exists():
                record = {
                    "src": str(src_file),
                    "dst": str(dst_file),
                    "relative_dst": str(rel_dst),
                    "status": SyncStatus.SKIPPED_SOURCE_MISSING.value,
                    "source_sha256": None,
                    "dest_sha256": None,
                    "source_mtime": None,
                    "dest_mtime": None,
                    "diff": "",
                }
                file_records.append(record)
                continue

            src_sha = compute_sha256(src_file)
            src_mtime = src_file.stat().st_mtime

            # Case 1: 目标文件不存在 -> 首次创建
            if not dst_file.exists():
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                dst_mtime = dst_file.stat().st_mtime
                record = {
                    "src": str(src_file),
                    "dst": str(dst_file),
                    "relative_dst": str(rel_dst),
                    "status": SyncStatus.CREATED.value,
                    "source_sha256": src_sha,
                    "dest_sha256": src_sha,
                    "source_mtime": src_mtime,
                    "dest_mtime": dst_mtime,
                    "diff": "",
                }
                file_records.append(record)
                continue

            # Case 2: 目标文件已存在 -> 比较内容哈希
            dst_sha = compute_sha256(dst_file)
            dst_mtime = dst_file.stat().st_mtime

            if src_sha == dst_sha:
                # 哈希完全一致，跳过无需变更
                record = {
                    "src": str(src_file),
                    "dst": str(dst_file),
                    "relative_dst": str(rel_dst),
                    "status": SyncStatus.UP_TO_DATE.value,
                    "source_sha256": src_sha,
                    "dest_sha256": dst_sha,
                    "source_mtime": src_mtime,
                    "dest_mtime": dst_mtime,
                    "diff": "",
                }
                file_records.append(record)
                continue

            # 哈希不同，说明内容有差异
            file_diff = diff_files(src_file, dst_file)

            if dst_mtime > src_mtime:
                # 目标文件在 Obsidian 工作台中被就地修改过
                if not overwrite:
                    # 冲突保护：阻断覆盖
                    record = {
                        "src": str(src_file),
                        "dst": str(dst_file),
                        "relative_dst": str(rel_dst),
                        "status": SyncStatus.CONFLICT_PROTECTED.value,
                        "source_sha256": src_sha,
                        "dest_sha256": dst_sha,
                        "source_mtime": src_mtime,
                        "dest_mtime": dst_mtime,
                        "diff": file_diff,
                    }
                else:
                    # 强制覆盖
                    shutil.copy2(src_file, dst_file)
                    new_dst_mtime = dst_file.stat().st_mtime
                    record = {
                        "src": str(src_file),
                        "dst": str(dst_file),
                        "relative_dst": str(rel_dst),
                        "status": SyncStatus.OVERWRITTEN.value,
                        "source_sha256": src_sha,
                        "dest_sha256": src_sha,
                        "source_mtime": src_mtime,
                        "dest_mtime": new_dst_mtime,
                        "diff": file_diff if show_diff else "",
                    }
            else:
                # 目标时间戳 <= 源文件时间戳：代码库模板较新，正常同步更新
                shutil.copy2(src_file, dst_file)
                new_dst_mtime = dst_file.stat().st_mtime
                record = {
                    "src": str(src_file),
                    "dst": str(dst_file),
                    "relative_dst": str(rel_dst),
                    "status": SyncStatus.UPDATED.value,
                    "source_sha256": src_sha,
                    "dest_sha256": src_sha,
                    "source_mtime": src_mtime,
                    "dest_mtime": new_dst_mtime,
                    "diff": file_diff if show_diff else "",
                }

            file_records.append(record)

        # 汇总统计
        created_count = sum(1 for r in file_records if r["status"] == SyncStatus.CREATED.value)
        up_to_date_count = sum(1 for r in file_records if r["status"] == SyncStatus.UP_TO_DATE.value)
        updated_count = sum(1 for r in file_records if r["status"] == SyncStatus.UPDATED.value)
        conflict_count = sum(1 for r in file_records if r["status"] == SyncStatus.CONFLICT_PROTECTED.value)
        overwritten_count = sum(1 for r in file_records if r["status"] == SyncStatus.OVERWRITTEN.value)
        missing_count = sum(1 for r in file_records if r["status"] == SyncStatus.SKIPPED_SOURCE_MISSING.value)

        summary = {
            "created": created_count,
            "up_to_date": up_to_date_count,
            "updated": updated_count,
            "conflict_protected": conflict_count,
            "overwritten": overwritten_count,
            "missing": missing_count,
            "total": len(file_records),
        }

        diffs = [r["diff"] for r in file_records if r.get("diff")]

        result_dict: Dict[str, Any] = {
            "vault_path": str(resolved_vault),
            "created": created_count,
            "up_to_date": up_to_date_count,
            "updated": updated_count,
            "conflict_protected": conflict_count,
            "overwritten": overwritten_count,
            "missing": missing_count,
            "total": len(file_records),
            "success": conflict_count == 0 and missing_count == 0,
            "summary": summary,
            "files": file_records,
            "items": file_records,
            "results": {Path(r["src"]).name: r for r in file_records},
            "diffs": diffs,
        }

        for r in file_records:
            src_name = Path(r["src"]).name
            dst_name = Path(r["dst"]).name
            result_dict[src_name] = r
            result_dict[dst_name] = r
            if r.get("relative_dst"):
                result_dict[r["relative_dst"]] = r

        return result_dict

    # 绑定 sync 方法描述符
    sync = _SyncDescriptor()

    @classmethod
    def format_summary(cls, sync_result: Dict[str, Any]) -> str:
        """格式化输出同步结果摘要"""
        lines = [
            "=== Obsidian 工作台模板同步报告 ===",
            f"工作台路径: {sync_result.get('vault_path', '')}",
            "",
        ]
        files = sync_result.get("files", [])
        for f in files:
            src_name = Path(f["src"]).name
            rel_dst = f.get("relative_dst", f["dst"])
            status = f["status"]
            if status == SyncStatus.CREATED.value:
                lines.append(f"✔ [首次创建] {src_name} -> {rel_dst}")
            elif status == SyncStatus.UP_TO_DATE.value:
                lines.append(f"✔ [已是最新] {src_name} == {rel_dst}")
            elif status == SyncStatus.UPDATED.value:
                lines.append(f"🔄 [更新同步] {src_name} -> {rel_dst}")
            elif status == SyncStatus.CONFLICT_PROTECTED.value:
                lines.append(f"⚠️ [防冲保护] {src_name} -> {rel_dst} (工作台已就地修改，已拦截覆盖)")
            elif status == SyncStatus.OVERWRITTEN.value:
                lines.append(f"❗ [强制覆盖] {src_name} -> {rel_dst}")
            elif status == SyncStatus.SKIPPED_SOURCE_MISSING.value:
                lines.append(f"❌ [源文件缺失] {src_name}")

            if f.get("diff"):
                lines.append(f"--- 差异预览 ({src_name}) ---")
                lines.append(f["diff"].rstrip())
                lines.append("----------------------------")

        summary = sync_result.get("summary", {})
        lines.append("")
        lines.append(
            f"汇总: 首次创建 {summary.get('created', 0)}, "
            f"已是最新 {summary.get('up_to_date', 0)}, "
            f"更新同步 {summary.get('updated', 0)}, "
            f"防冲保护 {summary.get('conflict_protected', 0)}, "
            f"强制覆盖 {summary.get('overwritten', 0)}"
        )
        return "\n".join(lines)


# 模块级便捷同步函数
def sync(
    templates_dir: Union[str, Path, None] = None,
    vault_path: Optional[Union[str, Path]] = None,
    overwrite: bool = False,
    show_diff: bool = False,
    mapping: Optional[Dict[str, str]] = None,
) -> dict:
    """模块级直接调用同步"""
    return VaultSyncAdapter.sync(
        templates_dir=templates_dir,
        vault_path=vault_path,
        overwrite=overwrite,
        show_diff=show_diff,
        mapping=mapping,
    )
