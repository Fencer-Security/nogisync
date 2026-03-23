import textwrap
from unittest import TestCase

from nogisync.markdown import (
    NOTION_MAX_LIST_DEPTH,
    convert_markdown_table_to_latex,
    parse_markdown_to_notion_blocks,
    process_inline_formatting,
    replace_content_that_is_too_long,
)


class TestConvertMarkdownTableToLatex(TestCase):
    def test_table_without_header(self):
        markdown_table = "| Cell 1 | Cell 2 |\n| Cell 3 | Cell 4 |"
        result = convert_markdown_table_to_latex(markdown_table)
        self.assertIn("\\begin{array}", result)
        self.assertIn("Cell 1", result)
        self.assertNotIn("\\textbf", result)

    def test_table_with_header(self):
        markdown_table = "| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1 | Cell 2 |"
        result = convert_markdown_table_to_latex(markdown_table)
        self.assertIn("\\begin{array}", result)
        self.assertIn("\\textbf{Header 1}", result)
        self.assertIn("Cell 1", result)
        self.assertIn("\\end{array}", result)

    def test_table_with_bold_header(self):
        markdown_table = "| **Header 1** | **Header 2** |\n|----------|----------|\n| Cell 1 | Cell 2 |"
        result = convert_markdown_table_to_latex(markdown_table)
        self.assertIn("\\textbf{Header 1}", result)

    def test_single_line_table(self):
        markdown_table = "| Cell 1 | Cell 2 |"
        result = convert_markdown_table_to_latex(markdown_table)
        self.assertIn("\\begin{array}", result)
        self.assertIn("Cell 1", result)
        self.assertIn("\\end{array}", result)
        self.assertNotIn("\\textbf", result)


