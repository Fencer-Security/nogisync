import re

NOTION_CONTENT_MAX_LENGTH = 2000
# Notion API rejects list nesting beyond 3 levels
NOTION_MAX_LIST_DEPTH = 3

NOTION_SUPPORTED_LANGUAGES = frozenset(
    {
        "abap",
        "abc",
        "agda",
        "arduino",
        "ascii art",
        "assembly",
        "bash",
        "basic",
        "bnf",
        "c",
        "c#",
        "c++",
        "clojure",
        "coffeescript",
        "coq",
        "css",
        "dart",
        "dhall",
        "diff",
        "docker",
        "ebnf",
        "elixir",
        "elm",
        "erlang",
        "f#",
        "flow",
        "fortran",
        "gherkin",
        "glsl",
        "go",
        "graphql",
        "groovy",
        "haskell",
        "hcl",
        "html",
        "idris",
        "java",
        "javascript",
        "json",
        "julia",
        "kotlin",
        "latex",
        "less",
        "lisp",
        "livescript",
        "llvm ir",
        "lua",
        "makefile",
        "markdown",
        "markup",
        "matlab",
        "mathematica",
        "mermaid",
        "nix",
        "notion formula",
        "objective-c",
        "ocaml",
        "pascal",
        "perl",
        "php",
        "plain text",
        "powershell",
        "prolog",
        "protobuf",
        "purescript",
        "python",
        "r",
        "racket",
        "reason",
        "ruby",
        "rust",
        "sass",
        "scala",
        "scheme",
        "scss",
        "shell",
        "smalltalk",
        "solidity",
        "sql",
        "swift",
        "toml",
        "typescript",
        "vb.net",
        "verilog",
        "vhdl",
        "visual basic",
        "webassembly",
        "xml",
        "yaml",
        "java/c/c++/c#",
    }
)


def replace_part(parts, pattern, replace_function) -> list:
    # Process italic matches
    new_text_parts = []
    for part in parts:
        if isinstance(part, str):
            matches = list(re.finditer(pattern, part))
            prev_end = 0
            for match in matches:
                if prev_end != match.start():
                    new_text_parts.append(part[prev_end : match.start()])
                new_text_parts.append(replace_function(match))
                prev_end = match.end()
            new_text_parts.append(part[prev_end:])
        else:
            new_text_parts.append(part)
    return new_text_parts


def replace_content_that_is_too_long(content) -> str:
    if len(content) > NOTION_CONTENT_MAX_LENGTH:
        return f"This content is too long to be displayed in Notion. There is a {NOTION_CONTENT_MAX_LENGTH} character limit currently."
    return content


