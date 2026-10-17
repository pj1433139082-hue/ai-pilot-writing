#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 领航团写作脚手架与规范校验工具 (Pilot CLI)
提供模板新建、AI提示词导出、规范门禁校验与 Obsidian 工作台同步功能。
仅使用 Python 3 标准库，无任何第三方包依赖。
"""

import os
import sys
import argparse
import datetime
import shutil
from pathlib import Path

# 添加当前目录至 sys.path，保证子模块可导入
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.linter import PilotLinter
from core.reporter import Reporter

TEMPLATES_DIR = BASE_DIR / "templates"
PROMPTS_DIR = BASE_DIR / "prompts"
VAULT_TEMPLATE_DIR = Path(r"D:\obsidian_work\cangku\paper_work\工作台\模板")

TEMPLATE_MAP = {
    "business": {
        "file": "template-business-agent.md",
        "name": "业务实战与智能体落地模板",
        "vault_name": "AI领航团-业务实战型模板.md",
        "desc": "适用于水务现场、大区运营、工艺处置、流程自动化等真实智能体落地与经验沉淀"
    },
    "tool": {
        "file": "template-tool-guide.md",
        "name": "工具选型与评测避坑模板",
        "vault_name": "AI领航团-工具避坑型模板.md",
        "desc": "适用于办公 AI 工具、行业大模型、开发辅助工具的横向对比、避坑测评与落地打法"
    }
}

PROMPT_MAP = {
    "business": "draft-business-agent.md",
    "tool": "draft-tool-guide.md",
    "audit": "audit-pilot-article.md"
}

def cmd_new(args):
    """根据体裁从模板创建新草稿"""
    t_type = args.type.lower()
    if t_type not in TEMPLATE_MAP:
        print(f"❌ 错误: 未知模板类型 '{t_type}'，可选类型: {', '.join(TEMPLATE_MAP.keys())}")
        return 1

    tmpl_info = TEMPLATE_MAP[t_type]
    tmpl_file = TEMPLATES_DIR / tmpl_info["file"]
    if not tmpl_file.exists():
        print(f"❌ 错误: 模板文件不存在: {tmpl_file}")
        return 1

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    slug = args.slug.strip() if args.slug else f"{t_type}-article"
    author = args.author.strip() if args.author else "领航团成员"
    title = args.title.strip() if args.title else f"新{tmpl_info['name']}"

    if args.output:
        dest_path = Path(args.output).resolve()
    else:
        drafts_dir = BASE_DIR / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        dest_path = drafts_dir / f"{today_str}-{slug}.md"

    if dest_path.exists() and not args.force:
        print(f"⚠️ 文件已存在: {dest_path}")
        print("如需覆盖请加上 --force 参数")
        return 1

    with open(tmpl_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 替换常见占位符
    content = content.replace("{{date}}", today_str)
    content = content.replace("{{slug}}", slug)
    content = content.replace("{{author_name}}", author)
    content = content.replace("{{topic}}", t_type)
    content = content.replace("{{alias_1}}", f"{today_str}-{slug}")
    content = content.replace("{{alias_2}}", title)
    content = content.replace("{{文章标题：名词短语，如「污水厂进水冲击处置AI顾问落地实录」，禁止使用「浅谈/初探/关于」}}", title)
    content = content.replace("{{文章标题：名词短语，如「大模型与办公提效工具选型指引与避坑实录」，禁止使用「浅谈/初探/关于」}}", title)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✔ 成功创建文章草稿: {dest_path}")
    print(f"  - 体裁: {tmpl_info['name']}")
    print(f"  - 作者: {author}")
    print(f"  - 校验提示: 编写完成后可运行 `python pilot.py check {dest_path}` 自检")
    return 0

def cmd_prompt(args):
    """导出或查看配套的 AI 起草/评审提示词"""
    p_type = args.type.lower()
    if p_type not in PROMPT_MAP:
        print(f"❌ 错误: 未知提示词类型 '{p_type}'，可选类型: {', '.join(PROMPT_MAP.keys())}")
        return 1

    prompt_file = PROMPTS_DIR / PROMPT_MAP[p_type]
    if not prompt_file.exists():
        print(f"❌ 错误: 提示词文件不存在: {prompt_file}")
        return 1

    with open(prompt_file, "r", encoding="utf-8") as f:
        text = f.read()

    if args.output:
        out_p = Path(args.output).resolve()
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"✔ 提示词已导出至: {out_p}")
    else:
        print(text)
    return 0

def cmd_check(args):
    """运行规范检查器"""
    target = Path(args.target).resolve()
    if not target.exists():
        print(f"❌ 错误: 目标文件或目录不存在: {target}")
        return 1

    linter = PilotLinter()
    has_failure = False

    files_to_check = []
    if target.is_dir():
        files_to_check = sorted(target.glob("**/*.md"))
    else:
        files_to_check = [target]

    if not files_to_check:
        print(f"未在 {target} 找到 Markdown 文件")
        return 0

    for file_p in files_to_check:
        res = linter.lint_file(str(file_p))
        if args.md:
            print(Reporter.to_markdown(res))
        else:
            Reporter.print_console(res)
        if not res.is_valid:
            has_failure = True

    return 1 if has_failure else 0

def cmd_sync_vault(args):
    """将模板同步到本地 Obsidian 工作台模板目录"""
    if not VAULT_TEMPLATE_DIR.exists():
        print(f"⚠️ Obsidian 模板目录不存在: {VAULT_TEMPLATE_DIR}")
        print("正在尝试创建目标目录...")
        try:
            VAULT_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"❌ 无法创建目录: {e}")
            return 1

    synced_count = 0
    for key, info in TEMPLATE_MAP.items():
        src = TEMPLATES_DIR / info["file"]
        dst = VAULT_TEMPLATE_DIR / info["vault_name"]
        if src.exists():
            shutil.copy2(src, dst)
            print(f"✔ 已同步模板: {src.name} -> {dst}")
            synced_count += 1
        else:
            print(f"⚠️ 警告: 源模板不存在: {src}")

    # 同时同步 prompts 到工作台的提示词库 (如果存在工作台自治/工作流目录)
    print(f"\n🎉 模板同步完毕，共同步 {synced_count} 个模板至 Obsidian 工作台。")
    return 0

def cmd_list(args):
    """列出可用模板与提示词"""
    print("\n=== 可用文章模板 ===")
    for key, info in TEMPLATE_MAP.items():
        print(f"- {key:10s} : {info['name']}")
        print(f"  说明       : {info['desc']}")
        print(f"  源文件     : templates/{info['file']}")
        print(f"  Vault 映射 : {info['vault_name']}\n")

    print("=== 配套 AI 提示词 (prompts/) ===")
    for key, filename in PROMPT_MAP.items():
        print(f"- {key:10s} : prompts/{filename}")
    print()
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="AI 领航团写作脚手架与规范校验工具 (Pilot CLI)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # new 子命令
    p_new = subparsers.add_parser("new", help="基于体裁模板初始化新文章草稿")
    p_new.add_argument("-t", "--type", default="business", choices=["business", "tool"], help="体裁类型 (默认: business)")
    p_new.add_argument("-T", "--title", default="", help="文章中文标题 (需具体名词短语，如「某厂进水冲击处置AI实录」)")
    p_new.add_argument("-a", "--author", default="领航团成员", help="作者姓名/工号/部门")
    p_new.add_argument("-s", "--slug", default="", help="英文/拼音标识，用作文件名 (默认自动生成)")
    p_new.add_argument("-o", "--output", default="", help="自定义输出文件路径")
    p_new.add_argument("-f", "--force", action="store_true", help="若文件已存在则强制覆盖")

    # prompt 子命令
    p_prompt = subparsers.add_parser("prompt", help="导出或查看配套的 AI 起草/评审提示词")
    p_prompt.add_argument("-t", "--type", default="business", choices=["business", "tool", "audit"], help="提示词类型")
    p_prompt.add_argument("-o", "--output", default="", help="输出到指定文件 (默认直接打印到控制台)")

    # check 子命令
    p_check = subparsers.add_parser("check", help="自检文章是否符合领航团 P0 硬红线与 P1 优化项")
    p_check.add_argument("target", help="待检查的 Markdown 文件或目录路径")
    p_check.add_argument("--md", action="store_true", help="以 Markdown 格式输出评审报告")

    # sync-vault 子命令
    p_sync = subparsers.add_parser("sync-vault", help="同步最新模板至 Obsidian 工作台")

    # list 子命令
    p_list = subparsers.add_parser("list", help="查看所有可用模板与提示词列表")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        "new": cmd_new,
        "prompt": cmd_prompt,
        "check": cmd_check,
        "sync-vault": cmd_sync_vault,
        "list": cmd_list
    }

    cmd_fn = dispatch.get(args.command)
    if cmd_fn:
        return cmd_fn(args)
    else:
        parser.print_help()
        return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