class TestParseBlocks(TestCase):
    def test_empty_string(self):
        self.assertEqual(parse_markdown_to_notion_blocks(""), [])

    def test_paragraph(self):
        result = parse_markdown_to_notion_blocks("plain text")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "paragraph")

    def test_heading_levels(self):
        text = "# H1\n## H2\n### H3\n#### H4"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["type"], "heading_1")
        self.assertEqual(result[0]["heading_1"]["rich_text"][0]["text"]["content"], "H1")
        self.assertEqual(result[1]["type"], "heading_2")
        self.assertEqual(result[2]["type"], "heading_3")

    def test_horizontal_line(self):
        result = parse_markdown_to_notion_blocks("---\n")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "divider")

    def test_blockquote(self):
        result = parse_markdown_to_notion_blocks("> This is a quote")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "quote")
        self.assertEqual(result[0]["quote"]["rich_text"][0]["text"]["content"], "This is a quote")

    def test_code_block(self):
        blocks = parse_markdown_to_notion_blocks("```python\nprint('hello')\n```")
        self.assertEqual(blocks[0]["type"], "code")
        self.assertEqual(blocks[0]["code"]["language"], "python")
        self.assertIn("print('hello')", blocks[0]["code"]["rich_text"][0]["text"]["content"])

    def test_code_block_unsupported_language_falls_back_to_plain_text(self):
        blocks = parse_markdown_to_notion_blocks("```text\nhello\n```")
        self.assertEqual(blocks[0]["code"]["language"], "plain text")

    def test_code_block_supported_language_preserved(self):
        for lang in ("mermaid", "sql", "typescript", "yaml"):
            blocks = parse_markdown_to_notion_blocks(f"```{lang}\ncontent\n```")
            self.assertEqual(blocks[0]["code"]["language"], lang)

    def test_indented_code_flushed_by_regular_line(self):
        result = parse_markdown_to_notion_blocks("    code line\nregular line")
        self.assertEqual(result[0]["type"], "code")
        self.assertEqual(result[0]["code"]["language"], "plain text")
        self.assertEqual(result[0]["code"]["rich_text"][0]["text"]["content"], "code line")
        self.assertEqual(result[1]["type"], "paragraph")

    def test_indented_code_at_end_of_file(self):
        result = parse_markdown_to_notion_blocks("Paragraph\n    code line 1\n    code line 2")
        self.assertEqual(result[0]["type"], "paragraph")
        self.assertEqual(result[1]["type"], "code")
        self.assertEqual(result[1]["code"]["rich_text"][0]["text"]["content"], "code line 1\ncode line 2")

    def test_image_with_caption(self):
        result = parse_markdown_to_notion_blocks("![My caption](https://example.com/image.png)")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "image")
        self.assertEqual(result[0]["image"]["external"]["url"], "https://example.com/image.png")
        self.assertEqual(result[0]["image"]["caption"][0]["text"]["content"], "My caption")

    def test_image_without_caption(self):
        result = parse_markdown_to_notion_blocks("![](https://example.com/image.png)")
        self.assertEqual(result[0]["type"], "image")
        self.assertNotIn("caption", result[0]["image"])

    def test_image_relative_url_becomes_paragraph(self):
        result = parse_markdown_to_notion_blocks("![diagram](./architecture.png)")
        self.assertEqual(result[0]["type"], "paragraph")

    def test_image_http_url_accepted(self):
        result = parse_markdown_to_notion_blocks("![](http://example.com/img.png)")
        self.assertEqual(result[0]["type"], "image")

    def test_empty_lines_filtered(self):
        result = parse_markdown_to_notion_blocks("**bold** \n\n *italic*")
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0]["paragraph"]["rich_text"][0]["annotations"]["bold"])
        self.assertTrue(result[1]["paragraph"]["rich_text"][1]["annotations"]["italic"])

    def test_mixed_content(self):
        blocks = parse_markdown_to_notion_blocks("# Title\nParagraph\n```code\nblock\n```\n- List item")
        self.assertEqual(blocks[0]["type"], "heading_1")
        self.assertEqual(blocks[1]["type"], "paragraph")
        self.assertEqual(blocks[2]["type"], "code")
        self.assertEqual(blocks[3]["type"], "bulleted_list_item")

    def test_latex_block(self):
        result = parse_markdown_to_notion_blocks("$$x^2 + y^2 = z^2$$")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "equation")
        self.assertEqual(result[0]["equation"]["expression"], "x^2 + y^2 = z^2")

    def test_multiline_latex_block(self):
        result = parse_markdown_to_notion_blocks("$$\n\\frac{a}{b}\n$$")
        self.assertEqual(result[0]["type"], "equation")
        self.assertIn("\\frac{a}{b}", result[0]["equation"]["expression"])


class TestParseTables(TestCase):
    def test_table_with_header(self):
        text = "| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1 | Cell 2 |"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "equation")
        self.assertIn("\\textbf{Header 1}", result[0]["equation"]["expression"])

    def test_table_no_header(self):
        text = "| Cell 1 | Cell 2 |\n| Cell 3 | Cell 4 |"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(result[0]["type"], "equation")
        latex = result[0]["equation"]["expression"]
        self.assertIn("\\textsf{Cell 1}", latex)
        self.assertNotIn("\\textbf", latex)

    def test_table_followed_by_content(self):
        text = "| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1 | Cell 2 |\n\nParagraph after table"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(result[0]["type"], "equation")
        self.assertEqual(result[1]["type"], "paragraph")


