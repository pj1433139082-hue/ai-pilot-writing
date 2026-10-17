# -*- coding: utf-8 -*-
"""
AI 领航团文章规范检查器 (零依赖 Python 3 标准库)
提供双模式 (draft/publish) 规则校验引擎、P0 硬阻断门禁与 P1 软优化建议
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

# 文本字数区间
MIN_CJK, MAX_CJK = 1500, 2500

# 冒号密度阈值（叙述段内连续冒号数）
COLON_PER_PARA_MIN = 3

# 核心词局部堆叠窗口大小与次数阈值
KEY_WINDOW = 100
KEY_WINDOW_MAX = 4

# 一级文风禁用词 (P0)
TIER1_BANNED = [
    "赋能", "抓手", "颗粒度", "拉通", "底层逻辑", "顶层设计",
    "护城河", "组合拳", "深度赋能", "全面打通", "深度剖析",
]

# 浮夸/AI套话 (P1)
AI_SLOP_WORDS = [
    "赋能", "颠覆", "开启崭新篇章", "开启新篇章", "如春风拂面",
    "未来已来", "不言而喻", "毋庸置疑", "天花板", "神器", "秒杀一切",
    "纵观全局", "纵观历史", "画卷", "底色", "奏响", "重塑", "领航",
]

# 标题禁止词
BANNED_TITLE_WORDS = ["浅谈", "初探", "关于", "浅析", "探讨"]

# 外泄 P0（门禁 INTERNAL_P0 ∪ 体检表 INTERNAL_WORDS）
INTERNAL_P0 = [
    "内部资料库", "智能体管家", "cangku", "obsidian_work", "ops-ai-hub",
    "钉钉-任务台", "task-states", "ai-task-center", "工作台/", "工作台\\",
    "资料库/", "Hermes", "hermes",
]

# 软词 / 待人工确认词
INTERNAL_P1 = ["管家", "本机", "arXiv", "Zotero", "Multica"]
SOFT_WORDS = ["大概", "应该", "看起来", "本机"]

DOTCLAUDE_RE = re.compile(r"(?<![\w.])\.claude(?![\w])")
LOCAL_PATH_RE = re.compile(r"(?<![A-Za-z0-9/\\])(?:[A-Za-z]:[\\/]|\\\\[A-Za-z0-9._-]+\\)")
FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.S)
GEN_NOTE_RE = re.compile(r"^> \[!info\] (?:生产说明|生成说明)\r?\n(?:>.*\r?\n?)*", re.M)
CODE_FENCE_RE = re.compile(r"```.*?```", re.S)

CN_HEAD_RE = re.compile(r"^#{1,3}\s*[一二三四五六七八九十]+\s*[、.．]", re.M)
SRC_SEC_RE = re.compile(r"^#{1,3}\s*[^\n]{0,16}(资料来源|参考资料|素材来源)\s*$", re.M)
FETCH_TIME_RE = re.compile(r"抓取时间|读取时间|实读时间|抓取于|访问时间|检索时间"
                          r"|(?:抓取|读取|实读|访问|检索)\s*[:：]?\s*\d{4}-\d{2}-\d{2}")
URL_RE = re.compile(r"https?://")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

SECRET_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE), "疑似 OpenAI/通用 API Key 泄露"),
    (re.compile(r"(?:password|passwd|pwd)\s*[:=]\s*['\"][^\s'\"]{6,}['\"]", re.IGNORECASE), "疑似明文密码配置"),
    (re.compile(r"ghp_[a-zA-Z0-9]{30,}", re.IGNORECASE), "疑似 GitHub Personal Access Token"),
]


def zh_len(s: str) -> int:
    return len(CJK_RE.findall(s))


def colon_heavy_paragraphs(text: str, min_count: int = COLON_PER_PARA_MIN) -> list[str]:
    """返回「叙述段里连用 ≥min_count 个冒号」的段落首 40 字。
    叙述段 = 连续的正文行；列表项（`-`/`*`/`数字.`）、引用（`>`）、标题、代码行
    都不计入，且打断当前的叙述段。
    """
    out, buf = [], []
    for line in text.split("\n"):
        s = line.strip()
        if not s or s.startswith(("-", "*", ">", "#", "|")) or re.match(r"^\d+[.、)]", s):
            if buf:
                out.append(buf)
                buf = []
            continue
        buf.append(s)
    if buf:
        out.append(buf)
    hits = []
    for blk in out:
        joined = " ".join(blk)
        if joined.count("：") >= min_count:
            hits.append(joined[:40])
    return hits


def keyword_stacking(text: str, keywords, *, window: int = KEY_WINDOW,
                     need: int = KEY_WINDOW_MAX) -> list[tuple[str, int]]:
    """返回 [(词, 某窗口内最多重复次数)]，只报局部堆叠。
    按窗口滑动统计每个 2-gram 在任意 window 个中文字内的最大出现次数。
    """
    out = []
    for k in keywords:
        if len(k) < 2:
            continue
        pos = [m.start() for m in re.finditer(re.escape(k), text)]
        if len(pos) < need:
            continue
        best, j = 0, 0
        for i in range(len(pos)):
            while pos[i] - pos[j] >= window:
                j += 1
            best = max(best, i - j + 1)
        if best >= need:
            out.append((k, best))
    out.sort(key=lambda x: (-x[1], x[0]))
    return out


def find_unresolved_slots(text: str) -> list[str]:
    """查找文本中未填写的 {{...}} 占位槽位。"""
    return re.findall(r"\{\{([^}]+)\}\}", text)


def read_views(text: str) -> dict:
    """返回四个视图：text(原文) / raw(去 frontmatter 与生产/生成说明，留代码块) /
    prose(再去代码块，用于字数与文风) / nontable(prose 去表格行)。"""
    raw = FRONTMATTER_RE.sub("", text, count=1)
    raw = GEN_NOTE_RE.sub("", raw)
    prose = CODE_FENCE_RE.sub("", raw)
    nontable = re.sub(r"^\|.*$", "", prose, flags=re.M)
    return {"text": text, "raw": raw, "prose": prose, "nontable": nontable}


@dataclass
class Issue:
    level: str  # "P0" or "P1"
    code: str
    message: str
    line: Optional[int] = None
    snippet: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class LintResult:
    file_path: str
    issues: List[Issue] = field(default_factory=list)
    chars: int = 0
    facts: Dict[str, Any] = field(default_factory=dict)

    @property
    def p0_issues(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "P0"]

    @property
    def p1_issues(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "P1"]

    @property
    def is_valid(self) -> bool:
        return len(self.p0_issues) == 0

    def to_dict(self) -> dict:
        return {
            "path": str(self.file_path),
            "chars": self.chars,
            "p0": [i.message for i in self.p0_issues],
            "p1": [i.message for i in self.p1_issues],
            "facts": self.facts,
        }

    def __getitem__(self, key: str) -> Any:
        if key in ("path", "file_path"):
            return str(self.file_path)
        if key == "chars":
            return self.chars
        if key == "p0":
            return [i.message for i in self.p0_issues]
        if key == "p1":
            return [i.message for i in self.p1_issues]
        if key == "facts":
            return self.facts
        if key == "issues":
            return self.issues
        if key == "is_valid":
            return self.is_valid
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        return key in ("path", "file_path", "chars", "p0", "p1", "facts", "issues", "is_valid")

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self) -> List[str]:
        return ["path", "chars", "p0", "p1", "facts"]


class PilotLinter:
    BANNED_TITLE_WORDS = BANNED_TITLE_WORDS
    AI_SLOP_WORDS = AI_SLOP_WORDS
    TIER1_BANNED = TIER1_BANNED
    SECRET_PATTERNS = SECRET_PATTERNS
    INTERNAL_P0 = INTERNAL_P0
    INTERNAL_P1 = INTERNAL_P1
    SOFT_WORDS = SOFT_WORDS

    def __init__(self):
        pass

    def lint_file(self, file_path: str, mode: str = "draft", publish: bool = False, keywords: str = "") -> LintResult:
        if not os.path.exists(file_path):
            res = LintResult(file_path=file_path)
            res.issues.append(Issue(level="P0", code="FILE_NOT_FOUND", message=f"文件不存在: {file_path}"))
            return res

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return self.lint_text(content, file_path=file_path, mode=mode, publish=publish, keywords=keywords)

    def lint_text(self, text: str, file_path: str = "<inline>", mode: str = "draft",
                  publish: bool = False, keywords: str = "") -> LintResult:
        # publish 参数优先级更高：publish=True 时转为 publish 模式
        eff_mode = "publish" if publish or mode == "publish" else "draft"

        result = LintResult(file_path=file_path)
        lines = text.splitlines()

        # 视图构建
        views = read_views(text)
        raw = views["raw"]
        prose = views["prose"]
        nontable = views["nontable"]
        chars = zh_len(prose)
        result.chars = chars

        # 统计事实抽取
        facts: Dict[str, Any] = {}
        facts["链接数"] = len(URL_RE.findall(raw))
        facts["中文数字标题"] = len(CN_HEAD_RE.findall(raw))
        facts["中文字"] = chars
        facts["抓取时间"] = len(FETCH_TIME_RE.findall(raw))
        facts["来源小节"] = bool(SRC_SEC_RE.search(raw))
        facts["冒号"] = prose.count("：")
        result.facts = facts

        # ==========================================
        # 1. 结构与格式骨架检查 (Both Modes)
        # ==========================================
        self._check_frontmatter(text, lines, result)
        self._check_title(lines, result)
        self._check_callouts(text, result)
        self._check_opening_questions(text, result)
        self._check_tables(text, result)
        self._check_pitfall_table(text, result)
        self._check_secrets(lines, result)

        # ==========================================
        # 2. 模式差异性指标 (Draft vs Publish)
        # ==========================================
        self._check_slots(text, eff_mode, result)
        self._check_char_count(chars, eff_mode, result)
        self._check_drive_paths(raw, eff_mode, result)
        self._check_internal_jargon(raw, eff_mode, result)

        # Publish 模式独有的排版配额与语法残留拦截
        if eff_mode == "publish":
            self._check_typography_quotas(prose, nontable, chars, result)
            self._check_publish_residuals(raw, result)

        # ==========================================
        # 3. P1 文风优化与体裁诊断 (Both Modes)
        # ==========================================
        self._check_ai_slop(lines, result)
        self._check_colon_density(nontable, result)
        self._check_word_stacking(nontable, prose, keywords, result)
        self._check_actionable_items(text, result)
        self._check_citation_and_structure_p1(raw, facts, result)

        if eff_mode == "publish" and re.search(r"^status:\s*draft\b", text, flags=re.M):
            result.issues.append(Issue(
                level="P1", code="P1_STATUS_DRAFT",
                message="源文件 status 仍为 draft",
                suggestion="发布前请将 frontmatter 中的 status 改为 ready 或 published"
            ))

        return result

    def _check_frontmatter(self, text: str, lines: List[str], res: LintResult):
        if not text.startswith("---"):
            res.issues.append(Issue(
                level="P0", code="P0_FRONTMATTER_MISSING",
                message="缺少 YAML Frontmatter 元数据块 (以 --- 开头)",
                line=1, suggestion="在文章开头添加标准元数据定义"
            ))
            return

        m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
        if not m:
            res.issues.append(Issue(
                level="P0", code="P0_FRONTMATTER_UNCLOSED",
                message="YAML Frontmatter 未正确闭合 (缺少配对的 ---)",
                line=1
            ))
            return

        fm_content = m.group(1)
        for req_field in ["title", "created", "status", "author"]:
            if not re.search(rf"^{req_field}\s*:", fm_content, re.MULTILINE):
                # 兼容历史稿件：如果 author 未在 frontmatter 定义，但有生成说明、已发布或废弃状态
                if req_field == "author" and (
                    re.search(r">\s*由\s+[^\s·]+\s+生成", text)
                    or re.search(r"published_at|status:\s*(?:published|dropped)", fm_content)
                ):
                    continue
                res.issues.append(Issue(
                    level="P0", code="P0_FRONTMATTER_FIELD",
                    message=f"Frontmatter 缺少必要字段: {req_field}",
                    line=1, suggestion=f"在 Frontmatter 中补齐 {req_field}: 属性"
                ))

    def _check_title(self, lines: List[str], res: LintResult):
        title_line = None
        line_no = None
        for idx, line in enumerate(lines, 1):
            if line.startswith("# ") and not line.startswith("## "):
                title_line = line[2:].strip()
                line_no = idx
                break

        if not title_line:
            res.issues.append(Issue(
                level="P0", code="P0_TITLE_MISSING",
                message="缺少一级文章标题 (# 标题)", line=1,
                suggestion="添加一个具体而有实体内容的一级标题"
            ))
            return

        for banned in self.BANNED_TITLE_WORDS:
            if banned in title_line:
                res.issues.append(Issue(
                    level="P0", code="P0_TITLE_BANNED_WORD",
                    message=f"标题包含禁用词汇「{banned}」: \"{title_line}\"",
                    line=line_no, snippet=title_line,
                    suggestion=f"修改标题，禁止使用「{banned}」，改用具体名词短语，如「进水冲击处置AI顾问落地实录」"
                ))

    def _check_callouts(self, text: str, res: LintResult):
        if not re.search(r">\s*\[!abstract\]\s*一句话定位", text, re.IGNORECASE):
            res.issues.append(Issue(
                level="P0", code="P0_CALLOUT_ABSTRACT_MISSING",
                message="缺少开篇定位块: `> [!abstract] 一句话定位`",
                suggestion="在标题后增加一句话定位 Callout 说明解决什么业务问题"
            ))

        # 同时兼容「生产说明」与历史的「生成说明」
        if not re.search(r">\s*\[!info\]\s*(?:生产说明|生成说明)", text, re.IGNORECASE):
            res.issues.append(Issue(
                level="P0", code="P0_CALLOUT_INFO_MISSING",
                message="缺少生产说明块: `> [!info] 生产说明`",
                suggestion="在定位后增加生产说明 Callout 说明作者与场景"
            ))
        else:
            if "事实截止" not in text:
                res.issues.append(Issue(
                    level="P1", code="P1_FACT_CUTOFF_MISSING",
                    message="生产说明中未明确标注「事实截止」日期",
                    suggestion="在生产说明中注明事实截止时间（如 事实截止：2026-10-17）"
                ))

    def _check_opening_questions(self, text: str, res: LintResult):
        has_three_q = bool(re.search(r"(?:三个问题|3个问题|明确回答.*问题|重点回答.*问题|讲清.*(?:怎么|哪些|哪步))", text))
        q_count = len(re.findall(r"^[123]\.\s+\*\*.*?\*\*", text, re.MULTILINE))
        if not has_three_q and q_count < 3:
            res.issues.append(Issue(
                level="P0", code="P0_OPENING_QUESTIONS_MISSING",
                message="缺少开篇自述三问引导（未明确回答哪三个具体问题）",
                suggestion="在正文第一段明确列出「重点回答三个问题：1. ... 2. ... 3. ...」"
            ))

    def _check_tables(self, text: str, res: LintResult):
        table_separators = re.findall(r"^\|(?:\s*:?[-]{2,}:?\s*\|)+\s*$", text, re.MULTILINE)
        count = len(table_separators)
        if count < 2:
            res.issues.append(Issue(
                level="P0", code="P0_TABLE_COUNT_LOW",
                message=f"全文 Markdown 结构化表格仅 {count} 张，未达硬指标 (必须 ≥ 2 张)",
                suggestion="领航团规范要求必须提供结构化对照表、配置速查表或避坑大表，请补充表格"
            ))

    def _check_pitfall_table(self, text: str, res: LintResult):
        sec_matches = list(re.finditer(r"(?:^|\n)#{1,3}\s+.*(?:踩坑|避坑|排错|常见问题|局限).*\n([\s\S]*?)(?=\n#{1,3}\s|\Z)", text))
        if not sec_matches:
            res.issues.append(Issue(
                level="P0", code="P0_PITFALL_SECTION_MISSING",
                message="缺少独立的「踩坑清单」或「避坑指南」章节",
                suggestion="添加专门章节记录真实踩坑经验与解决建议"
            ))
            return

        # 检查是否存在包含 Markdown 结构化表格的避坑小节
        has_table = any(bool(re.search(r"\|(?:\s*:?[-]{2,}:?\s*\|)+", m.group(1))) for m in sec_matches)
        if not has_table:
            res.issues.append(Issue(
                level="P0", code="P0_PITFALL_TABLE_MISSING",
                message="踩坑与避坑部分缺少结构化大表 (Markdown 形式)",
                suggestion="将踩坑记录整理为 [踩坑现象 | 真实根因 | 应对建议] 的结构化表格"
            ))

    def _check_secrets(self, lines: List[str], res: LintResult):
        for idx, line in enumerate(lines, 1):
            for pat, desc in self.SECRET_PATTERNS:
                if pat.search(line):
                    res.issues.append(Issue(
                        level="P0", code="P0_SECRET_LEAK",
                        message=f"第 {idx} 行发现高危敏感信息: {desc}",
                        line=idx, snippet=line.strip()[:60] + "...",
                        suggestion="严禁在文章中直接写入真实 Token 或密码，请使用占位符脱敏"
                    ))

    def _check_slots(self, text: str, mode: str, res: LintResult):
        slots = find_unresolved_slots(text)
        if slots:
            slot_preview = "、".join(slots[:3]) + ("..." if len(slots) > 3 else "")
            if mode == "publish":
                res.issues.append(Issue(
                    level="P0", code="P0_UNRESOLVED_SLOTS",
                    message=f"发现未填写的模板槽位（终审禁止残留）: {slot_preview}",
                    suggestion="在终审发布前，请补全或替换所有正文及元数据 {{...}} 槽位"
                ))
            else:
                res.issues.append(Issue(
                    level="P1", code="P1_UNRESOLVED_SLOTS",
                    message=f"发现 {len(slots)} 处未填写的模板槽位: {slot_preview}",
                    suggestion="草稿撰写中，可在定稿前逐步补齐占位插槽"
                ))

    def _check_char_count(self, chars: int, mode: str, res: LintResult):
        if not (MIN_CJK <= chars <= MAX_CJK):
            if mode == "publish":
                res.issues.append(Issue(
                    level="P0", code="P0_CHAR_COUNT",
                    message=f"字数 {chars} 不在 {MIN_CJK}–{MAX_CJK}",
                    suggestion=f"发布稿必须严格控制正文字数在 {MIN_CJK}–{MAX_CJK} 之间"
                ))
            else:
                res.issues.append(Issue(
                    level="P1", code="P1_CHAR_COUNT",
                    message=f"字数 {chars} 不在 {MIN_CJK}–{MAX_CJK} (草稿阶段建议 1500-2500 字)",
                    suggestion="草稿初期不阻断，定稿时请调整至 1500–2500 字最佳阅读体量"
                ))

    def _check_drive_paths(self, raw: str, mode: str, res: LintResult):
        masked = URL_RE.sub("URL", raw)
        drives = sorted({m.group(0) for m in LOCAL_PATH_RE.finditer(masked)})
        if drives:
            d_str = "、".join(drives[:5]) + ("…" if len(drives) > 5 else "")
            if mode == "publish":
                res.issues.append(Issue(
                    level="P0", code="P0_LOCAL_PATH",
                    message=f"本地盘符路径（读者打不开）: {d_str}",
                    suggestion="读者开发机路径各异，严禁在正文或代码块中保留本地盘符绝对路径"
                ))
            else:
                res.issues.append(Issue(
                    level="P1", code="P1_LOCAL_PATH",
                    message=f"本地盘符路径（读者打不开，建议清理）: {d_str}",
                    suggestion="草稿中使用了本地盘符，定稿前建议脱敏为相对路径或环境变量"
                ))

    def _check_internal_jargon(self, raw: str, mode: str, res: LintResult):
        hits = {w: raw.count(w) for w in self.INTERNAL_P0 if raw.count(w)}
        n_dc = len(DOTCLAUDE_RE.findall(raw))
        if n_dc:
            hits[".claude"] = n_dc

        if hits:
            msg_body = "、".join(f"{w}×{n}" if n > 1 else w for w, n in hits.items())
            if mode == "publish":
                res.issues.append(Issue(
                    level="P0", code="P0_INTERNAL_WORD",
                    message=f"内部词（只对作者成立）: {msg_body}",
                    suggestion="请清理针对作者开发机或特定内部系统的私有词汇，替换为公开通用词"
                ))
            else:
                res.issues.append(Issue(
                    level="P1", code="P1_INTERNAL_WORD",
                    message=f"内部词（只对作者成立，建议替换）: {msg_body}",
                    suggestion="建议替换内部专有名词，使外部读者易于理解"
                ))

    def _check_typography_quotas(self, prose: str, nontable: str, chars: int, res: LintResult):
        # 1. 破折号 <= max(1, chars // 1000)
        dashes = len(re.findall(r"——|--", nontable))
        limit = max(1, chars // 1000)
        if dashes > limit:
            res.issues.append(Issue(
                level="P0", code="P0_DASH_OVERUSE",
                message=f"破折号 {dashes} 处，超过 {limit}（≤1/千字）",
                suggestion="破折号过多会导致语气过于零碎，改用括号、逗号或句号"
            ))

        # 2. 加粗每大节 <= 1（非表格行）
        sections, cur, name = [], [], "（开篇）"
        for line in prose.split("\n"):
            if re.match(r"^#{1,2} ", line):
                sections.append((name, cur))
                cur, name = [], line.strip("# ").strip()
            else:
                cur.append(line)
        sections.append((name, cur))
        for name, sec_lines in sections:
            txt = "\n".join(l for l in sec_lines if not l.startswith("|"))
            bolds = len(re.findall(r"\*\*[^*]+\*\*", txt))
            if bolds > 1:
                res.issues.append(Issue(
                    level="P0", code="P0_BOLD_OVERUSE",
                    message=f"「{name[:18]}」加粗 {bolds} 处（每节 ≤1）",
                    suggestion="每节只保留最关键的一处加粗强调，避免整段视觉杂乱"
                ))

        # 3. 「不是A，是B」转折 <= 1
        pats = len(re.findall(
            r"不在[^。，]{1,12}，在|不是[^。，]{1,12}，(?:而是|是)|不是[^。]{1,14}。\s*(?:真正|它只有|其实)",
            prose))
        if pats > 1:
            res.issues.append(Issue(
                level="P0", code="P0_NOT_A_BUT_B",
                message=f"「不是A，是B」式转折 {pats} 处（全篇 ≤1）",
                suggestion="避免典型的 AI 写作说教式对比转折句型"
            ))

        # 4. 一级禁用词
        banned = [w for w in self.TIER1_BANNED if w in prose]
        if banned:
            res.issues.append(Issue(
                level="P0", code="P0_TIER1_BANNED",
                message="一级禁用词: " + "、".join(banned),
                suggestion="严禁在领航团文章中使用通用大模型空洞套话"
            ))

    def _check_publish_residuals(self, raw: str, res: LintResult):
        # 排除允许的开头 double callout 后的 callout 残留
        clean_raw = re.sub(r">\s*\[!(?:abstract|info)\][^\n]*", "", raw, flags=re.IGNORECASE)
        for k, msg in [("[!", "Obsidian callout"), ("[[", "双链"), ("![](", "本地图片")]:
            if k in (clean_raw if k == "[!" else raw):
                res.issues.append(Issue(
                    level="P0", code="P0_PUBLISH_RESIDUAL",
                    message=f"发布稿残留 {msg}",
                    suggestion=f"发布稿中不能存在 {msg}，请将其转换为标准 Markdown 格式"
                ))

    def _check_ai_slop(self, lines: List[str], res: LintResult):
        for idx, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                continue
            for word in self.AI_SLOP_WORDS:
                if word in line:
                    res.issues.append(Issue(
                        level="P1", code="P1_AI_SLOP_WORD",
                        message=f"第 {idx} 行出现浮夸/AI套话「{word}」",
                        line=idx, snippet=line.strip()[:60],
                        suggestion=f"建议删除或替换「{word}」，用具体的业务事实、指标或动作替代"
                    ))

    def _check_colon_density(self, nontable: str, res: LintResult):
        heavy = colon_heavy_paragraphs(nontable)
        if heavy:
            res.issues.append(Issue(
                level="P1", code="P1_COLON_DENSITY_HIGH",
                message=f"叙述段冒号连用 {len(heavy)} 处（每段 ≥{COLON_PER_PARA_MIN} 个）："
                        + "；".join(f"「{h}…」" for h in heavy[:2]),
                suggestion="段落内避免连续使用冒号，改用逗号、句号拆分短句，保持自然叙述"
            ))

    def _check_word_stacking(self, nontable: str, prose: str, keywords: str, res: LintResult):
        kws = [k for k in keywords.split(",") if k.strip()]
        if not kws:
            m = re.search(r"^# (.+)$", prose, flags=re.M)
            if m:
                title = re.sub(r"[^\u4e00-\u9fff]", "", m.group(1))
                kws = sorted({title[i:i + 2] for i in range(len(title) - 1)})
        stack = keyword_stacking(nontable, kws)
        if stack:
            res.issues.append(Issue(
                level="P1", code="P1_WORD_STACKING",
                message="标题核心词局部堆叠（"
                        + "、".join(f"{k}×{n}/{KEY_WINDOW}字" for k, n in stack[:5])
                        + "）：同一短句里反复出现，考虑换同义词或删重复",
                suggestion="适当调整句式或使用指代词，避免短距离内反复重复同一核心词"
            ))

    def _check_actionable_items(self, text: str, res: LintResult):
        has_checklist = bool(re.search(r"-\s*\[[\sXx]\]", text))
        has_action_item = bool(re.search(r"(?:单一行动项|行动项|立刻落地|Checklist|复用清单)", text))
        if not has_checklist and not has_action_item:
            res.issues.append(Issue(
                level="P1", code="P1_ACTION_ITEM_MISSING",
                message="缺少直接可上手的 Checklist 或单一行动项",
                suggestion="在文末增加读者看完即可照着操作的 Checklist 或 5 分钟单一行动项"
            ))

    def _check_citation_and_structure_p1(self, raw: str, facts: Dict[str, Any], res: LintResult):
        if not facts.get("来源小节"):
            res.issues.append(Issue(
                level="P1", code="P1_SRC_SEC_MISSING",
                message="无正式来源小节",
                suggestion="在文末增加「资料来源」或「参考资料」小节"
            ))
        if facts.get("链接数", 0) == 0:
            res.issues.append(Issue(
                level="P1", code="P1_NO_URL",
                message="全文无外部链接",
                suggestion="文章应包含可回溯的外部公开参考链接"
            ))
        elif facts.get("链接数", 0) < 3:
            res.issues.append(Issue(
                level="P1", code="P1_URL_LOW",
                message=f"来源链接偏少（{facts['链接数']} 条）",
                suggestion="建议补充 3 条以上的高信噪比参考链接"
            ))
        if facts.get("抓取时间", 0) == 0:
            res.issues.append(Issue(
                level="P1", code="P1_FETCH_TIME_MISSING",
                message="来源未标抓取/读取时间（B4#5）",
                suggestion="在外部来源中注明抓取或核验时间"
            ))
        if facts.get("中文数字标题", 0) == 0:
            res.issues.append(Issue(
                level="P1", code="P1_CN_HEAD_MISSING",
                message="章节标题未用中文数字编号（D2）",
                suggestion="建议采用「一、为什么值得看」「二、...」等中文数字编号体系"
            ))

        soft = {w: raw.count(w) for w in sorted(set(self.INTERNAL_P1 + self.SOFT_WORDS)) if raw.count(w)}
        if soft:
            res.issues.append(Issue(
                level="P1", code="P1_SOFT_WORDS",
                message="软词（人工确认是否该改写）: " + "、".join(f"{w}×{n}" for w, n in soft.items()),
                suggestion="人工复核软词用法，避免过于模糊或不确定表达"
            ))


def lint_article(path: str | Path, mode: str = "draft", publish: bool = False, keywords: str = "") -> LintResult:
    """顶级便捷调用函数，兼容 legacy article_lint.py 接口与新规范。"""
    linter = PilotLinter()
    return linter.lint_file(str(path), mode=mode, publish=publish, keywords=keywords)
