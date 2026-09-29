from __future__ import annotations

import ast
import math
from typing import Any, Mapping

from .tool_contracts import ToolExecutionError


MAX_EXPRESSION_LENGTH = 512
MAX_POWER = 100
MAX_ABSOLUTE_RESULT = 1e100


class CalculatorError(ToolExecutionError):
    """Raised when a calculator expression is invalid or unsafe."""


_ALLOWED_BINARY_OPERATORS = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
    ast.Mod: lambda left, right: left % right,
    ast.Pow: lambda left, right: left ** right,
}

_ALLOWED_UNARY_OPERATORS = {
    ast.UAdd: lambda value: +value,
    ast.USub: lambda value: -value,
}


def calculate_expression(expression: str) -> int | float:
    """Safely evaluate a restricted arithmetic expression."""
    if not isinstance(expression, str):
        raise CalculatorError("Calculator expression must be a string.")

    expression = expression.strip()

    if not expression:
        raise CalculatorError("Calculator expression cannot be empty.")

    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise CalculatorError(
            f"Calculator expression exceeds {MAX_EXPRESSION_LENGTH} characters."
        )

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError("Invalid calculator expression.") from exc

    value = _evaluate_node(tree.body)

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculatorError("Calculator result must be numeric.")

    if isinstance(value, float) and not math.isfinite(value):
        raise CalculatorError("Calculator result must be finite.")

    if abs(value) > MAX_ABSOLUTE_RESULT:
        raise CalculatorError("Calculator result exceeds the allowed magnitude.")

    return value


def _evaluate_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise CalculatorError("Boolean values are not allowed.")

        if isinstance(node.value, (int, float)):
            if isinstance(node.value, float) and not math.isfinite(node.value):
                raise CalculatorError("Non-finite numbers are not allowed.")
            return node.value

        raise CalculatorError("Only numeric constants are allowed.")

    if isinstance(node, ast.UnaryOp):
        operation = _ALLOWED_UNARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise CalculatorError("Unsupported unary operator.")
        return operation(_evaluate_node(node.operand))

    if isinstance(node, ast.BinOp):
        operation = _ALLOWED_BINARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise CalculatorError("Unsupported binary operator.")

        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)

        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_POWER:
                raise CalculatorError(
                    f"Exponent magnitude cannot exceed {MAX_POWER}."
                )

        if isinstance(node.op, (ast.Div, ast.Mod)) and right == 0:
            raise CalculatorError("Division or modulo by zero is not allowed.")

        try:
            result = operation(left, right)
        except (ArithmeticError, OverflowError) as exc:
            raise CalculatorError("Calculator arithmetic failed.") from exc

        if isinstance(result, float) and not math.isfinite(result):
            raise CalculatorError("Calculator result must be finite.")

        if abs(result) > MAX_ABSOLUTE_RESULT:
            raise CalculatorError("Calculator result exceeds the allowed magnitude.")

        return result

    raise CalculatorError(
        f"Unsupported calculator expression node: {type(node).__name__}."
    )


def calculator_handler(
    context: Any,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Tool handler for the Ann-E engineering calculator."""
    if context.is_cancelled():
        context.raise_if_cancelled()

    expression = arguments["expression"]
    value = calculate_expression(expression)

    return {
        "expression": expression,
        "value": value,
    }