class TestParseLists(TestCase):
    def test_nested_bulleted_lists(self):
        result = parse_markdown_to_notion_blocks("- Item 1\n  - Nested 1\n    - Nested 2\n- Item 2")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"], "Item 1")

        nested1 = result[0]["bulleted_list_item"]["children"][0]
        self.assertEqual(nested1["bulleted_list_item"]["rich_text"][0]["text"]["content"], "Nested 1")

        nested2 = nested1["bulleted_list_item"]["children"][0]
        self.assertEqual(nested2["bulleted_list_item"]["rich_text"][0]["text"]["content"], "Nested 2")

    def test_nested_numbered_lists(self):
        result = parse_markdown_to_notion_blocks("1. First\n  1. Nested 1\n    1. Nested 2\n2. Second")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["numbered_list_item"]["rich_text"][0]["text"]["content"], "First")

        nested1 = result[0]["numbered_list_item"]["children"][0]
        self.assertEqual(nested1["numbered_list_item"]["rich_text"][0]["text"]["content"], "Nested 1")

        nested2 = nested1["numbered_list_item"]["children"][0]
        self.assertEqual(nested2["numbered_list_item"]["rich_text"][0]["text"]["content"], "Nested 2")

    def test_numbered_with_nested_bulleted(self):
        text = textwrap.dedent("""
            1. **First Numbered List Item**:
               - First nested bulleted list item.
            2. **Second Numbered List Item**:
               - Second nested bulleted list item.
            3. **Third Numbered List Item**:
               - Third nested bulleted list item.
        """)
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 3)
        for i, (parent_text, child_text) in enumerate(
            [
                ("First Numbered List Item", "First nested bulleted list item."),
                ("Second Numbered List Item", "Second nested bulleted list item."),
                ("Third Numbered List Item", "Third nested bulleted list item."),
            ]
        ):
            self.assertEqual(result[i]["type"], "numbered_list_item")
            self.assertEqual(result[i]["numbered_list_item"]["rich_text"][0]["text"]["content"], parent_text)
            child = result[i]["numbered_list_item"]["children"][0]
            self.assertEqual(child["type"], "bulleted_list_item")
            self.assertEqual(child["bulleted_list_item"]["rich_text"][0]["text"]["content"], child_text)

    def test_bulleted_with_nested_numbered(self):
        text = textwrap.dedent("""
            - **First Bulleted List Item**:
               1. First nested numbered list item.
            - **Second Bulleted List Item**:
               1. Second nested numbered list item.
            - **Third Bulleted List Item**:
               1. Third nested numbered list item.
        """)
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 3)
        for i, (parent_text, child_text) in enumerate(
            [
                ("First Bulleted List Item", "First nested numbered list item."),
                ("Second Bulleted List Item", "Second nested numbered list item."),
                ("Third Bulleted List Item", "Third nested numbered list item."),
            ]
        ):
            self.assertEqual(result[i]["type"], "bulleted_list_item")
            self.assertEqual(result[i]["bulleted_list_item"]["rich_text"][0]["text"]["content"], parent_text)
            child = result[i]["bulleted_list_item"]["children"][0]
            self.assertEqual(child["type"], "numbered_list_item")
            self.assertEqual(child["numbered_list_item"]["rich_text"][0]["text"]["content"], child_text)


class TestListNestingDepthLimit(TestCase):
    def test_bulleted_list_capped_at_max_depth(self):
        lines = []
        for i in range(NOTION_MAX_LIST_DEPTH + 2):
            lines.append("  " * i + f"- Level {i}")
        result = parse_markdown_to_notion_blocks("\n".join(lines))

        # Walk down the nesting to verify depth is capped
        node = result[0]
        depth = 1
        while "children" in node.get("bulleted_list_item", {}):
            node = node["bulleted_list_item"]["children"][0]
            depth += 1
        self.assertLessEqual(depth, NOTION_MAX_LIST_DEPTH)

    def test_numbered_list_capped_at_max_depth(self):
        lines = []
        for i in range(NOTION_MAX_LIST_DEPTH + 2):
            lines.append("  " * i + f"{i + 1}. Level {i}")
        result = parse_markdown_to_notion_blocks("\n".join(lines))

        node = result[0]
        depth = 1
        while "children" in node.get("numbered_list_item", {}):
            node = node["numbered_list_item"]["children"][0]
            depth += 1
        self.assertLessEqual(depth, NOTION_MAX_LIST_DEPTH)


