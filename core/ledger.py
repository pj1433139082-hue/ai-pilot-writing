# -*- coding: utf-8 -*-
"""
AI 领航团文章台账适配器 (LedgerAdapter)
提供防重查重、草稿原子化登记与离线快照兜底功能 (纯 Python 3 标准库)
"""

import os
import re
import json
import tempfile
import datetime
from pathlib import Path
from typing import List, Dict, Optional, Union, Any, Tuple

# 默认中央防重台账与快照路径
DEFAULT_LEDGER_PATH = Path(r"D:\obsidian_work\cangku\paper_work\工作台\AI领航团文章\已写清单.md")
DEFAULT_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "ledger-snapshot.json"


def cjk_bigrams(text: str) -> set[str]:
    """
    提取文本中的 CJK 字符二元组与英数字单词及二元子串。
    采用纯标准库正则，对中英文混合标题具备强容错性（忽略多余空格、标点及大小写）。
    """
    if not text:
        return set()
    # 匹配英数字连续块或非 ASCII Unicode 块 (CJK 等)
    blocks = re.findall(r"[a-zA-Z0-9]+|[^\W\d_a-zA-Z]+", text.lower())
    tokens = set()
    for b in blocks:
        if re.match(r"^[a-z0-9]+$", b):
            tokens.add(b)
            if len(b) > 2:
                for i in range(len(b) - 1):
                    tokens.add(b[i : i + 2])
        else:
            if len(b) == 1:
                tokens.add(b)
            else:
                for i in range(len(b) - 1):
                    tokens.add(b[i : i + 2])
    return tokens


def cjk_bigram_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的 CJK bigram Jaccard 相似度 (0.0 ~ 1.0)。
    若两文本完全相同（忽略首尾空格和大小写），直接返回 1.0。
    """
    s1 = text1.strip().lower()
    s2 = text2.strip().lower()
    if s1 == s2 and s1:
        return 1.0

    toks1 = cjk_bigrams(s1)
    toks2 = cjk_bigrams(s2)
    union = toks1 | toks2
    if not union:
        return 1.0 if s1 == s2 else 0.0
    return len(toks1 & toks2) / len(union)


def is_matching_topic(title: str, pool_title: str, threshold: float = 0.7) -> bool:
    """
    判断草稿标题是否命中了选题池中的某条记录。
    判据：相似度 >= threshold 或者满足非平凡子串包含。
    """
    sim = cjk_bigram_similarity(title, pool_title)
    if sim >= threshold:
        return True

    # 规范化去除标点与空格进行子串检查
    t_clean = re.sub(r"[^\w]+", "", title.lower()).replace("_", "")
    p_clean = re.sub(r"[^\w]+", "", pool_title.lower()).replace("_", "")
    if min(len(t_clean), len(p_clean)) >= 4 and (t_clean in p_clean or p_clean in t_clean):
        return True

    # 原始字面子串检查
    t_strip = title.strip().lower()
    p_strip = pool_title.strip().lower()
    if min(len(t_strip), len(p_strip)) >= 4 and (t_strip in p_strip or p_strip in t_strip):
        return True

    return False


def parse_markdown_ledger(content: str) -> Dict[str, Any]:
    """
    从 Markdown 源码中解析 `## 已写` 和 `## 选题池` 表格。
    """
    written: List[Dict[str, str]] = []
    pool: List[Dict[str, str]] = []
    current_sec: Optional[str] = None

    for line in content.splitlines():
        s = line.strip()
        if s.startswith("## "):
            if "已写" in s:
                current_sec = "written"
            elif "选题池" in s:
                current_sec = "pool"
            else:
                current_sec = None
            continue

        if current_sec and s.startswith("|") and s.endswith("|"):
            parts = [p.strip() for p in s.split("|")][1:-1]
            if not parts or any(c in parts[0] for c in ["---", "日期", "优先级"]):
                continue

            if current_sec == "written" and len(parts) >= 6:
                written.append({
                    "date": parts[0],
                    "title": parts[1],
                    "source": parts[2],
                    "status": parts[3],
                    "file": parts[4],
                    "feedback": parts[5]
                })
            elif current_sec == "pool" and len(parts) >= 4:
                pool.append({
                    "priority": parts[0],
                    "title": parts[1],
                    "source": parts[2],
                    "angle": parts[3],
                    "claimed_topic": parts[4] if len(parts) > 4 else "",
                    "last_published": parts[5] if len(parts) > 5 else ""
                })

    return {
        "written": written,
        "pool": pool
    }


def _atomic_write_file(file_path: Path, content: str) -> None:
    """
    在同一目录下创建临时文件并原子替换，确保在断电或异常时不破坏原文件。
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = file_path.parent
    with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
        tf.write(content)
        tf.flush()
        os.fsync(tf.fileno())
        temp_name = tf.name

    try:
        os.replace(temp_name, file_path)
    except Exception:
        if os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except OSError:
                pass
        raise


