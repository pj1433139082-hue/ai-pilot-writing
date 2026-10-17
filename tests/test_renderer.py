# -*- coding: utf-8 -*-
"""
AI 领航团模板插槽引擎单元测试 (tests/test_renderer.py)
验证 TemplateRenderer 的插槽解析、元数据水化、原型标题前缀匹配及未解析插槽探测
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.renderer import TemplateRenderer

TEMPLATES_DIR = BASE_DIR / "templates"


class TestTemplateRenderer(unittest.TestCase):
    def setUp(self):
        self.renderer = TemplateRenderer()
        self.sample_template = (
            "---\n"
            "title: {{date}}-{{slug}}\n"
            "tags: [kind/article, topic/ai-pilot, topic/{{topic}}]\n"
            "aliases: [{{alias_1}}, {{alias_2}}]\n"
            "created: {{date}}\n"
            "updated: {{date}}\n"
            "date: {{date}}\n"
            "status: draft\n"
            "author: {{author}}\n"
            "---\n\n"
            "# {{title}}\n\n"
            "> 业务场景：{{business_scene}}\n"
        )

    def test_render_full_context(self):
        """测试全量上下文渲染，所有插槽均被水化"""
        context = {
            "date": "2026-10-18",
            "slug": "impact-agent",
            "author": "张工",
            "topic": "business",
            "title": "污水厂进水冲击处置AI顾问落地实录",
            "alias_1": "2026-10-18-impact-agent",
            "alias_2": "污水厂进水冲击处置AI顾问落地实录",
            "business_scene": "进水冲击处置",
        }
        rendered = self.renderer.render(self.sample_template, context)

        self.assertNotIn("{{", rendered)
        self.assertNotIn("}}", rendered)
        self.assertIn("title: 2026-10-18-impact-agent", rendered)
        self.assertIn("author: 张工", rendered)
        self.assertIn("# 污水厂进水冲击处置AI顾问落地实录", rendered)
        self.assertIn("> 业务场景：进水冲击处置", rendered)

        unresolved = self.renderer.find_unresolved_slots(rendered)
        self.assertEqual(unresolved, [])

    def test_render_partial_context_retains_business_slots(self):
        """测试部分上下文渲染（仅元数据），业务插槽保留供作者填报"""
        context = {
            "date": "2026-10-18",
            "slug": "impact-agent",
            "author": "李工",
            "topic": "business",
            "title": "进水冲击处置实录",
        }
        rendered = self.renderer.render(self.sample_template, context)

        # 元数据应已成功水化
        self.assertIn("title: 2026-10-18-impact-agent", rendered)
        self.assertIn("author: 李工", rendered)
        self.assertIn("# 进水冲击处置实录", rendered)
        # 未提供的业务插槽应保留原样
        self.assertIn("{{business_scene}}", rendered)

        # 检查未解析插槽清单
        unresolved = self.renderer.find_unresolved_slots(rendered)
        self.assertIn("business_scene", unresolved)
        self.assertNotIn("title", unresolved)
        self.assertNotIn("date", unresolved)
        self.assertNotIn("author", unresolved)

    def test_render_archetype_title_prefix(self):
        """测试原型标题占位符（如 {{文章标题：...}}）通过前缀或精确键水化"""
        tmpl = "# {{文章标题：名词短语，如「污水厂进水冲击处置AI顾问落地实录」，禁止使用「浅谈/初探/关于」}}\n"
        context = {"title": "污水厂进水冲击处置AI顾问落地实录"}
        rendered = self.renderer.render(tmpl, context)
        self.assertEqual(rendered, "# 污水厂进水冲击处置AI顾问落地实录\n")

        # 亦支持精确 key 覆盖
        exact_key = "文章标题：名词短语，如「污水厂进水冲击处置AI顾问落地实录」，禁止使用「浅谈/初探/关于」"
        rendered_exact = self.renderer.render(tmpl, {exact_key: "自定义精确标题"})
        self.assertEqual(rendered_exact, "# 自定义精确标题\n")

    def test_render_author_aliases(self):
        """测试 author 与 author_name 互相容错水化"""
        tmpl = "author: {{author}} | author_name: {{author_name}}"

        # context 仅给 author
        r1 = self.renderer.render(tmpl, {"author": "王工"})
        self.assertEqual(r1, "author: 王工 | author_name: 王工")

        # context 仅给 author_name
        r2 = self.renderer.render(tmpl, {"author_name": "赵工"})
        self.assertEqual(r2, "author: 赵工 | author_name: 赵工")

    def test_render_alias_derivation(self):
        """测试 alias_1 与 alias_2 在未显式提供时的自动推导"""
        tmpl = "aliases: [{{alias_1}}, {{alias_2}}]"
        context = {
            "date": "2026-10-18",
            "slug": "demo-tool",
            "title": "办公工具选型指引",
        }
        rendered = self.renderer.render(tmpl, context)
        self.assertEqual(rendered, "aliases: [2026-10-18-demo-tool, 办公工具选型指引]")

        # 若显式传入则优先使用显式值
        context_override = {
            "date": "2026-10-18",
            "slug": "demo-tool",
            "title": "办公工具选型指引",
            "alias_1": "custom-alias-1",
            "alias_2": "custom-alias-2",
        }
        rendered_override = self.renderer.render(tmpl, context_override)
        self.assertEqual(rendered_override, "aliases: [custom-alias-1, custom-alias-2]")

    def test_find_unresolved_slots_raw_template(self):
        """测试对原始模板解析出所有待填充插槽，且去除插槽两端空白"""
        tmpl = "Hello {{ title }} and {{   date   }} and {{business_scene}} and {{ title }}"
        slots = self.renderer.find_unresolved_slots(tmpl)
        self.assertEqual(slots, ["title", "date", "business_scene", "title"])

        unique_slots = self.renderer.find_unresolved_slots(tmpl, unique=True)
        self.assertEqual(unique_slots, ["title", "date", "business_scene"])

    def test_find_unresolved_slots_on_template_files(self):
        """测试对实际标准模板文件进行插槽扫描"""
        biz_file = TEMPLATES_DIR / "template-business-agent.md"
        tool_file = TEMPLATES_DIR / "template-tool-guide.md"

        self.assertTrue(biz_file.exists(), f"Missing template: {biz_file}")
        self.assertTrue(tool_file.exists(), f"Missing template: {tool_file}")

        biz_slots = self.renderer.find_unresolved_slots(biz_file.read_text(encoding="utf-8"))
        tool_slots = self.renderer.find_unresolved_slots(tool_file.read_text(encoding="utf-8"))

        # 必须包含规范化元数据插槽
        for req_slot in ["title", "date", "slug", "author", "topic", "alias_1", "alias_2"]:
            self.assertIn(req_slot, biz_slots, f"biz template missing slot: {req_slot}")
            self.assertIn(req_slot, tool_slots, f"tool template missing slot: {req_slot}")

        # 必须包含各自特征业务插槽
        self.assertIn("business_scene", biz_slots)
        self.assertIn("tool_list", tool_slots)

    def test_classmethod_and_instance_calls_equivalent(self):
        """测试类方法与实例方法调用一致性"""
        text = "Hello {{name}}"
        ctx = {"name": "World"}
        self.assertEqual(TemplateRenderer.render(text, ctx), self.renderer.render(text, ctx))
        self.assertEqual(
            TemplateRenderer.find_unresolved_slots("{{a}} {{b}}"),
            self.renderer.find_unresolved_slots("{{a}} {{b}}")
        )


if __name__ == "__main__":
    unittest.main()