class TestNestedListFallback(TestCase):
    def test_numbered_list_nested_after_non_list_item(self):
        text = textwrap.dedent("""\
            - Parent item
            Continuation paragraph
                1. Nested numbered item""")
        result = parse_markdown_to_notion_blocks(text)
        types = [b["type"] for b in result]
        self.assertIn("numbered_list_item", types)

    def test_bulleted_list_nested_after_non_list_item(self):
        text = textwrap.dedent("""\
            - Parent item
            Continuation paragraph
                - Nested bulleted item""")
        result = parse_markdown_to_notion_blocks(text)
        types = [b["type"] for b in result]
        self.assertIn("bulleted_list_item", types)

    def test_multiline_list_item_with_nested_subitem(self):
        text = textwrap.dedent("""\
            - **Database Connection Scaling**: Multiple concurrent Lambda executions could exhaust database
              connections.
                - **Mitigation**: Set Lambda reserved concurrency limits initially.""")
        result = parse_markdown_to_notion_blocks(text)
        bullet_items = [b for b in result if b["type"] == "bulleted_list_item"]
        self.assertTrue(len(bullet_items) >= 2)


class TestInlineFormatting(TestCase):
    def test_plain_text(self):
        result = process_inline_formatting("plain text")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "text")
        self.assertEqual(result[0]["text"]["content"], "plain text")

    def test_empty(self):
        self.assertEqual(process_inline_formatting(""), [])

    def test_empty_parts_filtered(self):
        result = process_inline_formatting("**bold**")
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["annotations"]["bold"])

    def test_bold(self):
        result = process_inline_formatting("This is **bold** text")
        self.assertEqual(result[1]["annotations"]["bold"], True)
        self.assertEqual(result[1]["text"]["content"], "bold")

    def test_italic(self):
        result = process_inline_formatting("This is *italic* text")
        self.assertEqual(result[1]["annotations"]["italic"], True)
        self.assertEqual(result[1]["text"]["content"], "italic")

    def test_bold_italic(self):
        result = process_inline_formatting("This is **_bold italic_** text")
        self.assertTrue(result[1]["annotations"]["bold"])
        self.assertTrue(result[1]["annotations"]["italic"])
        self.assertEqual(result[1]["text"]["content"], "bold italic")

        result = process_inline_formatting("This is __*bold italic*__ text")
        self.assertTrue(result[1]["annotations"]["bold"])
        self.assertTrue(result[1]["annotations"]["italic"])

    def test_code(self):
        result = process_inline_formatting("This is `code` text")
        self.assertEqual(result[1]["annotations"]["code"], True)
        self.assertEqual(result[1]["text"]["content"], "code")

    def test_strikethrough(self):
        result = process_inline_formatting("This is ~struck~ text")
        self.assertEqual(result[1]["annotations"]["strikethrough"], True)
        self.assertEqual(result[1]["text"]["content"], "struck")

    def test_link(self):
        result = process_inline_formatting("This is a [link](https://example.com)")
        self.assertEqual(result[1]["text"]["link"]["url"], "https://example.com")
        self.assertEqual(result[1]["text"]["content"], "link")

    def test_equation(self):
        result = process_inline_formatting("This is $x^2$ equation")
        self.assertEqual(result[1]["type"], "equation")
        self.assertEqual(result[1]["equation"]["expression"], "x^2")

    def test_multiple_formats(self):
        result = process_inline_formatting("Normal **bold** *italic* `code` [link](url) ~strike~ $math$")
        self.assertTrue(len(result) > 6)

    def test_nested_formats(self):
        result = process_inline_formatting("**Bold with *italic* inside**")
        self.assertTrue(any(part.get("annotations", {}).get("bold") for part in result))


class TestReplaceContentTooLong(TestCase):
    def test_long_content_replaced(self):
        result = replace_content_that_is_too_long("*" * 2001)
        self.assertEqual(
            result, "This content is too long to be displayed in Notion. There is a 2000 character limit currently."
        )
