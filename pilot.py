#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 领航团写作脚手架与规范校验工具 (Pilot CLI)
提供模板新建、AI提示词导出、规范门禁校验、中央防重台账与 Obsidian 工作台同步功能。
仅使用 Python 3 标准库，无任何第三方包依赖。
"""

import os
import sys
import stat
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
from core.renderer import TemplateRenderer
from core.ledger import LedgerAdapter
from core.vault_sync import VaultSyncAdapter

TEMPLATES_DIR = BASE_DIR / "templates"
PROMPTS_DIR = BASE_DIR / "prompts"

# 目录批量检查超过该数量后，提示改用 --quiet，避免逐份报告把终端刷爆
CHECK_DIR_QUIET_HINT = 200

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

    # 1. 查重检测
    vault_path_arg = getattr(args, "vault_path", None)
    ledger = LedgerAdapter(vault_path=vault_path_arg)
    if title:
        matches = ledger.search_duplicate(title, threshold=0.5)
        if matches:
            print("\n" + "=" * 60)
            print("⚠️  [防重提醒] 发现可能重复或高度相似的历史文章/选题:")
            for m in matches:
                src_label = "已写清单" if m["table"] == "written" else "选题池"
                score_pct = f"{m['score'] * 100:.1f}%"
                print(f"  • [{src_label}] 相似度: {score_pct:>5s} | 《{m['title']}》")
            print("=" * 60 + "\n")

    # 2. 确定输出目标路径并检查覆盖
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

    # 3. 读取模板并水化元数据插槽
    with open(tmpl_file, "r", encoding="utf-8") as f:
        content = f.read()

    context = {
        "title": title,
        "date": today_str,
        "slug": slug,
        "author": author,
        "author_name": author,
        "topic": t_type,
        "alias_1": f"{today_str}-{slug}",
        "alias_2": title,
    }
    rendered = TemplateRenderer.render(content, context)

    # 4. 写入目标草稿文件
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"✔ 成功创建文章草稿: {dest_path}")
    print(f"  - 体裁: {tmpl_info['name']}")
    print(f"  - 作者: {author}")

    # 5. 原子化登记防重台账
    if not getattr(args, "no_register", False):
        reg_res = ledger.register_draft(
            title=title,
            file_name=dest_path.name,
            author=author,
            date=today_str,
        )
        if reg_res.get("registered"):
            print(f"✔ 已在中央防重台账中登记草稿: 《{title}》 ({dest_path.name})")
            if reg_res.get("removed_from_pool"):
                for p_item in reg_res["removed_from_pool"]:
                    print(f"  - 已从选题池中移出命中条目: 《{p_item}》")
        elif reg_res.get("snapshot_fallback"):
            print(f"ℹ️  [快照兜底] {reg_res.get('notice')}")
        else:
            print(f"ℹ️  台账登记反馈: {reg_res.get('notice', '')}")
    else:
        print("ℹ️  [--no-register] 跳过中央台账登记")

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
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"✔ 提示词已导出至: {out_p}")
    else:
        print(text)
    return 0


# Windows 目录联结 / 符号链接的重解析标记；非 Windows 上为空元组，不做额外检查
_REPARSE_TAGS_TO_SKIP = tuple(
    tag
    for tag in (
        getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", None),
        getattr(stat, "IO_REPARSE_TAG_SYMLINK", None),
    )
    if tag is not None
)


def _is_linked_dir(path: Path) -> bool:
    """判断目录是否是符号链接或 Windows 目录联结 (junction)"""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return getattr(st, "st_reparse_tag", 0) in _REPARSE_TAGS_TO_SKIP


def _iter_md_files(target: Path):
    """流式枚举目录下的 Markdown 文件

    不使用 sorted(target.glob("**/*.md"))：那需要先把整棵树的匹配结果全部物化
    并排序后才进入打印循环，在真实笔记库上会长时间零输出（实测 29,794 个文件
    仅枚举就要 ~48 秒）。这里改为边遍历边产出，首份报告立即可见。

    同时跳过符号链接与 Windows 目录联结：os.walk(followlinks=False) 只跳过
    os.path.islink() 为真的项，而目录联结（junction）不是符号链接、会被照常
    深入，一旦指回上层就会把文件数放大数十倍（实测 2,000 个文件膨胀成 78,000
    个路径，check 从 30 秒变成 14 分钟）。
    """
    for root, dirnames, filenames in os.walk(target):
        if _REPARSE_TAGS_TO_SKIP:
            dirnames[:] = sorted(
                d for d in dirnames if not _is_linked_dir(Path(root) / d)
            )
        else:
            dirnames.sort()
        for name in sorted(filenames):
            if name.endswith(".md"):
                yield Path(root) / name


def cmd_check(args):
    """运行规范检查器"""
    target = Path(args.target).resolve()
    if not target.exists():
        print(f"❌ 错误: 目标文件或目录不存在: {target}")
        return 1

    mode = "publish" if getattr(args, "publish", False) or args.mode == "publish" else "draft"
    quiet = getattr(args, "quiet", False)
    is_dir = target.is_dir()

    linter = PilotLinter()
    has_failure = False
    checked = 0
    failed = 0
    hinted = False

    files_to_check = _iter_md_files(target) if is_dir else iter([target])

    for file_p in files_to_check:
        res = linter.lint_file(str(file_p), mode=mode)
        checked += 1
        if not res.is_valid:
            has_failure = True
            failed += 1

        if args.md:
            print(Reporter.to_markdown(res))
        elif quiet:
            flag = "PASS" if res.is_valid else "FAIL"
            print(f"{flag}  P0={len(res.p0_issues)} P1={len(res.p1_issues)}  {file_p}")
        else:
            Reporter.print_console(res)
            if is_dir and not hinted and checked >= CHECK_DIR_QUIET_HINT:
                hinted = True
                print(
                    f"ℹ️  已检查 {checked} 个文件，逐份打印会非常慢；"
                    "大目录建议改用 `--quiet` 只看结论，或用 `--md` 导出报告。",
                    file=sys.stderr
                )

    if checked == 0:
        print(f"未在 {target} 找到 Markdown 文件")
        return 0

    if quiet:
        print(f"\n汇总: 共检查 {checked} 个文件，通过 {checked - failed} 个，未通过 {failed} 个。")

    return 1 if has_failure else 0


def cmd_sync_vault(args):
    """将模板同步到本地 Obsidian 工作台模板目录"""
    vault_path_arg = getattr(args, "vault_path", None)
    result = VaultSyncAdapter.sync(
        TEMPLATES_DIR,
        vault_path=vault_path_arg,
        overwrite=args.overwrite,
        show_diff=args.diff,
    )
    print(VaultSyncAdapter.format_summary(result))
    if result.get("missing", 0) > 0:
        return 1
    return 0


def cmd_list(args):
    """列出可用模板、配套提示词与中央防重台账状态"""
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

    print("=== 中央防重台账状态 ===")
    vault_path_arg = getattr(args, "vault_path", None)
    ledger = LedgerAdapter(vault_path=vault_path_arg)
    if ledger.is_vault_available:
        print(f"  状态       : 🟢 中央台账正常连接")
        print(f"  台账路径   : {ledger.ledger_path}")
    else:
        print(f"  状态       : 🟡 离线快照兜底模式 (中央台账不可达)")
        print(f"  快照路径   : {ledger.snapshot_path}")

    try:
        data = ledger.parse_ledger()
        written_count = len(data.get("written", []))
        pool_count = len(data.get("pool", []))
        print(f"  已写文章数 : {written_count} 篇")
        print(f"  选题池储备 : {pool_count} 条")
    except Exception as e:
        print(f"  数据解析异常: {e}")
    print()
    return 0


def main(argv=None):
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
    p_new.add_argument("--no-register", action="store_true", help="仅生成本地草稿，不登记中央台账")
    p_new.add_argument("--vault-path", default=None, help="Obsidian 工作台路径或台账路径")

    # prompt 子命令
    p_prompt = subparsers.add_parser("prompt", help="导出或查看配套的 AI 起草/评审提示词")
    p_prompt.add_argument("-t", "--type", default="business", choices=["business", "tool", "audit"], help="提示词类型 (business|tool|audit)")
    p_prompt.add_argument("-o", "--output", default="", help="输出到指定文件 (默认直接打印到控制台)")

    # check 子命令
    p_check = subparsers.add_parser("check", help="自检文章是否符合领航团 P0 硬红线与 P1 优化项")
    p_check.add_argument("target", help="待检查的 Markdown 文件或目录路径")
    p_check.add_argument("--mode", choices=["draft", "publish"], default="draft", help="校验模式 (draft: 草稿阶段放宽字数与槽位, publish: 终审全量门禁)")
    p_check.add_argument("--publish", action="store_true", help="快捷启用 publish 终审门禁模式 (等价于 --mode publish)")
    p_check.add_argument("--md", action="store_true", help="以 Markdown 格式输出评审报告")
    p_check.add_argument("--quiet", action="store_true", help="目录批量检查时只输出每个文件的 PASS/FAIL 与汇总，避免逐份报告刷屏")

    # sync-vault 子命令
    p_sync = subparsers.add_parser("sync-vault", help="同步最新模板至 Obsidian 工作台")
    p_sync.add_argument("--vault-path", default=None, help="显式指定 Obsidian 工作台路径")
    p_sync.add_argument("--overwrite", action="store_true", help="强制覆盖已就地修改的目标模板")
    p_sync.add_argument("--diff", action="store_true", help="显示模板变更 unified diff 差异详情")

    # list 子命令
    p_list = subparsers.add_parser("list", help="查看所有可用模板、提示词与防重台账状态")
    p_list.add_argument("--vault-path", default=None, help="显式指定 Obsidian 工作台路径")

    args = parser.parse_args(argv)
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
