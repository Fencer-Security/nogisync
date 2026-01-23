import textwrap
from unittest import TestCase

from nogisync.markdown import (
    convert_markdown_table_to_latex,
    parse_markdown_to_notion_blocks,
    process_inline_formatting,
    replace_content_that_is_too_long,
)


class TestMarkdown(TestCase):
    def test_convert_markdown_table_to_latex(self):
        # Test table without header
        markdown_table = "| Cell 1 | Cell 2 |\n| Cell 3 | Cell 4 |"
        result = convert_markdown_table_to_latex(markdown_table)
        self.assertIn("\\begin{array}", result)
        self.assertIn("Cell 1", result)
        self.assertNotIn("\\textbf", result)  # No bold headers

        # Test table with header
        markdown_table = "| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1 | Cell 2 |"
        result = convert_markdown_table_to_latex(markdown_table)
        self.assertIn("\\begin{array}", result)
        self.assertIn("\\textbf{Header 1}", result)
        self.assertIn("Cell 1", result)
        self.assertIn("\\end{array}", result)

        # Test table with bold header
        markdown_table = "| **Header 1** | **Header 2** |\n|----------|----------|\n| Cell 1 | Cell 2 |"
        result = convert_markdown_table_to_latex(markdown_table)
        self.assertIn("\\begin{array}", result)
        self.assertIn("\\textbf{Header 1}", result)
        self.assertIn("Cell 1", result)
        self.assertIn("\\end{array}", result)

    def test_convert_markdown_table_to_latex_single_line(self):
        # Test table with only one line (no newlines) - should not raise IndexError
        markdown_table = "| Cell 1 | Cell 2 |"
        result = convert_markdown_table_to_latex(markdown_table)
        self.assertIn("\\begin{array}", result)
        self.assertIn("Cell 1", result)
        self.assertIn("Cell 2", result)
        self.assertIn("\\end{array}", result)
        self.assertNotIn("\\textbf", result)  # No bold headers

    def test_parse_markdown_to_notion_blocks_blockquote(self):
        text = "> This is a quote"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "quote")
        self.assertEqual(result[0]["quote"]["rich_text"][0]["text"]["content"], "This is a quote")

    def test_parse_markdown_to_notion_blocks_code(self):
        markdown = "```python\nprint('hello')\n```"
        blocks = parse_markdown_to_notion_blocks(markdown)
        self.assertEqual(blocks[0]["type"], "code")
        self.assertEqual(blocks[0]["code"]["language"], "python")
        self.assertIn("print('hello')", blocks[0]["code"]["rich_text"][0]["text"]["content"])

    def test_parse_markdown_to_notion_blocks_empty_parts(self):
        # Test empty parts are filtered out
        text = "**bold** \n\n *italic*"  # Extra newlines create empty parts
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0]["paragraph"]["rich_text"][0]["annotations"]["bold"])
        self.assertTrue(result[1]["paragraph"]["rich_text"][1]["annotations"]["italic"])

    def test_parse_markdown_to_notion_blocks_empty_string(self):
        text = ""
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(result, [])

    def test_parse_markdown_to_notion_blocks_heading_levels(self):
        text = "# H1\n## H2\n### H3\n#### H4"  # H4 should be ignored
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["type"], "heading_1")
        self.assertEqual(result[0]["heading_1"]["rich_text"][0]["text"]["content"], "H1")
        self.assertEqual(result[1]["type"], "heading_2")
        self.assertEqual(result[1]["heading_2"]["rich_text"][0]["text"]["content"], "H2")
        self.assertEqual(result[2]["type"], "heading_3")
        self.assertEqual(result[2]["heading_3"]["rich_text"][0]["text"]["content"], "H3")

    def test_parse_markdown_to_notion_blocks_headings(self):
        markdown = "# Heading 1\n## Heading 2\n### Heading 3"
        blocks = parse_markdown_to_notion_blocks(markdown)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0]["type"], "heading_1")
        self.assertEqual(blocks[1]["type"], "heading_2")
        self.assertEqual(blocks[2]["type"], "heading_3")

    def test_parse_markdown_to_notion_blocks_horizontal_line(self):
        text = "---\n"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "divider")

    def test_parse_markdown_to_notion_blocks_image(self):
        text = "![alt text](https://example.com/image.jpg)"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "image")
        self.assertEqual(result[0]["image"]["external"]["url"], "https://example.com/image.jpg")

    def test_parse_markdown_to_notion_blocks_indented_code(self):
        text = "    code line 1\n    code line 2\n"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "code")
        self.assertEqual(result[0]["code"]["language"], "plain text")
        self.assertEqual(result[0]["code"]["rich_text"][0]["text"]["content"], "code line 1\ncode line 2")

    def test_parse_markdown_to_notion_blocks_indented_code_empty(self):
        # Test indented code block followed by non-indented line
        text = "    code line\nregular line"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["type"], "code")
        self.assertEqual(result[0]["code"]["rich_text"][0]["text"]["content"], "code line")
        self.assertEqual(result[1]["type"], "paragraph")

    def test_parse_markdown_to_notion_blocks_lists(self):
        markdown = "- Item 1\n  - Nested Item\n- Item 2"
        blocks = parse_markdown_to_notion_blocks(markdown)
        self.assertEqual(blocks[0]["type"], "bulleted_list_item")
        self.assertIn("children", blocks[0]["bulleted_list_item"])
        self.assertEqual(len(blocks), 2)

    def test_parse_markdown_to_notion_blocks_mixed_content(self):
        markdown = "# Title\nParagraph\n```code\nblock\n```\n- List item"
        blocks = parse_markdown_to_notion_blocks(markdown)
        self.assertTrue(len(blocks) > 3)
        self.assertEqual(blocks[0]["type"], "heading_1")
        self.assertEqual(blocks[1]["type"], "paragraph")
        self.assertEqual(blocks[2]["type"], "code")
        self.assertEqual(blocks[3]["type"], "bulleted_list_item")

    def test_parse_markdown_to_notion_blocks_nested_lists(self):
        text = "- Item 1\n  - Nested 1\n    - Nested 2\n- Item 2"
        result = parse_markdown_to_notion_blocks(text)

        # Check first level items
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["type"], "bulleted_list_item")
        self.assertEqual(result[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"], "Item 1")

        # Check nested items
        nested1 = result[0]["bulleted_list_item"]["children"][0]
        self.assertEqual(nested1["type"], "bulleted_list_item")
        self.assertEqual(nested1["bulleted_list_item"]["rich_text"][0]["text"]["content"], "Nested 1")

        nested2 = nested1["bulleted_list_item"]["children"][0]
        self.assertEqual(nested2["type"], "bulleted_list_item")
        self.assertEqual(nested2["bulleted_list_item"]["rich_text"][0]["text"]["content"], "Nested 2")

    def test_parse_markdown_to_notion_blocks_numbered_lists(self):
        text = "1. First\n  1. Nested 1\n    1. Nested 2\n2. Second"
        result = parse_markdown_to_notion_blocks(text)

        # Check first level items
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["type"], "numbered_list_item")
        self.assertEqual(result[0]["numbered_list_item"]["rich_text"][0]["text"]["content"], "First")

        # Check nested items
        nested1 = result[0]["numbered_list_item"]["children"][0]
        self.assertEqual(nested1["type"], "numbered_list_item")
        self.assertEqual(nested1["numbered_list_item"]["rich_text"][0]["text"]["content"], "Nested 1")

        nested2 = nested1["numbered_list_item"]["children"][0]
        self.assertEqual(nested2["type"], "numbered_list_item")
        self.assertEqual(nested2["numbered_list_item"]["rich_text"][0]["text"]["content"], "Nested 2")

    def test_parse_markdown_to_notion_blocks_table(self):
        text = "| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1 | Cell 2 |"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "equation")
        self.assertTrue("expression" in result[0]["equation"])

    def test_parse_markdown_to_notion_blocks_table_no_header(self):
        text = "| Cell 1 | Cell 2 |\n| Cell 3 | Cell 4 |"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "equation")
        latex = result[0]["equation"]["expression"]
        self.assertIn("\\textsf{Cell 1}", latex)
        self.assertNotIn("\\textbf", latex)

    def test_parse_markdown_to_notion_blocks_table_with_header(self):
        # Test table with header row
        text = "| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1 | Cell 2 |"
        result = parse_markdown_to_notion_blocks(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "equation")
        latex = result[0]["equation"]["expression"]
        self.assertIn("\\textbf{Header 1}", latex)
        self.assertIn("Cell 1", latex)

    def test_process_inline_formatting_bold(self):
        text = "This is **bold** text"
        result = process_inline_formatting(text)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1]["annotations"]["bold"], True)
        self.assertEqual(result[1]["text"]["content"], "bold")

    def test_process_inline_formatting_bold_italic(self):
        text = "This is **_bold italic_** text"
        result = process_inline_formatting(text)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1]["annotations"]["bold"], True)
        self.assertEqual(result[1]["annotations"]["italic"], True)
        self.assertEqual(result[1]["text"]["content"], "bold italic")

        text = "This is __*bold italic*__ text"
        result = process_inline_formatting(text)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1]["annotations"]["bold"], True)
        self.assertEqual(result[1]["annotations"]["italic"], True)
        self.assertEqual(result[1]["text"]["content"], "bold italic")

    def test_process_inline_formatting_code(self):
        text = "This is `code` text"
        result = process_inline_formatting(text)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1]["annotations"]["code"], True)
        self.assertEqual(result[1]["text"]["content"], "code")

    def test_process_inline_formatting_empty(self):
        text = ""
        result = process_inline_formatting(text)
        self.assertEqual(result, [])

    def test_process_inline_formatting_empty_parts(self):
        text = "**bold**"  # No text before or after
        result = process_inline_formatting(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["annotations"]["bold"], True)

    def test_process_inline_formatting_equation(self):
        text = "This is $x^2$ equation"
        result = process_inline_formatting(text)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1]["type"], "equation")
        self.assertEqual(result[1]["equation"]["expression"], "x^2")

    def test_process_inline_formatting_italic(self):
        text = "This is *italic* text"
        result = process_inline_formatting(text)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1]["annotations"]["italic"], True)
        self.assertEqual(result[1]["text"]["content"], "italic")

    def test_process_inline_formatting_link(self):
        text = "This is a [link](https://example.com)"
        result = process_inline_formatting(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["text"]["link"]["url"], "https://example.com")
        self.assertEqual(result[1]["text"]["content"], "link")

    def test_process_inline_formatting_multiple_formats(self):
        text = "Normal **bold** *italic* `code` [link](url) ~strike~ $math$"
        result = process_inline_formatting(text)
        self.assertTrue(len(result) > 6)  # Verify all formats processed

    def test_process_inline_formatting_nested_formats(self):
        text = "**Bold with *italic* inside**"
        result = process_inline_formatting(text)
        self.assertTrue(any(part.get("annotations", {}).get("bold") for part in result))
        # self.assertTrue(any(part.get("annotations", {}).get("italic") for part in result))

    def test_process_inline_formatting_plain(self):
        text = "plain text"
        result = process_inline_formatting(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "text")
        self.assertEqual(result[0]["text"]["content"], "plain text")

    def test_process_inline_formatting_strikethrough(self):
        text = "This is ~struck~ text"
        result = process_inline_formatting(text)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1]["annotations"]["strikethrough"], True)
        self.assertEqual(result[1]["text"]["content"], "struck")

    def test_parse_markdown_to_notion_blocks_mixed_nested_lists_numbered_bulleted(self):
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
        self.assertEqual(result[0]["type"], "numbered_list_item")
        self.assertEqual(result[0]["numbered_list_item"]["rich_text"][0]["text"]["content"], "First Numbered List Item")
        self.assertEqual(result[0]["numbered_list_item"]["children"][0]["type"], "bulleted_list_item")
        self.assertEqual(
            result[0]["numbered_list_item"]["children"][0]["bulleted_list_item"]["rich_text"][0]["text"]["content"],
            "First nested bulleted list item.",
        )
        self.assertEqual(result[1]["type"], "numbered_list_item")
        self.assertEqual(
            result[1]["numbered_list_item"]["rich_text"][0]["text"]["content"], "Second Numbered List Item"
        )
        self.assertEqual(result[1]["numbered_list_item"]["children"][0]["type"], "bulleted_list_item")
        self.assertEqual(
            result[1]["numbered_list_item"]["children"][0]["bulleted_list_item"]["rich_text"][0]["text"]["content"],
            "Second nested bulleted list item.",
        )
        self.assertEqual(result[2]["type"], "numbered_list_item")
        self.assertEqual(result[2]["numbered_list_item"]["rich_text"][0]["text"]["content"], "Third Numbered List Item")
        self.assertEqual(result[2]["numbered_list_item"]["children"][0]["type"], "bulleted_list_item")
        self.assertEqual(
            result[2]["numbered_list_item"]["children"][0]["bulleted_list_item"]["rich_text"][0]["text"]["content"],
            "Third nested bulleted list item.",
        )

    def test_parse_markdown_to_notion_blocks_mixed_nested_lists_bulleted_numbered(self):
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
        self.assertEqual(result[0]["type"], "bulleted_list_item")
        self.assertEqual(result[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"], "First Bulleted List Item")
        self.assertEqual(result[0]["bulleted_list_item"]["children"][0]["type"], "numbered_list_item")
        self.assertEqual(
            result[0]["bulleted_list_item"]["children"][0]["numbered_list_item"]["rich_text"][0]["text"]["content"],
            "First nested numbered list item.",
        )
        self.assertEqual(result[1]["type"], "bulleted_list_item")
        self.assertEqual(
            result[1]["bulleted_list_item"]["rich_text"][0]["text"]["content"], "Second Bulleted List Item"
        )
        self.assertEqual(result[1]["bulleted_list_item"]["children"][0]["type"], "numbered_list_item")
        self.assertEqual(
            result[1]["bulleted_list_item"]["children"][0]["numbered_list_item"]["rich_text"][0]["text"]["content"],
            "Second nested numbered list item.",
        )
        self.assertEqual(result[2]["type"], "bulleted_list_item")
        self.assertEqual(result[2]["bulleted_list_item"]["rich_text"][0]["text"]["content"], "Third Bulleted List Item")
        self.assertEqual(result[2]["bulleted_list_item"]["children"][0]["type"], "numbered_list_item")
        self.assertEqual(
            result[2]["bulleted_list_item"]["children"][0]["numbered_list_item"]["rich_text"][0]["text"]["content"],
            "Third nested numbered list item.",
        )

    def test_replace_content_that_is_too_long(self):
        text = "*" * 2001
        result = replace_content_that_is_too_long(text)
        self.assertEqual(len(result), 94)
        self.assertEqual(
            result, "This content is too long to be displayed in Notion. There is a 2000 character limit currently."
        )