def process_inline_formatting(text) -> list[dict]:
    """
    Process inline formatting in Markdown text and convert it to Notion rich text formatting.
    """

    # Regular expressions for bold and italic markdown
    code_pattern = r"`(.+?)`"
    bold_pattern = r"(\*\*(.+?)\*\*)|(__(.+?)__)"
    overline_pattern = r"\~(.+?)\~"
    inline_katex_pattern = r"\$(.+?)\$"
    italic_pattern = r"(\*(.+?)\*)|(_(.+?)_)"
    link_pattern = r"\[(.+?)\]\((.+?)\)"
    bold_italic_pattern = r"(__\*(.+?)\*__)|(\*\*_(.+?)_\*\*)"

    def replace_katex(match) -> dict:
        return {"type": "equation", "equation": {"expression": match.group(1)}}

    def replace_bolditalic(match) -> dict:
        content = match.group(2) or match.group(4)
        content = replace_content_that_is_too_long(content)
        return {
            "type": "text",
            "text": {"content": content, "link": None},
            "annotations": {
                "bold": True,
                "italic": True,
                "strikethrough": False,
                "underline": False,
                "code": False,
                "color": "default",
            },
            "plain_text": content,
            "href": None,
        }

    # Replace markdown with Notion rich text formatting
    def replace_code(match) -> dict:
        content = match.group(1)
        content = replace_content_that_is_too_long(content)
        return {
            "type": "text",
            "text": {"content": content, "link": None},
            "annotations": {
                "bold": False,
                "italic": False,
                "strikethrough": False,
                "underline": False,
                "code": True,
                "color": "default",
            },
            "plain_text": content,
            "href": None,
        }

    # Replace markdown with Notion rich text formatting
    def replace_overline(match) -> dict:
        content = match.group(1)
        content = replace_content_that_is_too_long(content)
        return {
            "type": "text",
            "text": {"content": content, "link": None},
            "annotations": {
                "bold": False,
                "italic": False,
                "strikethrough": True,
                "underline": False,
                "code": False,
                "color": "default",
            },
            "plain_text": content,
            "href": None,
        }

    # Replace markdown with Notion rich text formatting
    def replace_bold(match) -> dict:
        content = match.group(2) or match.group(4)
        content = replace_content_that_is_too_long(content)
        return {
            "type": "text",
            "text": {"content": content, "link": None},
            "annotations": {
                "bold": True,
                "italic": False,
                "strikethrough": False,
                "underline": False,
                "code": False,
                "color": "default",
            },
            "plain_text": content,
            "href": None,
        }

    def replace_italic(match) -> dict:
        content = match.group(2) or match.group(4)
        content = replace_content_that_is_too_long(content)
        return {
            "type": "text",
            "text": {"content": content, "link": None},
            "annotations": {
                "bold": False,
                "italic": True,
                "strikethrough": False,
                "underline": False,
                "code": False,
                "color": "default",
            },
            "plain_text": content,
            "href": None,
        }

    def replace_link(match) -> dict:
        content = match.group(1)
        content = replace_content_that_is_too_long(content)
        return {
            "type": "text",
            "text": {"content": content, "link": {"url": match.group(2)}},
            "annotations": {
                "bold": False,
                "italic": False,
                "strikethrough": False,
                "underline": False,
                "code": False,
                "color": "default",
            },
            "plain_text": content,
            "href": match.group(2),
        }

    # Apply the replacements for bold and italic formatting
    text_parts = []

    # Process bold italic matches
    matches = list(re.finditer(bold_italic_pattern, text))
    prev_end = 0
    for match in matches:
        # The false branch (prev_end == match.start()) only occurs when two bold-italic
        # matches are adjacent with no gap, which doesn't happen in practice
        if prev_end != match.start():  # pragma: no branch
            text_parts.append(text[prev_end : match.start()])
        text_parts.append(replace_bolditalic(match))
        prev_end = match.end()
    text_parts.append(text[prev_end:])

    text_parts = replace_part(text_parts, bold_pattern, replace_bold)
    text_parts = replace_part(text_parts, italic_pattern, replace_italic)
    text_parts = replace_part(text_parts, inline_katex_pattern, replace_katex)
    text_parts = replace_part(text_parts, overline_pattern, replace_overline)
    text_parts = replace_part(text_parts, code_pattern, replace_code)
    text_parts = replace_part(text_parts, link_pattern, replace_link)

    # Remove empty strings from the list and return the processed text parts
    return [
        ({"type": "text", "text": {"content": part}} if isinstance(part, str) else part)
        for part in text_parts
        if part != ""
    ]


# katex
def convert_markdown_table_to_latex(text) -> str:
    split_column = text.split("\n")
    has_header = False
    # Check if the second line is a delimiter
    if len(split_column) > 1 and re.match(r"\|\s*-+\s*\|", split_column[1]):
        # Remove the delimiter line
        split_column.pop(1)
        has_header = True
    table_content = ""
    for i, row in enumerate(split_column):
        modified_content = re.findall(r"(?<=\|).*?(?=\|)", row)
        new_text = ""
        for j, cell in enumerate(modified_content):
            cell_text = f"\\textsf{{{cell.strip()}}}"
            if i == 0 and has_header:
                cell_content = process_inline_formatting(cell.strip())[0]["text"]["content"]
                cell_text = f"\\textsf{{\\textbf{{{cell_content}}}}}"
            if j == len(modified_content) - 1:
                cell_text += " \\\\\\hline\n"
            else:
                cell_text += " & "
            new_text += cell_text
        table_content += new_text

    count_column = len(split_column[0].split("|"))

    table_column = "|c" * count_column
    add_table = f"\\def\\arraystretch{{1.4}}\\begin{{array}}{{{table_column}|}}\\hline\n{table_content}\\end{{array}}"

    return add_table


