import re
from typing import List, Optional

from lark import Tree

from ..parser import parser
from .context import Context
from .constants import (
    TAB_INDENT_SIZE,
    INLINE_COMMENT_OFFSET,
    GLOBAL_SCOPE_SURROUNDING_EMPTY_LINES_TABLE,
)
from .types import FormattedLines
from .block import format_block
from .class_statement import format_class_statement
from .comments import (
    gather_standalone_comments,
    gather_inline_comments,
)


def format_code(
    gdscript_code: str,
    max_line_length: int,
    spaces_for_indent: Optional[int] = None,
    parse_tree: Optional[Tree] = None,
    comment_parse_tree: Optional[Tree] = None,
) -> str:
    parse_tree = (
        parse_tree
        if parse_tree is not None
        else parser.parse(gdscript_code, gather_metadata=True)
    )
    comment_parse_tree = (
        comment_parse_tree
        if comment_parse_tree is not None
        else parser.parse_comments(gdscript_code)
    )
    gdscript_code_lines = [
        "",
        *gdscript_code.splitlines(),
    ]  # type: List[str]
    formatted_lines = []  # type: FormattedLines
    single_indent_size = (
        TAB_INDENT_SIZE if spaces_for_indent is None else spaces_for_indent
    )
    single_indent_string = (
        "\t" if spaces_for_indent is None else " " * spaces_for_indent
    )
    context = Context(
        single_indent_size=single_indent_size,
        single_indent_string=single_indent_string,
        previously_processed_line_number=0,
        max_line_length=max_line_length,
        gdscript_code_lines=gdscript_code_lines,
        standalone_comments=gather_standalone_comments(
            gdscript_code, comment_parse_tree
        ),
        inline_comments=gather_inline_comments(gdscript_code, comment_parse_tree),
    )
    formatted_lines, _ = format_block(
        parse_tree.children,
        format_class_statement,
        context,
        GLOBAL_SCOPE_SURROUNDING_EMPTY_LINES_TABLE,
    )
    formatted_lines.append((None, ""))
    formatted_lines = _add_inline_comments(formatted_lines, context.inline_comments)
    formatted_lines = _add_standalone_comments(
        formatted_lines, context.standalone_comments, context.indent_regex
    )
    formatted_lines = _cleanup_region_spacing(formatted_lines)

    return "\n".join([line for _, line in formatted_lines])


def _add_inline_comments(
    formatted_lines: FormattedLines, comments: List[Optional[str]]
) -> FormattedLines:
    remaining_comments = comments[:]
    postprocessed_lines = []  # type: FormattedLines
    comment_offset = " " * INLINE_COMMENT_OFFSET

    for line_no, line in reversed(formatted_lines):
        if line_no is None:
            postprocessed_lines.append((line_no, line))
            continue
        comments = remaining_comments[line_no:]
        remaining_comments = remaining_comments[:line_no]
        if comments != []:
            new_line = comment_offset.join(
                [line] + [c for c in comments if c is not None]
            )
            postprocessed_lines.append((line_no, new_line))
        else:
            postprocessed_lines.append((line_no, line))

    return list(reversed(postprocessed_lines))


# pylint: disable=too-many-locals
def _add_standalone_comments(
    formatted_lines: FormattedLines,
    standalone_comments: List[Optional[str]],
    indent_regex: re.Pattern,
) -> FormattedLines:
    remaining_comments = standalone_comments[:]
    postprocessed_lines = []  # type: FormattedLines
    currently_inside_expression = False
    last_expression_line_no = None

    for line_no, line in reversed(formatted_lines):
        if line_no is None:
            postprocessed_lines.append((line_no, line))
            currently_inside_expression = False
            continue
        if not currently_inside_expression:
            postprocessed_lines.append((line_no, line))
            currently_inside_expression = True
            last_expression_line_no = line_no
            continue

        comments = remaining_comments[line_no:last_expression_line_no]
        remaining_comments = remaining_comments[:line_no]
        indent = _get_greater_indent(line, postprocessed_lines[-1][1], indent_regex)

        reversed_comments = list(reversed(comments))
        for i, comment in enumerate(reversed_comments):
            if comment is None:
                continue
            stripped = comment.strip()

            if stripped.startswith("#region"):
                # Insert a blank line before #region (optional)
                postprocessed_lines.append((None, ""))
                postprocessed_lines.append((None, f"{indent}{comment}"))

            elif stripped.startswith("#endregion"):
                # Remove up to 2 blank lines if they precede this comment
                while postprocessed_lines and postprocessed_lines[-1][1].strip() == "":
                    postprocessed_lines.pop()

                postprocessed_lines.append((None, f"{indent}{comment}"))

                # Add 2 lines after if another #region follows
                if i + 1 < len(reversed_comments):
                    next_comment = reversed_comments[i + 1]
                    if next_comment and next_comment.strip().startswith("#region"):
                        postprocessed_lines.append((None, ""))
                        postprocessed_lines.append((None, ""))

            else:
                # Normal comments
                postprocessed_lines.append((None, f"{indent}{comment}"))

        postprocessed_lines.append((line_no, line))

    return list(reversed(postprocessed_lines))


def _get_greater_indent(line_a: str, line_b: str, indent_regex: re.Pattern):
    line_a_match = indent_regex.search(line_a)
    line_b_match = indent_regex.search(line_b)
    line_a_indent = "" if line_a_match is None else line_a_match.group(0)
    line_b_indent = "" if line_b_match is None else line_b_match.group(0)
    return line_a_indent if len(line_a_indent) > len(line_b_indent) else line_b_indent


def _cleanup_region_spacing(formatted_lines: FormattedLines) -> FormattedLines:
    cleaned: FormattedLines = []
    i = 0
    while i < len(formatted_lines):
        line_no, line = formatted_lines[i]
        stripped = line.strip()

        if stripped.startswith("#endregion"):
            # Remove blank lines before #endregion
            while cleaned and cleaned[-1][1].strip() == "":
                cleaned.pop()
            cleaned.append((line_no, line))

            # Look ahead: if next non-blank is #region, ensure exactly 2 blank lines
            j = i + 1
            # Count how many blank lines already exist
            blank_lines = 0
            while j < len(formatted_lines):
                _, next_line = formatted_lines[j]
                if next_line.strip() == "":
                    blank_lines += 1
                    j += 1
                    continue
                if next_line.strip().startswith("#region"):
                    missing = 2 - blank_lines
                    for _ in range(missing):
                        cleaned.append((None, ""))
                break
        else:
            cleaned.append((line_no, line))

        i += 1

    return cleaned
