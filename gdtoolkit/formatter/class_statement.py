from typing import Dict, Callable
from functools import partial

from lark import Tree

from .types import FormattedLines, Outcome
from .context import Context, ExpressionContext
from .block import format_block
from .function_statement import format_func_statement
from .statement_utils import format_simple_statement
from .var_statement import format_var_statement
from .expression_to_str import expression_to_str
from .expression import (
    format_expression,
    format_concrete_expression,
)


def format_class_statement(statement: Tree, context: Context) -> Outcome:
    handlers = {
        "pass_stmt": partial(format_simple_statement, "pass"),
        "enum_stmt": _format_enum_statement,
        "signal_stmt": _format_signal_statement,
        "extends_stmt": _format_extends_statement,
        "classname_stmt": _format_classname_statement,
        "classname_extends_stmt": _format_classname_extends_statement,
        "class_var_stmt": format_var_statement,
        "const_stmt": _format_const_statement,
        "class_def": _format_class_statement,
        "func_def": _format_func_statement,
        "static_func_def": partial(
            _format_child_and_prepend_to_outcome, prefix="static "
        ),
    }  # type: Dict[str, Callable]
    return handlers[statement.data](statement, context)


def _format_child_and_prepend_to_outcome(
    statement: Tree, context: Context, prefix: str
) -> Outcome:
    lines, last_processed_line = format_class_statement(statement.children[0], context)
    first_line_no, first_line = lines[0]
    return (
        [
            (
                first_line_no,
                "{}{}{}".format(context.indent_string, prefix, first_line.strip()),
            )
        ]
        + lines[1:],
        last_processed_line,
    )


def _format_const_statement(statement: Tree, context: Context) -> Outcome:
    if len(statement.children) == 4:
        prefix = "const {} = ".format(statement.children[1].value)
    elif len(statement.children) == 5:
        prefix = "const {} := ".format(statement.children[1].value)
    elif len(statement.children) == 6:
        prefix = "const {}: {} = ".format(
            statement.children[1].value, statement.children[3].value
        )
    expression_context = ExpressionContext(
        prefix, statement.line, "", statement.end_line
    )
    return format_expression(statement.children[-1], expression_context, context)


def _format_signal_statement(statement: Tree, context: Context) -> Outcome:
    if len(statement.children) == 1 or len(statement.children[1].children) == 0:
        return format_simple_statement(
            "signal {}".format(statement.children[0].value), statement, context
        )
    expression_context = ExpressionContext(
        "signal {}".format(statement.children[0].value),
        statement.line,
        "",
        statement.end_line,
    )
    signal_args = statement.children[-1]
    return format_concrete_expression(signal_args, expression_context, context)


def _format_classname_statement(statement: Tree, context: Context) -> Outcome:
    last_processed_line_no = statement.line
    formatted_lines: FormattedLines = [
        (
            statement.line,
            "{}class_name {}".format(
                context.indent_string, statement.children[0].value
            ),
        )
    ]
    return (formatted_lines, last_processed_line_no)


def _format_extends_statement(statement: Tree, context: Context) -> Outcome:
    last_processed_line_no = statement.line
    optional_attributes = (
        ""
        if len(statement.children) == 1
        else ".{}".format(
            ".".join([expression_to_str(child) for child in statement.children[1:]])
        )
    )
    formatted_lines: FormattedLines = [
        (
            statement.line,
            "{}extends {}{}".format(
                context.indent_string,
                expression_to_str(statement.children[0]),
                optional_attributes,
            ),
        )
    ]
    return (formatted_lines, last_processed_line_no)


def _format_classname_extends_statement(statement: Tree, context: Context) -> Outcome:
    last_processed_line_no = statement.line
    extendee_pos = 2 + 1
    optional_attributes = (
        ""
        if len(statement.children) <= extendee_pos + 1
        else ".{}".format(
            ".".join(
                [
                    expression_to_str(child)
                    for child in statement.children[extendee_pos + 1 :]
                ]
            )
        )
    )
    formatted_lines: FormattedLines = [
        (
            statement.line,
            "{}class_name {} extends {}{}".format(
                context.indent_string,
                statement.children[1].value,
                expression_to_str(statement.children[extendee_pos]),
                optional_attributes,
            ),
        )
    ]
    return (formatted_lines, last_processed_line_no)


def _format_class_statement(statement: Tree, context: Context) -> Outcome:
    last_processed_line_no = statement.line
    name = statement.children[0].value
    formatted_lines: FormattedLines = [
        (statement.line, "{}class {}:".format(context.indent_string, name))
    ]
    class_lines, last_processed_line_no = format_block(
        statement.children[1:],
        format_class_statement,
        context.create_child_context(last_processed_line_no),
    )
    formatted_lines += class_lines
    return (formatted_lines, last_processed_line_no)


def _format_func_statement(statement: Tree, context: Context) -> Outcome:
    func_header = statement.children[0]
    formatted_lines, last_processed_line_no = _format_func_header(func_header, context)
    func_lines, last_processed_line_no = format_block(
        statement.children[1:],
        format_func_statement,
        context.create_child_context(last_processed_line_no),
    )
    formatted_lines += func_lines
    return (formatted_lines, last_processed_line_no)


def _format_func_header(statement: Tree, context: Context) -> Outcome:
    name = statement.children[0].value
    has_return_type = len(statement.children) > 2
    expression_context = ExpressionContext(
        f"func {name}",
        statement.line,
        f" -> {statement.children[2].value}:" if has_return_type else ":",
        statement.end_line,
    )
    func_args = statement.children[1]
    return format_concrete_expression(func_args, expression_context, context)


def _format_enum_statement(statement: Tree, context: Context) -> Outcome:
    actual_enum = statement.children[0]
    prefix = (
        "enum {} ".format(actual_enum.children[0].value)
        if len(actual_enum.children) == 2
        else "enum "
    )
    expression_context = ExpressionContext(
        prefix, statement.line, "", statement.end_line
    )
    enum_body = actual_enum.children[-1]
    return format_concrete_expression(enum_body, expression_context, context)