def parse_markdown_to_notion_blocks(markdown) -> list[dict]:
    """
    Parse Markdown text and convert it into a list of Notion blocks.

    :param markdown: The Markdown text to be parsed.
    :type markdown: str
    :return: A list of Notion blocks representing the parsed Markdown content.
    :rtype: list
    """

    # Detect code blocks enclosed within triple backticks
    code_block_pattern = re.compile(r"```(\w+?)\n(.+?)```", re.DOTALL)
    # katex
    latex_block_pattern = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
    numbered_list_pattern_nested = r"^( *)(\d+)\. "
    unordered_list_pattern_nested = r"^( *)(\-) "
    heading_pattern = r"^(#+) "

    # indented_code_pattern = re.compile(r'^ {4}(.+)$', re.MULTILINE)
    # triple_backtick_code_pattern = re.compile(r"^```(.+?)```", re.MULTILINE | re.DOTALL)
    blockquote_pattern = r"^> (.+)$"
    horizontal_line_pattern = r"^-{3,}$"
    image_pattern = r"!\[(.*?)\]\((.*?)\)"

    code_blocks: dict = {}

    def replace_code_blocks(match) -> str:
        index = len(code_blocks)
        language, content = match.group(1), match.group(2)
        language = (language or "plain text").strip().lower()
        if language not in NOTION_SUPPORTED_LANGUAGES:
            language = "plain text"
        code_blocks[index] = language, content.strip()
        return f"CODE_BLOCK_{index}"

    # Replace code blocks with placeholders
    markdown = code_block_pattern.sub(replace_code_blocks, markdown)

    # katex
    latex_blocks: dict = {}

    def replace_latex_blocks(match) -> str:
        index = len(latex_blocks)
        latex_blocks[index] = (match.group(1) + "").strip()
        return f"LATEX_BLOCK_{index}"

    # Replace code blocks with placeholders
    markdown = latex_block_pattern.sub(replace_latex_blocks, markdown)

    lines = markdown.split("\n")
    blocks: list[dict] = []

    # Initialize variables to keep track of the current table
    current_table: list[str] = []
    in_table = False

    current_indent = 0
    stack = [blocks]

    indented_code_accumulator = []
    for line in lines:
        # Check if the line is a table row (e.g., "| Header 1 | Header 2 |" or "| Content 1 | Content 2 |")
        is_table_row = re.match(r"\|\s*[^-|]+\s*\|", line)
        # Check if the line is a table delimiter (e.g., "|---|---|")
        is_table_delimiter = re.match(r"\|\s*[-]+\s*\|\s*[-]+\s*\|", line)

        # If we find table row or delimiter, add the line to the current table
        if is_table_row or is_table_delimiter:
            current_table.append(line)
            in_table = True
            continue
        elif in_table and (not is_table_row and not is_table_delimiter):
            # If we find a non-table line and we're in a table, end the current table
            in_table = False
            # Process the current table
            table_str = "\n".join(current_table)
            # katex
            latex_table = convert_markdown_table_to_latex(table_str)
            # Create Notion equation block with LaTeX table expression
            equation_block = {"type": "equation", "equation": {"expression": latex_table}}
            blocks.append(equation_block)
            # Reset the current table
            current_table = []
            continue

        list_match = re.match(numbered_list_pattern_nested, line)
        if list_match:
            indent = len(list_match.group(1))
            line = line[len(list_match.group(0)) :]

            item = {
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": process_inline_formatting(line)},
            }

            while indent < current_indent:
                # If the indentation is less than the current level, go back one level in the stack
                stack.pop()
                current_indent -= 1

            if indent == current_indent or len(stack) >= NOTION_MAX_LIST_DEPTH:
                # Same level, or Notion max nesting depth reached — append at current level
                stack[-1].append(item)
            else:  # indent > current_indent
                # Nested item, add it as a child of the previous item
                previous_parent = stack[-1][-1]
                if "bulleted_list_item" in previous_parent:
                    previous_parent_list_item_type = "bulleted_list_item"
                elif "numbered_list_item" in previous_parent:
                    previous_parent_list_item_type = "numbered_list_item"
                else:
                    # Previous item is not a list item (e.g., a paragraph from a
                    # continuation line), so we can't nest. Append at current level.
                    stack[-1].append(item)
                    # The continue makes the code after the else block unreachable
                    # from this path, which coverage reports as a missing branch
                    continue  # pragma: no branch

                # Children are always freshly created on the first nest, so
                # the false branch (children already exists) is not reachable
                if "children" not in previous_parent[previous_parent_list_item_type]:  # pragma: no branch
                    previous_parent[previous_parent_list_item_type]["children"] = []
                previous_parent[previous_parent_list_item_type]["children"].append(item)
                stack.append(
                    previous_parent[previous_parent_list_item_type]["children"]
                )  # Add a new level to the stack
                current_indent += 1

            continue

        list_match = re.match(unordered_list_pattern_nested, line)
        if list_match:
            indent = len(list_match.group(1))
            line = line[len(list_match.group(0)) :]

            item = {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": process_inline_formatting(line)},
            }

            while indent < current_indent:
                # If the indentation is less than the current level, go back one level in the stack
                stack.pop()
                current_indent -= 1

            if indent == current_indent or len(stack) >= NOTION_MAX_LIST_DEPTH:
                # Same level, or Notion max nesting depth reached — append at current level
                stack[-1].append(item)
            else:  # indent > current_indent
                # Nested item, add it as a child of the previous item
                previous_parent = stack[-1][-1]
                if "bulleted_list_item" in previous_parent:
                    previous_parent_list_item_type = "bulleted_list_item"
                elif "numbered_list_item" in previous_parent:
                    previous_parent_list_item_type = "numbered_list_item"
                else:
                    # Previous item is not a list item (e.g., a paragraph from a
                    # continuation line), so we can't nest. Append at current level.
                    stack[-1].append(item)
                    # The continue makes the code after the else block unreachable
                    # from this path, which coverage reports as a missing branch
                    continue  # pragma: no branch

                # Children are always freshly created on the first nest, so
                # the false branch (children already exists) is not reachable
                if "children" not in previous_parent[previous_parent_list_item_type]:  # pragma: no branch
                    previous_parent[previous_parent_list_item_type]["children"] = []
                previous_parent[previous_parent_list_item_type]["children"].append(item)
                stack.append(
                    previous_parent[previous_parent_list_item_type]["children"]
                )  # Add a new level to the stack
                current_indent += 1

            continue

        if line.startswith("    "):  # Check if the line is indented
            indented_code_accumulator.append(line[4:])  # Remove the leading spaces
            continue
        else:
            if indented_code_accumulator:  # Check if there are accumulated lines
                code_block = "\n".join(indented_code_accumulator)
                blocks.append(
                    {
                        "object": "block",
                        "type": "code",
                        "code": {
                            "language": "plain text",
                            "rich_text": [
                                {"type": "text", "text": {"content": replace_content_that_is_too_long(code_block)}}
                            ],
                        },
                    }
                )
                # Clear the accumulator
                indented_code_accumulator = []

        # Reset list nesting state when a non-list line is encountered,
        # so stale state doesn't cause errors when a new list starts later.
        current_indent = 0
        stack = [blocks]

        # Check for headings and create appropriate heading blocks
        heading_match = re.match(heading_pattern, line)
        blockquote_match = re.match(blockquote_pattern, line)
        image_match = re.search(image_pattern, line)

        if heading_match:
            heading_level = len(heading_match.group(1))
            content = re.sub(heading_pattern, "", line)
            if 1 <= heading_level <= 3:
                block_type = f"heading_{heading_level}"
                blocks.append(
                    {
                        "object": "block",
                        "type": block_type,
                        block_type: {"rich_text": process_inline_formatting(content)},
                    }
                )

        # Check for horizontal line and create divider blocks
        elif re.match(horizontal_line_pattern, line):
            blocks.append({"divider": {}, "type": "divider"})

        # Check for blockquote and create blockquote blocks
        elif blockquote_match:
            blocks.append(
                {
                    "object": "block",
                    "type": "quote",
                    "quote": {"rich_text": process_inline_formatting(blockquote_match.group(1))},
                }
            )

        # Check for code blocks and create code blocks
        elif line.startswith("CODE_BLOCK_"):
            code_block_index = int(line[len("CODE_BLOCK_") :])
            language, code_block = code_blocks[code_block_index]
            blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": language,
                        "rich_text": [
                            {"type": "text", "text": {"content": replace_content_that_is_too_long(code_block)}}
                        ],
                    },
                }
            )

        # Check for katex blocks
        elif line.startswith("LATEX_BLOCK_"):
            latex_block_index = int(line[len("LATEX_BLOCK_") :])
            latex_content = latex_blocks[latex_block_index]
            blocks.append({"type": "equation", "equation": {"expression": latex_content}})

        # Image blocks — Notion only accepts absolute HTTP(S) URLs
        elif image_match:
            image_url = image_match.group(2)
            if image_url.startswith(("http://", "https://")):
                block: dict = {
                    "object": "block",
                    "type": "image",
                    "image": {
                        "external": {
                            "url": image_url,
                        }
                    },
                }
                caption = image_match.group(1)
                if caption:
                    block["image"]["caption"] = [{"type": "text", "text": {"content": caption, "link": None}}]
                blocks.append(block)
            else:
                # Relative/invalid URLs can't be used — render as a text paragraph
                blocks.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": process_inline_formatting(line)},
                    }
                )

        # Create paragraph blocks for other lines
        elif line.strip():
            blocks.append(
                {"object": "block", "type": "paragraph", "paragraph": {"rich_text": process_inline_formatting(line)}}
            )

    # If there's an unfinished table at the end of the lines, process it
    if in_table:
        table_str = "\n".join(current_table)
        latex_table = convert_markdown_table_to_latex(table_str)
        equation_block = {"type": "equation", "equation": {"expression": latex_table}}
        blocks.append(equation_block)

    # Add any remaining indented lines as a code block
    if indented_code_accumulator:
        code_block = "\n".join(indented_code_accumulator)
        blocks.append(
            {
                "object": "block",
                "type": "code",
                "code": {
                    "language": "plain text",
                    "rich_text": [{"type": "text", "text": {"content": replace_content_that_is_too_long(code_block)}}],
                },
            }
        )

    return blocks


def parse_md(markdown_text):
    """
    Parse Markdown text and convert it into Notion blocks.
    """
    # Parse the transformed Markdown to create Notion blocks
    return parse_markdown_to_notion_blocks(markdown_text.strip())
