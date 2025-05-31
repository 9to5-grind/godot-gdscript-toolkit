from doctest import debug
from typing import Dict, Callable, List, Optional
from importlib import import_module

from lark import Tree, Token
from lark.tree import Meta

from ..common.utils import get_line, get_end_line
from ..common.types import Node
from .context import Context, ExpressionContext
from .types import Outcome, FormattedLines
from .expression_utils import (
    remove_outer_parentheses,
    is_foldable,
    is_expression_forcing_multiple_lines,
    expression_contains_lambda,
    is_any_comma,
    is_trailing_comma,
    is_safe_operator_expression,
)
from .expression_to_str import expression_to_str
from .constants import TAB_INDENT_SIZE


def format_expression(
    expression: Tree,
    expression_context: ExpressionContext,
    context: Context,
    is_if_elif_condition_expr: bool = False,
) -> Outcome:
    concrete_expression = expression.children[0]
    return (
        _format_standalone_expression(
            concrete_expression, expression_context, context, is_if_elif_condition_expr
        ),
        get_end_line(expression),
    )


def format_concrete_expression(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> Outcome:
    return (
        _format_concrete_expression(expression, expression_context, context),
        get_end_line(expression),
    )


def _format_standalone_expression(
    expression: Node,
    expression_context: ExpressionContext,
    context: Context,
    is_if_elif_condition_expr: bool = False,
) -> FormattedLines:
    if not is_if_elif_condition_expr:
        expression = remove_outer_parentheses(expression)
    return _format_concrete_expression(expression, expression_context, context)


def _format_concrete_expression(
    expression: Node, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    if is_foldable(expression):
        assert isinstance(expression, Tree)
        return _format_foldable(expression, expression_context, context)  # type: ignore
    return _format_concrete_expression_to_single_line(
        expression, expression_context, context
    )


def _format_concrete_expression_to_single_line(
    expression: Node, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    return [
        (
            expression_context.prefix_line,
            "{}{}{}{}".format(
                context.indent_string,
                expression_context.prefix_string,
                expression_to_str(expression),
                expression_context.suffix_string,
            ),
        )
    ]


def _format_comma_separated_list(
    a_list: List[Node], expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    fake_meta = Meta()
    fake_meta.line = expression_context.prefix_line
    fake_meta.end_line = expression_context.suffix_line
    fake_expression = Tree("comma_separated_list", a_list, fake_meta)
    return _format_concrete_expression(fake_expression, expression_context, context)


def _format_foldable(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    if is_expression_forcing_multiple_lines(expression, context.standalone_comments):
        return _format_foldable_to_multiple_lines(
            expression, expression_context, context
        )
    single_line_number, single_line = _format_concrete_expression_to_single_line(
        expression, expression_context, context
    )[0]
    single_line_length = len(single_line.replace("\t", " " * TAB_INDENT_SIZE))
    if single_line_length <= context.max_line_length:
        return [(single_line_number, single_line)]
    return _format_foldable_to_multiple_lines(expression, expression_context, context)


def _format_foldable_to_multiple_lines(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    handlers = {
        "assnmnt_expr": _format_assignment_expression_to_multiple_lines,
        "test_expr": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_test_expr": _format_operator_chain_based_expression_to_multiple_lines,
        "or_test": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_or_test": _format_operator_chain_based_expression_to_multiple_lines,
        "and_test": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_and_test": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_actual_not_test": _format_not_test_to_multiple_lines,
        "content_test": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_content_test": (
            _format_operator_chain_based_expression_to_multiple_lines
        ),
        "comparison": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_comparison": _format_operator_chain_based_expression_to_multiple_lines,
        "bitw_or": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_bitw_or": _format_operator_chain_based_expression_to_multiple_lines,
        "bitw_xor": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_bitw_xor": _format_operator_chain_based_expression_to_multiple_lines,
        "bitw_and": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_bitw_and": _format_operator_chain_based_expression_to_multiple_lines,
        "shift_expr": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_shift_expr": _format_operator_chain_based_expression_to_multiple_lines,
        "arith_expr": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_arith_expr": _format_operator_chain_based_expression_to_multiple_lines,
        "mdr_expr": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_mdr_expr": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_actual_neg_expr": lambda e, ec, c: _append_to_expression_context_and_pass(
            f"{expression_to_str(e.children[0])}", e.children[1], ec, c
        ),
        "asless_actual_bitw_not": lambda e, ec, c: _append_to_expression_context_and_pass(
            f"{expression_to_str(e.children[0])}", e.children[1], ec, c
        ),
        "pow_expr": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_pow_expr": _format_operator_chain_based_expression_to_multiple_lines,
        "type_test": _format_operator_chain_based_expression_to_multiple_lines,
        "asless_type_test": _format_operator_chain_based_expression_to_multiple_lines,
        "actual_type_cast": _format_operator_chain_based_expression_to_multiple_lines,
        "await_expr": _format_await_expression_to_multiple_lines,
        "standalone_call": _format_call_expression_to_multiple_lines,
        "getattr_call": _collapse_getattr_tree_to_dot_chain_and_format_to_multiple_lines,
        "getattr": _collapse_getattr_tree_to_dot_chain_and_format_to_multiple_lines,
        "subscr_expr": _collapse_subscr_expr_tree_to_dot_chain_and_format_to_multiple_lines,
        "par_expr": _format_parentheses_to_multiple_lines,
        "array": _format_array_to_multiple_lines,
        "string": _format_string_to_multiple_lines,
        "dict": _format_dict_to_multiple_lines,
        "c_dict_element": _format_kv_pair_to_multiple_lines,
        "eq_dict_element": _format_kv_pair_to_multiple_lines,
        "lambda": _format_lambda_to_multiple_lines,
        "lambda_header": _format_lambda_header_to_multiple_lines,
        # fake expressions:
        "func_args": _format_args_to_multiple_lines,
        "func_arg_regular": _format_func_arg_to_multiple_lines,
        "func_arg_inf": _format_func_arg_to_multiple_lines,
        "func_arg_typed": _format_func_arg_to_multiple_lines,
        "enum_body": _format_dict_to_multiple_lines,
        "signal_args": _format_args_to_multiple_lines,
        "comma_separated_list": _format_comma_separated_list_to_multiple_lines,
        "contextless_comma_separated_list": (
            _format_contextless_comma_separated_list_to_multiple_lines
        ),
        "contextless_operator_chain_based_expression": (
            _format_contextless_operator_chain_based_expression_to_multiple_lines
        ),
        "annotation": _format_annotation_to_multiple_lines,
        "annotation_args": _format_args_to_multiple_lines,
        "dot_chain": _format_dot_chain_to_multiple_lines,
        "actual_getattr_call": _format_call_expression_to_multiple_lines,
        "actual_subscr_expr": _format_subscription_to_multiple_lines,
        # patterns (fake expressions):
        "list_pattern": _format_concrete_expression_to_single_line,
        "test_pattern": _format_operator_chain_based_expression_to_multiple_lines,
        "par_pattern": _format_parentheses_to_multiple_lines,
        "or_pattern": _format_operator_chain_based_expression_to_multiple_lines,
        "and_pattern": _format_operator_chain_based_expression_to_multiple_lines,
        "not_pattern": _format_concrete_expression_to_single_line,
        "comp_pattern": _format_operator_chain_based_expression_to_multiple_lines,
        "bitw_or_pattern": _format_operator_chain_based_expression_to_multiple_lines,
        "bitw_xor_pattern": _format_operator_chain_based_expression_to_multiple_lines,
        "bitw_and_pattern": _format_operator_chain_based_expression_to_multiple_lines,
        "shift_pattern": _format_operator_chain_based_expression_to_multiple_lines,
        "arith_pattern": _format_operator_chain_based_expression_to_multiple_lines,
        "mdr_pattern": _format_operator_chain_based_expression_to_multiple_lines,
        "neg_pattern": _format_concrete_expression_to_single_line,
        "bitw_not_pattern": _format_concrete_expression_to_single_line,
        "attr_pattern": _format_operator_chain_based_expression_to_multiple_lines,
        "call_pattern": _format_call_expression_to_multiple_lines,
        "array_pattern": _format_array_to_multiple_lines,
        "dict_pattern": _format_dict_to_multiple_lines,
        "kv_pair_pattern": _format_kv_pair_to_multiple_lines,
    }  # type: Dict[str, Callable]
    return handlers[expression.data](expression, expression_context, context)


def _format_array_to_multiple_lines(
    array: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    new_expression_context = ExpressionContext(
        f"{expression_context.prefix_string}[",
        expression_context.prefix_line,
        f"]{expression_context.suffix_string}",
        get_end_line(array),
    )
    return _format_comma_separated_list(array.children, new_expression_context, context)


def _format_dict_to_multiple_lines(
    a_dict: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    new_expression_context = ExpressionContext(
        f"{expression_context.prefix_string}{{",
        expression_context.prefix_line,
        f"}}{expression_context.suffix_string}",
        get_end_line(a_dict),
    )
    return _format_comma_separated_list(
        a_dict.children, new_expression_context, context
    )


def _format_args_to_multiple_lines(
    args: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    new_expression_context = ExpressionContext(
        f"{expression_context.prefix_string}(",
        expression_context.prefix_line,
        f"){expression_context.suffix_string}",
        get_end_line(args),
    )
    return _format_comma_separated_list(args.children, new_expression_context, context)


def _format_kv_pair_to_multiple_lines(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    suffix = ":" if expression.data in ["c_dict_element", "kv_pair_pattern"] else " ="
    key_expression_context = ExpressionContext(
        expression_context.prefix_string,
        expression_context.prefix_line,
        suffix,
        expression_context.suffix_line,
    )
    key_lines = _format_standalone_expression(
        expression.children[0], key_expression_context, context
    )
    value_expression_context = ExpressionContext(
        "", -1, expression_context.suffix_string, expression_context.suffix_line
    )
    value_lines = _format_standalone_expression(
        expression.children[1], value_expression_context, context
    )
    return key_lines + value_lines


def _format_parentheses_to_multiple_lines(
    par_expr: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    new_expression_context = ExpressionContext(
        f"{expression_context.prefix_string}(",
        expression_context.prefix_line,
        f"){expression_context.suffix_string}",
        get_end_line(par_expr),
    )
    return _format_standalone_expression(
        par_expr.children[0],
        new_expression_context,
        context,
    )


def _format_string_to_multiple_lines(
    string: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    long_string = string.children[0]
    lines = long_string.value.splitlines()
    formatted_lines = [
        (
            expression_context.prefix_line,
            "{}{}{}".format(
                context.indent_string, expression_context.prefix_string, lines[0]
            ),
        )
    ]  # type: FormattedLines
    for middle_line in lines[1:-1]:
        formatted_lines.append((get_line(string), middle_line))
    formatted_lines.append(
        (get_line(string), f"{lines[-1]}{expression_context.suffix_string}")
    )
    return formatted_lines


def _format_not_test_to_multiple_lines(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    spacing = "" if expression.children[0].value == "!" else " "
    return _append_to_expression_context_and_pass(
        f"{expression_to_str(expression.children[0])}{spacing}",
        expression.children[1],
        expression_context,
        context,
    )


def _format_assignment_expression_to_multiple_lines(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    new_expression_context = ExpressionContext(
        "{}{} {} ".format(
            expression_context.prefix_string,
            expression_to_str(expression.children[0]),
            expression_to_str(expression.children[1]),
        ),
        expression_context.prefix_line,
        expression_context.suffix_string,
        expression_context.suffix_line,
    )
    return _format_concrete_expression(
        expression.children[2], new_expression_context, context
    )


def _format_func_arg_to_multiple_lines(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    if expression.data == "func_arg_regular" and len(expression.children) == 1:
        return _format_concrete_expression(
            expression.children[0], expression_context, context
        )
    if expression.data == "func_arg_typed" and len(expression.children) == 2:
        return [
            (
                get_line(expression.children[1]),
                f"{context.indent_string}{expression_to_str(expression)}",
            )
        ]
    template = {
        "func_arg_regular": "{} = ",
        "func_arg_inf": "{} := ",
        "func_arg_typed": "{{}}: {} = ".format(expression.children[1]),
    }[expression.data]
    new_expression_context = ExpressionContext(
        template.format(expression.children[0].value),
        expression_context.prefix_line,
        expression_context.suffix_string,
        expression_context.suffix_line,
    )
    return format_expression(expression.children[-1], new_expression_context, context)[
        0
    ]


def _format_call_expression_to_multiple_lines(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    callee_node = expression.children[0]
    callee = expression_to_str(callee_node)
    list_is_empty = len(expression.children) == 1
    if list_is_empty:
        return [
            (
                expression_context.prefix_line,
                "{}{}{}(){}".format(
                    context.indent_string,
                    expression_context.prefix_string,
                    callee,
                    expression_context.suffix_string,
                ),
            )
        ]
    new_expression_context = ExpressionContext(
        "{}{}(".format(expression_context.prefix_string, callee),
        get_line(callee_node),
        "){}".format(expression_context.suffix_string),
        get_end_line(expression),
    )
    return _format_comma_separated_list(
        expression.children[1:], new_expression_context, context
    )


def _collapse_getattr_tree_to_dot_chain_and_format_to_multiple_lines(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    return _format_foldable_to_multiple_lines(
        _collapse_getattr_tree_to_dot_chain(expression), expression_context, context
    )


def _collapse_subscr_expr_tree_to_dot_chain_and_format_to_multiple_lines(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    dot_chain = _collapse_subscr_expr_tree_to_dot_chain(expression)
    if len(dot_chain.children) == 1:
        dot_chain = dot_chain.children[0]
    return _format_foldable_to_multiple_lines(dot_chain, expression_context, context)


def _format_subscription_to_multiple_lines(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    subscriptee_expression_context = ExpressionContext(
        expression_context.prefix_string,
        expression_context.prefix_line,
        "",
        expression_context.suffix_line,
    )
    subscriptee = expression.children[0]
    subscriptee_lines = _format_concrete_expression(
        subscriptee, subscriptee_expression_context, context
    )
    last_line = subscriptee_lines[-1][0]
    assert last_line is not None
    subscript_expression_context = ExpressionContext(
        f"{subscriptee_lines[-1][1].strip()}[",
        last_line,  # type: ignore
        f"]{expression_context.suffix_string}",
        expression_context.suffix_line,
    )
    subscript = expression.children[1]
    subscript_lines = _format_concrete_expression(
        subscript, subscript_expression_context, context
    )
    return subscriptee_lines[:-1] + subscript_lines


def _format_operator_chain_based_expression_to_multiple_lines(  # New version
        expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    # Original prefix/suffix from the ExpressionContext for the whole operator chain
    # e.g., for "if (a && b):", prefix_string="if (", suffix_string="):"
    # e.g., for "x = a && b", prefix_string="x = ", suffix_string=""
    outer_prefix = expression_context.prefix_string
    outer_suffix = expression_context.suffix_string

    # Determine if *new* grouping parentheses are needed around the entire chain.
    # This is for cases like `foo = bar or \n baz` becoming `foo = (bar or \n baz)`
    # It's NOT for the parentheses already part of `if (...)` or `call(...)`.
    already_in_parens_from_context = (
                                             outer_prefix.endswith("(") and outer_suffix.startswith(")")
                                     ) or (outer_prefix.endswith("[") and outer_suffix.startswith("]"))

    # If it's not already in parens from the context (like if, while, func call)
    # AND it's not a "safe" operator type, then we need to add grouping parens.
    needs_new_grouping_parens = (
            not already_in_parens_from_context
            and not is_safe_operator_expression(expression)
    )

    # These are the parentheses for the *overall grouping* if needed
    grouping_lpar = "(" if needs_new_grouping_parens else ""
    grouping_rpar = ")" if needs_new_grouping_parens else ""

    # Prepare the lines
    formatted_lines: FormattedLines = []

    processed_outer_prefix = outer_prefix.rstrip()
    space_before_grouping_lpar = ""
    if grouping_lpar and processed_outer_prefix:
        # If the original outer_prefix (before rstrip) did not end with a space,
        # and we are adding a grouping_lpar, we might need a space.
        # Example: "foo=" + "(" -> "foo= ("
        # More robust: if the rstripped prefix doesn't end with '(', '[', '{'
        # and isn't empty, and grouping_lpar is '(', then add space.
        if not processed_outer_prefix.endswith(tuple(" ([{")) and not outer_prefix.endswith(
                " "):  # Check original for space
            # If original outer_prefix did not have a trailing space (e.g. "foo=" vs "foo = ")
            # AND we're adding a '(', ensure a space.
            # The .rstrip() above removes the space if it was there. We need to re-evaluate.
            # Let's assume outer_prefix already has the correct spacing (e.g., "foo = ").
            # The .rstrip() is to handle cases where outer_prefix might be "foo =  " (extra spaces).
            # The issue is when outer_prefix is "foo=" and grouping_lpar is "(". We need "foo = (".
            # The ExpressionContext for var assignment *should* be "var name = ".
            # So `outer_prefix.rstrip()` would be "var name =".
            # Then `... + "("` gives "var name =(".
            #
            # The simple fix is if grouping_lpar is active, and outer_prefix is not empty
            # and doesn't already end with a '(', ensure it ends with a space before adding '('.
            if not processed_outer_prefix.endswith(tuple(list("([{."))):  # Dot also doesn't need space.
                space_before_grouping_lpar = " "

    # Check if we're in a variable assignment context and should use hanging indent
    # Only apply hanging indent for moderately long expressions, not extremely long ones
    is_var_assignment_context = outer_prefix.strip().endswith(" =")
    # Count operands (every other child starting from 0: operand, operator, operand, operator, ...)
    operand_count = len(expression.children[0::2]) if expression.children else 0
    is_moderately_long_expression = (
        expression.data == "arith_expr" 
        and operand_count <= 3  # Only 2-3 operands (like "a + b" or "a + b + c")
    )
    use_hanging_indent = (
        not needs_new_grouping_parens 
        and not already_in_parens_from_context 
        and is_var_assignment_context
        and is_safe_operator_expression(expression)
        and is_moderately_long_expression
    )

    if use_hanging_indent:
        # For hanging indent, we integrate the first operand on the same line as the prefix
        # and let the contextless formatter handle the rest with proper indentation
        pass  # We'll handle this case below by modifying the chain elements context
    else:
        # Original logic for cases that need grouping parentheses or are already in parens
        prefix_part = outer_prefix
        if grouping_lpar and prefix_part and not prefix_part.endswith(" ") and not prefix_part.endswith(
                tuple(list("([{."))):
            # If we are adding a grouping_lpar, and the prefix_part (like "var x=")
            # doesn't naturally end with a space or an open paren/bracket/dot, add a space.
            prefix_part += " "

        line_1_content = f"{context.indent_string}{prefix_part}{grouping_lpar}"

        # If outer_prefix was empty and no grouping_lpar, this might be just indent. Avoid if so.
        if line_1_content.strip() != "":
            formatted_lines.append((expression_context.prefix_line, line_1_content.rstrip()))

    # Context for the elements *within* the operator chain (they get indented)
    # Always use a child context for the chain elements themselves when multiline.
    context_for_the_chain_elements = context
    if needs_new_grouping_parens:
        # This function is adding '(...)' around the expression.
        # The elements of the chain should be indented one level
        # relative to the line where the opening grouping_lpar is placed.
        context_for_the_chain_elements = context.create_child_context(
            get_line(expression.children[0]) if expression.children else expression_context.prefix_line
        )
    elif already_in_parens_from_context:
        # We are already inside '(...)' from the calling context (e.g., if condition).
        # The elements of the chain should be indented one level relative to this 'context'.
        # (This is the same as the above case in terms of action, but the reasoning differs slightly)
        context_for_the_chain_elements = context.create_child_context(
            get_line(expression.children[0]) if expression.children else expression_context.prefix_line
        )
    else:
        # No new grouping '()' by this function, AND not already in '()' from context.
        # This is for "safe" operators that are split (e.g., A % B where % is safe).
        # The _format_contextless_operator_chain_based_expression_to_multiple_lines
        # will use this context to apply its hanging indent. The elements should
        # start at the current 'context' indent level.
        context_for_the_chain_elements = context

    # The chain elements themselves don't have further prefix/suffix from the outer ExpressionContext
    # when passed to the 'contextless' formatter.
    if use_hanging_indent:
        # For hanging indent, include the outer prefix with the first operand
        chain_elements_expr_context = ExpressionContext(
            outer_prefix,  # Include the variable assignment prefix
            expression_context.prefix_line,
            outer_suffix,  # Include the suffix
            get_end_line(expression.children[-1]),
        )
    else:
        chain_elements_expr_context = ExpressionContext(
            "",  # No specific prefix for the first element of the contextless chain
            get_line(expression.children[0]),
            "",  # No specific suffix for the last element of the contextless chain
            get_end_line(expression.children[-1]),
        )
    fake_meta = Meta()
    fake_meta.line = get_line(expression.children[0])
    fake_meta.end_line = get_end_line(expression.children[-1])
    fake_chain_expression_node = Tree(
        "contextless_operator_chain_based_expression", expression.children, fake_meta
    )

    chain_element_lines = _format_concrete_expression(
        fake_chain_expression_node,
        chain_elements_expr_context,
        context_for_the_chain_elements,
    )
    formatted_lines.extend(chain_element_lines)

    # Last line: indent + grouping_rpar + outer_suffix
    # Determine the line number for the suffix.
    # It should ideally be the end_line of the last actual content from chain_element_lines,
    # or fallback to expression_context.suffix_line if that's more meaningful.
    suffix_line_num = expression_context.suffix_line
    if chain_element_lines:
        last_internal_line_num, _ = chain_element_lines[-1]
        if last_internal_line_num is not None:
            suffix_line_num = last_internal_line_num
    if expression_context.suffix_line > suffix_line_num and expression_context.suffix_line != -1:  # Prefer if context's suffix_line is later
        suffix_line_num = expression_context.suffix_line
    if suffix_line_num == -1 and expression.children:  # Fallback to end of last child
        suffix_line_num = get_end_line(expression.children[-1])

    line_last_content = f"{context.indent_string}{grouping_rpar}{outer_suffix.lstrip()}"
    # If outer_suffix was empty and no grouping_rpar, this might be just indent. Avoid if so.
    if line_last_content.strip() != "":
        formatted_lines.append((suffix_line_num, line_last_content.rstrip()))

    # Filter out lines that effectively became empty (e.g., if outer_prefix and grouping_lpar were both empty)
    # A line is empty if, after stripping, it's an empty string.
    # context.indent_string itself is not an "empty" content line.
    final_formatted_lines = []
    for ln, l in formatted_lines:
        if l.strip() == "":  # If truly empty after stripping all spaces
            # Only keep if it was an intentionally blank line from somewhere (rare here)
            # or if it's the only line and it's supposed to be blank (also rare)
            # Generally, filter these out.
            pass
        elif l == context.indent_string and not (grouping_lpar or grouping_rpar or outer_prefix or outer_suffix):
            # If the line is JUST the indent string, and there was no real content for it, skip.
            pass
        else:
            final_formatted_lines.append((ln, l))

    return final_formatted_lines


def _format_contextless_operator_chain_based_expression_to_multiple_lines(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    formatted_lines = []  # type: FormattedLines

    operands = expression.children[0::2]
    operators = expression.children[1::2]

    if not operands:
        # This should not happen for a validly parsed operator chain expression.
        return []

    first_operand_node = operands[0]
    # Use the prefix and suffix from the expression context for the first operand
    # This allows hanging indent to work properly
    current_operand_formatted_lines = _format_concrete_expression(
        first_operand_node,
        ExpressionContext(
            expression_context.prefix_string,  # Use provided prefix (e.g., "var x = ")
            expression_context.prefix_line,
            "",  # No operator suffix for the first operand
            get_end_line(first_operand_node),
        ),
        context,
    )
    formatted_lines.extend(current_operand_formatted_lines)

    for i in range(len(operators)):
        operator_node = operators[i]  # This is typically a Token
        next_operand_node = operands[i + 1]

        operator_str = expression_to_str(operator_node)

        if formatted_lines:
            line_number, last_line_content = formatted_lines.pop()
            formatted_lines.append((line_number, f"{last_line_content} {operator_str}"))
        else:
            pass

        # For the last operand, include the suffix if it exists
        is_last_operand = (i == len(operators) - 1)
        operand_suffix = expression_context.suffix_string if is_last_operand else ""
        
        current_operand_formatted_lines = _format_concrete_expression(
            next_operand_node,
            ExpressionContext(
                "",  # No operator prefix
                get_line(next_operand_node),
                operand_suffix,  # Include suffix for last operand
                get_end_line(next_operand_node),
            ),
            context,
        )
        formatted_lines.extend(current_operand_formatted_lines)

    return formatted_lines


def _format_comma_separated_list_to_multiple_lines(
    expression: Tree, expression_context: ExpressionContext, context: Context
) -> FormattedLines:
    a_list = expression.children
    child_context = context.create_child_context(expression_context.prefix_line)
    child_expression_context = ExpressionContext(
        "",
        expression_context.prefix_line,
        "",
        expression_context.suffix_line,
    )
    fake_meta = Meta()
    fake_meta.line = expression_context.prefix_line
    fake_meta.end_line = expression_context.suffix_line
    fake_expression = Tree("contextless_comma_separated_list", a_list, fake_meta)
    formatted_lines = [
        (
            expression_context.prefix_line,
            f"{context.indent_string}{expression_context.prefix_string}",
        )
    ]  # type: FormattedLines
    if len(a_list) > 0:
        formatted_lines += _format_concrete_expression(
            fake_expression, child_expression_context, child_context
        )
    formatted_lines.append(
        (
            expression_context.suffix_line,
            f"{context.indent_string}{expression_context.suffix_string}",
        )
    )
    return formatted_lines


def _format_contextless_comma_separated_list_to_multiple_lines(
    expression: Tree, _: ExpressionContext, context: Context
) -> FormattedLines:
    a_list = expression.children
    elements = [node for node in a_list if not is_any_comma(node)]
    formatted_lines = []  # type: FormattedLines
    trailing_comma_present = is_trailing_comma(a_list[-1]) if len(a_list) > 0 else False
    for i, element in enumerate(elements):
        suffix = "," if i != len(elements) - 1 or trailing_comma_present else ""
        child_expression_context = ExpressionContext(
            "", get_line(element), suffix, get_end_line(element)
        )
        lines = _format_standalone_expression(
            element, child_expression_context, context
        )
        formatted_lines += lines
    return formatted_lines


def _append_to_expression_context(
    str_to_append: str,
    expression_context: ExpressionContext,
) -> ExpressionContext:
    return ExpressionContext(
        f"{expression_context.prefix_string}{str_to_append}",
        expression_context.prefix_line,
        expression_context.suffix_string,
        expression_context.suffix_line,
    )


def _append_to_expression_context_and_pass(
    str_to_append: str,
    expression: Tree,
    expression_context: ExpressionContext,
    context: Context,
) -> FormattedLines:
    new_expression_context = _append_to_expression_context(
        str_to_append, expression_context
    )
    return _format_concrete_expression(expression, new_expression_context, context)


def _append_to_expression_context_and_pass_standalone(
    str_to_append: str,
    expression: Tree,
    expression_context: ExpressionContext,
    context: Context,
) -> FormattedLines:
    new_expression_context = _append_to_expression_context(
        str_to_append, expression_context
    )
    return format_expression(expression, new_expression_context, context)[0]


def _format_await_expression_to_multiple_lines(
    expression: Tree,
    expression_context: ExpressionContext,
    context: Context,
) -> FormattedLines:
    str_to_append = " ".join(token.value for token in expression.children[:-1])
    new_expression_context = ExpressionContext(
        f"{expression_context.prefix_string}{str_to_append} ",
        expression_context.prefix_line,
        expression_context.suffix_string,
        expression_context.suffix_line,
    )
    return _format_concrete_expression(
        expression.children[-1], new_expression_context, context
    )


def _format_annotation_to_multiple_lines(
    annotation: Tree,
    _: ExpressionContext,
    context: Context,
) -> FormattedLines:
    annotation_name = annotation.children[0].value
    if len(annotation.children) == 1:
        return [(get_line(annotation), f"{context.indent_string}@{annotation_name}")]
    new_expression_context = ExpressionContext(
        f"@{annotation_name}", get_line(annotation), "", -1
    )
    return _format_concrete_expression(
        annotation.children[-1], new_expression_context, context
    )


def _collapse_getattr_tree_to_dot_chain(expression: Tree) -> Tree:
    reversed_dot_chain_children = []  # type: List[Node]
    pending_getattr_call_to_match = None
    next_expression_to_process = expression  # type: Optional[Node]
    while next_expression_to_process is not None:
        if isinstance(next_expression_to_process, Token):
            reversed_dot_chain_children.append(next_expression_to_process)
            next_expression_to_process = None
        elif next_expression_to_process.data == "getattr_call":
            pending_getattr_call_to_match = next_expression_to_process
            next_expression_to_process = next_expression_to_process.children[0]
        elif next_expression_to_process.data == "getattr":
            if pending_getattr_call_to_match is None:
                reversed_dot_chain_children += reversed(
                    next_expression_to_process.children[1:]
                )
            else:
                matching_attr = next_expression_to_process.children[-1]
                fake_meta = Meta()
                fake_meta.line = get_line(matching_attr)
                fake_meta.end_line = get_end_line(pending_getattr_call_to_match)
                fake_expression = Tree(
                    "actual_getattr_call",
                    [matching_attr] + pending_getattr_call_to_match.children[1:],
                    fake_meta,
                )
                pending_getattr_call_to_match = None
                reversed_dot_chain_children.append(fake_expression)
                reversed_dot_chain_children += reversed(
                    next_expression_to_process.children[1:-1]
                )
            next_expression_to_process = next_expression_to_process.children[0]
        elif next_expression_to_process.data == "subscr_expr":
            sub_dot_chain = _collapse_subscr_expr_tree_to_dot_chain(
                next_expression_to_process
            )
            reversed_dot_chain_children = reversed_dot_chain_children + list(
                reversed(sub_dot_chain.children)
            )
            next_expression_to_process = None
        else:
            reversed_dot_chain_children.append(next_expression_to_process)
            next_expression_to_process = None
    dot_chain_children = list(reversed(reversed_dot_chain_children))
    fake_meta = Meta()
    fake_meta.line = get_line(dot_chain_children[0])
    fake_meta.end_line = get_end_line(dot_chain_children[-1])
    fake_expression = Tree(
        "dot_chain",
        dot_chain_children,
        fake_meta,
    )
    return fake_expression


def _collapse_subscr_expr_tree_to_dot_chain(expression: Tree) -> Tree:
    subscriptee = expression.children[0]
    subscript_to_match = expression.children[1]
    collapsers = {
        "subscr_expr": _collapse_subscr_expr_tree_to_dot_chain,
        "getattr": _collapse_getattr_tree_to_dot_chain,
        "getattr_call": _collapse_getattr_tree_to_dot_chain,
    }
    sub_dot_chain = (
        collapsers[subscriptee.data](subscriptee).children
        if isinstance(subscriptee, Tree) and subscriptee.data in collapsers
        else [subscriptee]
    )
    matching_expr = sub_dot_chain[-1]
    fake_meta = Meta()
    fake_meta.line = get_line(matching_expr)
    fake_meta.end_line = get_end_line(expression)
    fake_expression = Tree(
        "actual_subscr_expr",
        [matching_expr, subscript_to_match],
        fake_meta,
    )

    dot_chain_children = sub_dot_chain[:-1] + [fake_expression]
    fake_meta = Meta()
    fake_meta.line = get_line(dot_chain_children[0])
    fake_meta.end_line = get_end_line(dot_chain_children[-1])
    fake_expression = Tree(
        "dot_chain",
        dot_chain_children,
        fake_meta,
    )
    return fake_expression


def _format_dot_chain_to_multiple_lines(
    dot_chain: Tree,
    expression_context: ExpressionContext,
    context: Context,
) -> FormattedLines:
    # temporary workaround for likely Godot bug
    # TODO: remove once not needed anymore (this probably should be kept until Godot 5 for compat)
    if expression_contains_lambda(dot_chain):
        return _format_dot_chain_to_multiple_lines_bottom_up(
            dot_chain, expression_context, context
        )
    if is_expression_forcing_multiple_lines(dot_chain, context.standalone_comments):
        return _format_operator_chain_based_expression_to_multiple_lines(
            dot_chain, expression_context, context
        )
    lines_formatted_bottom_up = _format_dot_chain_to_multiple_lines_bottom_up(
        dot_chain, expression_context, context
    )
    if all(
        len(line.replace("\t", " " * TAB_INDENT_SIZE)) <= context.max_line_length
        for line_number, line in lines_formatted_bottom_up
    ):
        return lines_formatted_bottom_up
    return _format_operator_chain_based_expression_to_multiple_lines(
        dot_chain, expression_context, context
    )


def _format_dot_chain_to_multiple_lines_bottom_up(
    dot_chain: Tree,
    expression_context: ExpressionContext,
    context: Context,
) -> FormattedLines:
    last_chain_element = dot_chain.children[-1]
    if (
        isinstance(last_chain_element, Token)
        or last_chain_element.data
        not in [
            "actual_getattr_call",
            "actual_subscr_expr",
        ]
        or (
            last_chain_element.data == "actual_getattr_call"
            and any(expression_contains_lambda(e) for e in dot_chain.children[:-1])
        )
    ):
        return _format_operator_chain_based_expression_to_multiple_lines(
            dot_chain, expression_context, context
        )

    fake_meta = Meta()
    fake_meta.line = get_line(dot_chain)
    fake_meta.end_line = get_end_line(last_chain_element.children[0])
    new_dot_chain = Tree(
        "non_foldable_dot_chain",
        dot_chain.children[:-1] + [last_chain_element.children[0]],
        fake_meta,
    )

    fake_meta = Meta()
    fake_meta.line = get_line(new_dot_chain)
    fake_meta.end_line = get_end_line(last_chain_element)
    new_actual_expr = Tree(
        last_chain_element.data,
        [new_dot_chain] + last_chain_element.children[1:],
        fake_meta,
    )
    return _format_concrete_expression(new_actual_expr, expression_context, context)


def _format_lambda_to_multiple_lines(
    a_lambda: Tree,
    expression_context: ExpressionContext,
    context: Context,
) -> FormattedLines:
    expression_context_for_header = ExpressionContext(
        expression_context.prefix_string, expression_context.prefix_line, "", -1
    )
    header_lines = _format_concrete_expression(
        a_lambda.children[0], expression_context_for_header, context
    )

    block_module = import_module("gdtoolkit.formatter.block")
    function_statement_module = import_module("gdtoolkit.formatter.function_statement")
    child_context = context.create_child_context(expression_context.prefix_line)
    (block_lines, _) = block_module.format_block(
        a_lambda.children[1:],
        function_statement_module.format_func_statement,
        child_context,
    )
    last_block_line_number, last_block_line_content = block_lines[-1]

    return (
        header_lines
        + block_lines[:-1]
        + [
            (
                last_block_line_number,
                f"{last_block_line_content}{expression_context.suffix_string}",
            )
        ]
    )


def _format_lambda_header_to_multiple_lines(
    lambda_header: Tree,
    expression_context: ExpressionContext,
    context: Context,
) -> FormattedLines:
    append_to_prefix = (
        f"func {lambda_header.children[0].value}"
        if isinstance(lambda_header.children[0], Token)
        else "func"
    )
    args_offset = 1 if isinstance(lambda_header.children[0], Token) else 0
    theres_something_after_args = len(lambda_header.children) > args_offset + 1
    optional_type_hint = (
        f" -> {lambda_header.children[args_offset+1]}"
        if theres_something_after_args
        else ""
    )
    prepend_to_suffix = f"{optional_type_hint}:"
    new_expression_context = ExpressionContext(
        f"{expression_context.prefix_string}{append_to_prefix}",
        expression_context.prefix_line,
        f"{prepend_to_suffix}{expression_context.suffix_string}",
        expression_context.suffix_line,
    )
    return _format_concrete_expression(
        lambda_header.children[args_offset], new_expression_context, context
    )
