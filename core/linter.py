# -*- coding: utf-8 -*-
"""
AI 领航团文章规范检查器 (零依赖 Python 3 标准库)
提供 P0 硬阻断检查与 P1 软优化建议
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

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

    @property
    def p0_issues(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "P0"]

    @property
    def p1_issues(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "P1"]

    @property
    def is_valid(self) -> bool:
        return len(self.p0_issues) == 0

class PilotLinter:
    BANNED_TITLE_WORDS = ["浅谈", "初探", "关于", "浅析", "探讨"]
    AI_SLOP_WORDS = [
        "赋能", "颠覆", "开启崭新篇章", "开启新篇章", "如春风拂面",
        "未来已来", "不言而喻", "毋庸置疑", "天花板", "神器", "秒杀一切"
    ]
    SECRET_PATTERNS = [
        (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE), "疑似 OpenAI/通用 API Key 泄露"),
        (re.compile(r"(?:password|passwd|pwd)\s*[:=]\s*['\"][^\s'\"]{6,}['\"]", re.IGNORECASE), "疑似明文密码配置"),
        (re.compile(r"ghp_[a-zA-Z0-9]{30,}", re.IGNORECASE), "疑似 GitHub Personal Access Token"),
    ]

    def __init__(self):
        pass

    def lint_file(self, file_path: str) -> LintResult:
        if not os.path.exists(file_path):
            res = LintResult(file_path=file_path)
            res.issues.append(Issue(level="P0", code="FILE_NOT_FOUND", message=f"文件不存在: {file_path}"))
            return res

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return self.lint_text(content, file_path=file_path)

    def lint_text(self, text: str, file_path: str = "<inline>") -> LintResult:
        result = LintResult(file_path=file_path)
        lines = text.splitlines()

        # 1. Frontmatter 检查
        self._check_frontmatter(text, lines, result)

        # 2. 标题规范检查
        self._check_title(lines, result)

        # 3. 双 Callout 检查 (abstract & info)
        self._check_callouts(text, result)

        # 4. 开篇三问检查
        self._check_opening_questions(text, result)

        # 5. 表格数量指标 (≥ 2 张)
        self._check_tables(text, result)

        # 6. 真实踩坑与负面反馈大表检查
        self._check_pitfall_table(text, result)

        # 7. 敏感信息与密钥外泄
        self._check_secrets(lines, result)

        # 8. P1: 去 AI 味检查
        self._check_ai_slop(lines, result)

        # 9. P1: 叙述段冒号连用密度 (单段 ≥3 冒号)
        self._check_colon_density(text, result)

        # 10. P1: 核心词 100 字短窗口局部堆叠
        self._check_word_stacking(text, result)

        # 11. P1: 落地物料检查 (Checklist 或 单一行动项)
        self._check_actionable_items(text, result)

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

        if not re.search(r">\s*\[!info\]\s*生产说明", text, re.IGNORECASE):
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
        has_three_q = bool(re.search(r"(?:三个问题|3个问题|明确回答.*问题|重点回答.*问题)", text))
        q_count = len(re.findall(r"^[123]\.\s+\*\*.*?\*\*", text, re.MULTILINE))
        if not has_three_q and q_count < 3:
            res.issues.append(Issue(
                level="P0", code="P0_OPENING_QUESTIONS_MISSING",
                message="缺少开篇自述三问引导（未明确回答哪三个具体问题）",
                suggestion="在正文第一段明确列出「重点回答三个问题：1. ... 2. ... 3. ...」"
            ))

    def _check_tables(self, text: str, res: LintResult):
        # 统计含有表格分隔行 |---| 的表格数量
        table_separators = re.findall(r"^\|(?:\s*:?[-]{2,}:?\s*\|)+\s*$", text, re.MULTILINE)
        count = len(table_separators)
        if count < 2:
            res.issues.append(Issue(
                level="P0", code="P0_TABLE_COUNT_LOW",
                message=f"全文 Markdown 结构化表格仅 {count} 张，未达硬指标 (必须 ≥ 2 张)",
                suggestion="领航团规范要求必须提供结构化对照表、配置速查表或避坑大表，请补充表格"
            ))

    def _check_pitfall_table(self, text: str, res: LintResult):
        has_pitfall_section = bool(re.search(r"#{1,3}\s*.*(?:踩坑|避坑|排错|常见问题)", text))
        if not has_pitfall_section:
            res.issues.append(Issue(
                level="P0", code="P0_PITFALL_SECTION_MISSING",
                message="缺少独立的「踩坑清单」或「避坑指南」章节",
                suggestion="添加专门章节记录真实踩坑经验与解决建议"
            ))
            return

        # 检查是否包含表格形式的踩坑对比
        pitfall_table_match = re.search(r"(?:踩坑|避坑|排错|局限).*\n[\s\S]*?\|(?:\s*:?[-]{2,}:?\s*\|)+\s*\n([\s\S]*?)(?=\n#{1,3}|\Z)", text)
        if not pitfall_table_match:
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

    def _check_colon_density(self, text: str, res: LintResult):
        # 排除代码块、Frontmatter 与表格
        clean_text = re.sub(r"^---[\s\S]*?---\n", "", text)
        clean_text = re.sub(r"```[\s\S]*?```", "", clean_text)
        clean_text = re.sub(r">.*", "", clean_text)  # 排除 callout
        clean_text = re.sub(r"^\|.*\|$", "", clean_text, flags=re.MULTILINE)  # 排除表格

        paragraphs = clean_text.split("\n\n")
        for p in paragraphs:
            p = p.strip()
            if not p or p.startswith("#"):
                continue
            # 排除纯列表
            list_lines = [l for l in p.splitlines() if re.match(r"^\s*[-*+0-9.]", l)]
            if len(list_lines) > len(p.splitlines()) / 2:
                continue

            colon_count = p.count("：") + p.count(":")
            if colon_count >= 3:
                res.issues.append(Issue(
                    level="P1", code="P1_COLON_DENSITY_HIGH",
                    message=f"叙述段落冒号连用密度过高 (当前段包含 {colon_count} 个冒号)",
                    snippet=p[:60] + "...",
                    suggestion="段落内避免连续使用冒号，改用逗号、句号拆分短句，保持自然叙述"
                ))

    def _check_word_stacking(self, text: str, res: LintResult):
        # 检查 100 字滑动窗口内核心业务词堆叠
        # 去除 markdown 标记
        stripped = re.sub(r"[#*`|>\-\[\]\(\)]", "", text)
        core_nouns = ["智能体", "模型", "提示词", "大区", "流程", "知识库", "台账", "工艺", "工具", "表格"]
        window_size = 100
        for noun in core_nouns:
            for i in range(0, max(0, len(stripped) - window_size), 50):
                chunk = stripped[i:i + window_size]
                if chunk.count(noun) >= 4:
                    res.issues.append(Issue(
                        level="P1", code="P1_WORD_STACKING",
                        message=f"局部 100 字窗口内核心词「{noun}」高频堆叠 (出现 {chunk.count(noun)} 次)",
                        snippet=chunk[:50] + "...",
                        suggestion=f"适当调整句式或使用指代词，避免短距离内反复重复「{noun}」"
                    ))
                    break

    def _check_actionable_items(self, text: str, res: LintResult):
        has_checklist = bool(re.search(r"-\s*\[[\sXx]\]", text))
        has_action_item = bool(re.search(r"(?:单一行动项|行动项|立刻落地|Checklist|复用清单)", text))
        if not has_checklist and not has_action_item:
            res.issues.append(Issue(
                level="P1", code="P1_ACTION_ITEM_MISSING",
                message="缺少直接可上手的 Checklist 或单一行动项",
                suggestion="在文末增加读者看完即可照着操作的 Checklist 或 5 分钟单一行动项"
            ))