class LedgerAdapter:
    """
    中央防重台账适配器
    支持 Obsidian 仓库真实台账读写、相似度查重与离线 JSON 快照兜底。
    """

    def __init__(
        self,
        ledger_path: Optional[Union[str, Path]] = None,
        snapshot_path: Optional[Union[str, Path]] = None,
        vault_path: Optional[Union[str, Path]] = None
    ):
        if ledger_path is not None:
            self.ledger_path: Optional[Path] = Path(ledger_path)
        elif vault_path is not None:
            vp = Path(vault_path)
            if vp.is_file() or vp.suffix == ".md":
                self.ledger_path = vp
            elif (vp / "工作台" / "AI领航团文章" / "已写清单.md").exists():
                self.ledger_path = vp / "工作台" / "AI领航团文章" / "已写清单.md"
            elif (vp / "已写清单.md").exists():
                self.ledger_path = vp / "已写清单.md"
            else:
                self.ledger_path = vp / "工作台" / "AI领航团文章" / "已写清单.md"
        else:
            env_path = os.environ.get("AI_PILOT_LEDGER_PATH")
            if env_path:
                self.ledger_path = Path(env_path)
            else:
                env_vault = os.environ.get("PILOT_VAULT_PATH") or os.environ.get("AI_PILOT_VAULT_PATH")
                if env_vault:
                    vp = Path(env_vault)
                    if (vp / "工作台" / "AI领航团文章" / "已写清单.md").exists():
                        self.ledger_path = vp / "工作台" / "AI领航团文章" / "已写清单.md"
                    elif (vp / "已写清单.md").exists():
                        self.ledger_path = vp / "已写清单.md"
                    else:
                        self.ledger_path = vp / "工作台" / "AI领航团文章" / "已写清单.md"
                else:
                    self.ledger_path = DEFAULT_LEDGER_PATH

        if snapshot_path is not None:
            self.snapshot_path: Optional[Path] = Path(snapshot_path)
        else:
            env_snap = os.environ.get("AI_PILOT_SNAPSHOT_PATH")
            self.snapshot_path = Path(env_snap) if env_snap else DEFAULT_SNAPSHOT_PATH

        # 离线或快照模式下记录的草稿（内存存储）
        self.memory_drafts: List[Dict[str, Any]] = []

    @property
    def is_vault_available(self) -> bool:
        """检查中央 Obsidian 仓库台账文件是否存在且可读"""
        return bool(self.ledger_path and self.ledger_path.exists() and self.ledger_path.is_file())

    def parse_ledger(self, content: Optional[str] = None) -> Dict[str, Any]:
        """
        解析台账内容。
        - 若提供 content，直接解析传入的字符串；
        - 若未提供 content 且中央台账存在，从中央台账文件读取；
        - 若中央台账不存在，自动回退到本地快照文件读取。
        """
        if content is not None:
            return parse_markdown_ledger(content)

        if self.is_vault_available and self.ledger_path:
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    return parse_markdown_ledger(f.read())
            except Exception as e:
                # 读中央台账失败时降级到快照
                pass

        return self._load_snapshot()

    def _load_snapshot(self) -> Dict[str, Any]:
        """从本地打包的 JSON 快照加载台账数据"""
        if self.snapshot_path and self.snapshot_path.exists():
            try:
                with open(self.snapshot_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {
                        "written": data.get("written", []),
                        "pool": data.get("pool", []),
                        "updated": data.get("updated", "")
                    }
            except Exception:
                pass
        return {"written": [], "pool": []}

    def search_duplicate(self, query: str, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        基于 CJK bigram Jaccard 相似度在已写文章和选题池中查重。
        对比 query 与所有已写题目和选题池题目。
        返回匹配列表，包含 score, title, table ('written' 或 'pool'), details，按 score 降序排列。
        """
        data = self.parse_ledger()
        matches: List[Dict[str, Any]] = []

        q = query.strip()
        if not q:
            return matches

        # 检查已写表
        for item in data.get("written", []):
            title = item.get("title", "")
            score = cjk_bigram_similarity(q, title)
            if score >= threshold:
                matches.append({
                    "score": round(score, 4),
                    "title": title,
                    "table": "written",
                    "details": item
                })

        # 检查选题池
        for item in data.get("pool", []):
            title = item.get("title", "")
            score = cjk_bigram_similarity(q, title)
            if score >= threshold:
                matches.append({
                    "score": round(score, 4),
                    "title": title,
                    "table": "pool",
                    "details": item
                })

        # 按相似度降序排序
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    def register_draft(
        self,
        title: str,
        file_name: str,
        author: str = "领航团成员",
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        登记新草稿：
        - 若中央台账存在：
          - 向 `## 已写` 表格顶部追加一行：
            `| YYYY-MM-DD | <title> | 本地草稿（<author>） | **draft** 新建 | `<file_name>` | — |`
          - 若匹配到 `## 选题池` 中的条目（相似度 >= 0.7 或非平凡子串包含），从 `## 选题池` 中移除该行
          - 更新 frontmatter 中的 `updated: YYYY-MM-DD`
          - 原子化写回 `已写清单.md`
        - 若中央台账不存在（独立开发/同事离线机）：
          - 自动记录到内存/本地日志
          - 返回状态包含 `snapshot_fallback=True` 与明确提示信息
        """
        if not author:
            author = "领航团成员"

        if not date:
            date = datetime.date.today().strftime("%Y-%m-%d")

        clean_file_name = Path(str(file_name).strip("` ")).name
        new_row = f"| {date} | {title} | 本地草稿（{author}） | **draft** 新建 | `{clean_file_name}` | — |"

        # 如果中央台账不可达，执行快照兜底模式
        if not self.is_vault_available or not self.ledger_path:
            record = {
                "title": title,
                "file_name": clean_file_name,
                "author": author,
                "date": date,
                "row": new_row,
                "timestamp": datetime.datetime.now().isoformat()
            }
            self.memory_drafts.append(record)
            return {
                "success": True,
                "registered": False,
                "snapshot_fallback": True,
                "title": title,
                "file_name": clean_file_name,
                "author": author,
                "date": date,
                "row": new_row,
                "removed_from_pool": [],
                "notice": "中央台账文件不可达，已进入快照兜底模式：草稿已暂存至本地内存/日志，未回写中央台账。"
            }

        # 中央台账可达，读取并执行更新
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            content = f.read()

        new_content, removed_pool_items = self._apply_draft_registration(
            content=content,
            title=title,
            new_row=new_row,
            date=date
        )

        _atomic_write_file(self.ledger_path, new_content)

        return {
            "success": True,
            "registered": True,
            "snapshot_fallback": False,
            "title": title,
            "file_name": clean_file_name,
            "author": author,
            "date": date,
            "row": new_row,
            "removed_from_pool": removed_pool_items,
            "notice": "已成功在中央防重台账中登记草稿。"
        }

    def _apply_draft_registration(
        self,
        content: str,
        title: str,
        new_row: str,
        date: str
    ) -> Tuple[str, List[str]]:
        """
        计算登记草稿并剔除选题池后的 Markdown 新内容。
        """
        # 1. 更新 frontmatter updated: YYYY-MM-DD
        if re.search(r"^updated:\s*\S+", content, flags=re.MULTILINE):
            content = re.sub(r"^(updated:\s*)\S+", rf"\g<1>{date}", content, flags=re.MULTILINE)
        else:
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = f"---{parts[1]}updated: {date}\n---{parts[2]}"

        lines = content.splitlines()
        output_lines: List[str] = []
        current_sec: Optional[str] = None
        inserted = False
        removed_from_pool: List[str] = []

        for line in lines:
            s = line.strip()
            if s.startswith("## "):
                if "已写" in s:
                    current_sec = "written"
                elif "选题池" in s:
                    current_sec = "pool"
                else:
                    current_sec = None

            if current_sec == "written" and not inserted:
                output_lines.append(line)
                # 寻找表格分隔行并在其后立即插入新行
                if s.startswith("|") and "---" in s:
                    output_lines.append(new_row)
                    inserted = True
                continue

            if current_sec == "pool" and s.startswith("|") and s.endswith("|"):
                parts = [p.strip() for p in s.split("|")][1:-1]
                if parts and not any(c in parts[0] for c in ["---", "优先级"]):
                    pool_title = parts[1] if len(parts) > 1 else ""
                    if is_matching_topic(title, pool_title, threshold=0.7):
                        removed_from_pool.append(pool_title)
                        continue  # 剔除该行

            output_lines.append(line)

        # 边缘兜底：若未能在原有表格中插入
        if not inserted:
            written_idx = -1
            for i, l in enumerate(output_lines):
                if l.strip().startswith("## ") and "已写" in l.strip():
                    written_idx = i
                    break
            if written_idx >= 0:
                table_header = [
                    "",
                    "| 日期 | 标题 | 来源 | 状态 | 文件 | 发布后反馈 |",
                    "|---|---|---|---|---|---|",
                    new_row
                ]
                output_lines = output_lines[: written_idx + 1] + table_header + output_lines[written_idx + 1 :]
            else:
                table_sec = [
                    "",
                    "## 已写（按日期倒序）",
                    "",
                    "| 日期 | 标题 | 来源 | 状态 | 文件 | 发布后反馈 |",
                    "|---|---|---|---|---|---|",
                    new_row
                ]
                output_lines.extend(table_sec)

        new_content = "\n".join(output_lines)
        if content.endswith("\n"):
            new_content += "\n"

        return new_content, removed_from_pool

    def export_snapshot(self, output_path: Optional[Union[str, Path]] = None) -> Path:
        """
        将当前中央台账导出为离线 JSON 快照文件。
        """
        if not self.is_vault_available or not self.ledger_path:
            raise FileNotFoundError("无法从不可达的中央台账导出快照")

        target_path = Path(output_path) if output_path else self.snapshot_path
        if not target_path:
            target_path = DEFAULT_SNAPSHOT_PATH

        with open(self.ledger_path, "r", encoding="utf-8") as f:
            text = f.read()

        updated_match = re.search(r"^updated:\s*(\S+)", text, re.MULTILINE)
        updated_date = updated_match.group(1) if updated_match else datetime.date.today().strftime("%Y-%m-%d")

        data = parse_markdown_ledger(text)
        snapshot = {
            "updated": updated_date,
            "written": data.get("written", []),
            "pool": data.get("pool", [])
        }

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

        return target_path
