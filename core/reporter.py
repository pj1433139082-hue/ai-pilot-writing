# -*- coding: utf-8 -*-
"""
诊断结果报告格式化输出器 (纯标准库)
支持控制台彩色输出与 Markdown 格式评审报告导出
"""

import sys
from typing import TextIO
from core.linter import LintResult, Issue

class Reporter:
    # ANSI 颜色标记 (若终端不支持可自动退化)
    USE_COLOR = sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False
    RED = "\033[91m" if USE_COLOR else ""
    YELLOW = "\033[93m" if USE_COLOR else ""
    GREEN = "\033[92m" if USE_COLOR else ""
    CYAN = "\033[96m" if USE_COLOR else ""
    BOLD = "\033[1m" if USE_COLOR else ""
    RESET = "\033[0m" if USE_COLOR else ""

    @classmethod
    def print_console(cls, result: LintResult, out: TextIO = sys.stdout):
        out.write(f"\n{cls.BOLD}=== AI 领航团文章规范检查报告 ==={cls.RESET}\n")
        out.write(f"目标文件: {cls.CYAN}{result.file_path}{cls.RESET}\n")

        p0_list = result.p0_issues
        p1_list = result.p1_issues

        if result.is_valid and not p1_list:
            out.write(f"\n{cls.GREEN}{cls.BOLD}✔ 完美通过！未发现任何 P0 阻断项或 P1 优化项。{cls.RESET}\n\n")
            return

        if p0_list:
            out.write(f"\n{cls.RED}{cls.BOLD}[P0 阻断项] 发现 {len(p0_list)} 处红线违规 (必须修复方可发布):{cls.RESET}\n")
            for idx, issue in enumerate(p0_list, 1):
                loc = f" (第 {issue.line} 行)" if issue.line else ""
                out.write(f"  {idx}. {cls.RED}[{issue.code}]{cls.RESET} {issue.message}{loc}\n")
                if issue.snippet:
                    out.write(f"     原文片段: \"{issue.snippet}\"\n")
                if issue.suggestion:
                    out.write(f"     💡 修复建议: {issue.suggestion}\n")

        if p1_list:
            out.write(f"\n{cls.YELLOW}{cls.BOLD}[P1 优化项] 发现 {len(p1_list)} 处文风与表达优化建议 (建议打磨):{cls.RESET}\n")
            for idx, issue in enumerate(p1_list, 1):
                loc = f" (第 {issue.line} 行)" if issue.line else ""
                out.write(f"  {idx}. {cls.YELLOW}[{issue.code}]{cls.RESET} {issue.message}{loc}\n")
                if issue.snippet:
                    out.write(f"     原文片段: \"{issue.snippet}\"\n")
                if issue.suggestion:
                    out.write(f"     💡 优化建议: {issue.suggestion}\n")

        out.write("\n" + "-" * 50 + "\n")
        if result.is_valid:
            out.write(f"结论: {cls.GREEN}{cls.BOLD}PASS (P0=0, P1={len(p1_list)}) - 符合领航团硬门禁要求{cls.RESET}\n\n")
        else:
            out.write(f"结论: {cls.RED}{cls.BOLD}REJECT (P0={len(p0_list)}, P1={len(p1_list)}) - 存在阻断红线，请按上述指引修复{cls.RESET}\n\n")

    @classmethod
    def to_markdown(cls, result: LintResult) -> str:
        status_badge = "✅ 通过" if result.is_valid else "❌ 打回重修"
        lines = [
            f"# 文章评审报告：{status_badge}",
            f"- **文件路径**: `{result.file_path}`",
            f"- **P0 阻断项**: {len(result.p0_issues)} 处",
            f"- **P1 优化项**: {len(result.p1_issues)} 处",
            "",
            "## 一、P0 阻断项（硬指标，发布前必须清零）",
        ]

        if not result.p0_issues:
            lines.append("✔ 未发现 P0 阻断性违规。")
        else:
            for idx, issue in enumerate(result.p0_issues, 1):
                loc = f"（第 {issue.line} 行）" if issue.line else ""
                lines.append(f"### {idx}. [{issue.code}] {issue.message} {loc}")
                if issue.snippet:
                    lines.append(f"> 原文：`{issue.snippet}`")
                if issue.suggestion:
                    lines.append(f"- **修改建议**：{issue.suggestion}")

        lines.extend([
            "",
            "## 二、P1 优化建议（文风去 AI 味与结构打磨）",
        ])

        if not result.p1_issues:
            lines.append("✔ 未发现明显优化项。")
        else:
            for idx, issue in enumerate(result.p1_issues, 1):
                loc = f"（第 {issue.line} 行）" if issue.line else ""
                lines.append(f"- **[{issue.code}]** {issue.message} {loc}")
                if issue.snippet:
                    lines.append(f"  - 原文片段：`{issue.snippet}`")
                if issue.suggestion:
                    lines.append(f"  - 建议：{issue.suggestion}")

        return "\n".join(lines)
