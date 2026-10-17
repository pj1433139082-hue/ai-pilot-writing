# -*- coding: utf-8 -*-
"""
AI 领航团模板声明式插槽引擎 (Template Slot Engine)
纯 Python 3 标准库实现，支持元数据插槽水化、原型标题兼容处理与未解析插槽探测
"""

import re
from typing import Dict, List, Optional, Any


class TemplateRenderer:
    """声明式模板插槽渲染器"""

    # 正则表达式匹配 {{slot_name}}，兼容插槽内部的首尾空白字符
    SLOT_PATTERN = re.compile(r"\{\{\s*([^}\r\n]+?)\s*\}\}")

    @classmethod
    def render(cls, template_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        根据给定的 context 上下文字典渲染模板文本。
        - 水化元数据插槽：date, slug, author, author_name, topic, title, alias_1, alias_2 等。
        - 优雅处理文章标题占位符（如以「文章标题」为前缀的 {{文章标题：...}} 或精确键匹配）。
        - 遇到未在 context 中提供的业务插槽或可选占位符时不报错，保留原插槽供作者后续撰写。
        """
        if context is None:
            context = {}

        # 清洗 context 键的前后空格
        clean_context = {str(k).strip(): v for k, v in context.items()}

        def replace_slot(match: re.Match) -> str:
            raw_content = match.group(1)
            slot_name = raw_content.strip()

            # 1. 精确匹配 context 中的键（值非 None 时有效替换）
            if slot_name in clean_context and clean_context[slot_name] is not None:
                return str(clean_context[slot_name])
            if slot_name.lower() in clean_context and clean_context[slot_name.lower()] is not None:
                return str(clean_context[slot_name.lower()])

            # 2. 原型标题占位符处理：以 "文章标题" 为前缀或 slot_name == "title"
            if slot_name.startswith("文章标题") or slot_name == "title":
                if "title" in clean_context and clean_context["title"] is not None:
                    return str(clean_context["title"])
                if "文章标题" in clean_context and clean_context["文章标题"] is not None:
                    return str(clean_context["文章标题"])

            # 3. 作者别名兼容处理：author 与 author_name 互通
            if slot_name in ("author", "author_name"):
                if "author" in clean_context and clean_context["author"] is not None:
                    return str(clean_context["author"])
                if "author_name" in clean_context and clean_context["author_name"] is not None:
                    return str(clean_context["author_name"])

            # 4. alias_1 与 alias_2 的自动推导（若 context 未显式提供）
            if slot_name == "alias_1":
                if "alias_1" in clean_context and clean_context["alias_1"] is not None:
                    return str(clean_context["alias_1"])
                if "date" in clean_context and "slug" in clean_context:
                    if clean_context["date"] is not None and clean_context["slug"] is not None:
                        return f"{clean_context['date']}-{clean_context['slug']}"

            if slot_name == "alias_2":
                if "alias_2" in clean_context and clean_context["alias_2"] is not None:
                    return str(clean_context["alias_2"])
                if "title" in clean_context and clean_context["title"] is not None:
                    return str(clean_context["title"])
                if "文章标题" in clean_context and clean_context["文章标题"] is not None:
                    return str(clean_context["文章标题"])

            # 5. 未在 context 中提供的业务插槽或可选占位符，保留原插槽供作者后续撰写
            return match.group(0)

        return cls.SLOT_PATTERN.sub(replace_slot, template_text)

    @classmethod
    def find_unresolved_slots(cls, content: str, unique: bool = False) -> List[str]:
        """
        探测文本中残留的未解析插槽 {{slot}}。
        - 去除插槽两端的空白字符。
        - 若 unique=True 则去重且保留首次出现顺序，默认返回所有出现的插槽名称。
        """
        slots = [m.strip() for m in cls.SLOT_PATTERN.findall(content) if m.strip()]
        if unique:
            return list(dict.fromkeys(slots))
        return slots
