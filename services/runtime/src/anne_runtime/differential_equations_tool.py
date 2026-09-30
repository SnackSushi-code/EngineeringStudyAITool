from __future__ import annotations

import ast
import math
from typing import Any, Mapping


MAX_EXPRESSION_LENGTH = 512
MAX_STEPS = 100_000
MAX_ABSOLUTE_VALUE = 1e100


class DifferentialEquationsError(ValueError):
    """Raised when an ODE input or numerical operation is invalid."""


_ALLOWED_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
}


class _SafeExpression:
    def __init__(self, expression: str) -> None:
        if not isinstance(expression, str):
            raise DifferentialEquationsError(
                "expression must be a string."
            )

        expression = expression.strip()

        if not expression:
            raise DifferentialEquationsError(
                "expression must not be empty."
            )

        if len(expression) > MAX_EXPRESSION_LENGTH:
            raise DifferentialEquationsError(
                f"expression exceeds the maximum length of "
                f"{MAX_EXPRESSION_LENGTH} characters."
            )

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise DifferentialEquationsError(
                "expression is not valid mathematical syntax."
            ) from exc

        self._tree = tree.body
        self._validate(self._tree)

    def _validate(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(
                node.value,
                (int, float),
            ):
                raise DifferentialEquationsError(
                    "expression contains an unsupported constant."
                )

            if not math.isfinite(float(node.value)):
                raise DifferentialEquationsError(
                    "expression contains a non-finite constant."
                )

            return

        if isinstance(node, ast.Name):
            if node.id not in {"t", "y"}:
                raise DifferentialEquationsError(
                    f"unsupported variable or name: {node.id}"
                )
            return

        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, (ast.UAdd, ast.USub)):
                raise DifferentialEquationsError(
                    "unsupported unary operator."
                )

            self._validate(node.operand)
            return

        if isinstance(node, ast.BinOp):
            if not isinstance(
                node.op,
                (
                    ast.Add,
                    ast.Sub,
                    ast.Mult,
                    ast.Div,
                    ast.Pow,
                ),
            ):
                raise DifferentialEquationsError(
                    "unsupported binary operator."
                )

            self._validate(node.left)
            self._validate(node.right)
            return

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise DifferentialEquationsError(
                    "unsupported function call."
                )

            if node.func.id not in _ALLOWED_FUNCTIONS:
                raise DifferentialEquationsError(
                    f"unsupported function: {node.func.id}"
                )

            if node.keywords:
                raise DifferentialEquationsError(
                    "keyword arguments are not supported."
                )

            if len(node.args) != 1:
                raise DifferentialEquationsError(
                    "mathematical functions require exactly one argument."
                )

            self._validate(node.args[0])
            return

        raise DifferentialEquationsError(
            f"unsupported expression element: "
            f"{type(node).__name__}"
        )

    def evaluate(self, t: float, y: float) -> float:
        try:
            value = self._evaluate(self._tree, t, y)
        except DifferentialEquationsError:
            raise
        except (ArithmeticError, ValueError, OverflowError) as exc:
            raise DifferentialEquationsError(
                "expression evaluation failed."
            ) from exc

        if not math.isfinite(value):
            raise DifferentialEquationsError(
                "expression produced a non-finite value."
            )

        if abs(value) > MAX_ABSOLUTE_VALUE:
            raise DifferentialEquationsError(
                "expression result exceeds the maximum magnitude."
            )

        return value

    def _evaluate(
        self,
        node: ast.AST,
        t: float,
        y: float,
    ) -> float:
        if isinstance(node, ast.Constant):
            return float(node.value)

        if isinstance(node, ast.Name):
            return t if node.id == "t" else y

        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate(node.operand, t, y)

            if isinstance(node.op, ast.UAdd):
                return +operand

            return -operand

        if isinstance(node, ast.BinOp):
            left = self._evaluate(node.left, t, y)
            right = self._evaluate(node.right, t, y)

            if isinstance(node.op, ast.Add):
                return left + right

            if isinstance(node.op, ast.Sub):
                return left - right

            if isinstance(node.op, ast.Mult):
                return left * right

            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise DifferentialEquationsError(
                        "division by zero in differential equation."
                    )

                return left / right

            if isinstance(node.op, ast.Pow):
                if abs(right) > 100:
                    raise DifferentialEquationsError(
                        "exponent exceeds the supported bound."
                    )

                return left**right

        if isinstance(node, ast.Call):
            function = _ALLOWED_FUNCTIONS[node.func.id]
            argument = self._evaluate(node.args[0], t, y)
            return float(function(argument))

        raise DifferentialEquationsError(
            "unsupported expression node."
        )


def _validate_number(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise DifferentialEquationsError(
            f"{name} must be a finite number."
        )

    value = float(value)

    if not math.isfinite(value):
        raise DifferentialEquationsError(
            f"{name} must be a finite number."
        )

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise DifferentialEquationsError(
            f"{name} exceeds the maximum magnitude."
        )

    return value


def _validate_step_count(
    t0: float,
    tf: float,
    step_size: float,
) -> int:
    distance = abs(tf - t0)

    if distance == 0:
        return 0

    if step_size <= 0:
        raise DifferentialEquationsError(
            "step_size must be greater than zero."
        )

    estimated_steps = math.ceil(distance / step_size)

    if estimated_steps > MAX_STEPS:
        raise DifferentialEquationsError(
            f"integration requires too many steps; maximum is "
            f"{MAX_STEPS}."
        )

    return estimated_steps


def _validate_result(value: float) -> float:
    if not math.isfinite(value):
        raise DifferentialEquationsError(
            "integration produced a non-finite result."
        )

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise DifferentialEquationsError(
            "integration result exceeds the maximum magnitude."
        )

    return float(value)


def _derivative(
    expression: _SafeExpression,
    t: float,
    y: float,
) -> float:
    return expression.evaluate(t, y)


def _solve_euler(
    expression: _SafeExpression,
    t0: float,
    y0: float,
    tf: float,
    step_size: float,
) -> tuple[float, float, int]:
    if t0 == tf:
        return t0, y0, 0

    direction = 1.0 if tf > t0 else -1.0
    t = t0
    y = y0
    steps = 0

    while direction * (tf - t) > 0:
        h = min(step_size, abs(tf - t)) * direction

        derivative = _derivative(expression, t, y)

        y = _validate_result(y + h * derivative)
        t = t + h

        if abs(tf - t) < 1e-14:
            t = tf

        steps += 1

    return t, y, steps


def _solve_rk4(
    expression: _SafeExpression,
    t0: float,
    y0: float,
    tf: float,
    step_size: float,
) -> tuple[float, float, int]:
    if t0 == tf:
        return t0, y0, 0

    direction = 1.0 if tf > t0 else -1.0
    t = t0
    y = y0
    steps = 0

    while direction * (tf - t) > 0:
        h = min(step_size, abs(tf - t)) * direction

        k1 = _derivative(expression, t, y)

        k2 = _derivative(
            expression,
            t + h / 2.0,
            _validate_result(y + h * k1 / 2.0),
        )

        k3 = _derivative(
            expression,
            t + h / 2.0,
            _validate_result(y + h * k2 / 2.0),
        )

        k4 = _derivative(
            expression,
            t + h,
            _validate_result(y + h * k3),
        )

        y = _validate_result(
            y + h * (
                k1 + 2.0 * k2 + 2.0 * k3 + k4
            ) / 6.0
        )

        t = t + h

        if abs(tf - t) < 1e-14:
            t = tf

        steps += 1

    return t, y, steps


def differential_equations(
    *,
    operation: str,
    expression: str,
    t0: float,
    y0: float,
    tf: float,
    step_size: float,
) -> dict[str, Any]:
    if operation not in {"euler", "rk4"}:
        raise DifferentialEquationsError(
            f"Unsupported differential equation operation: {operation}"
        )

    t0 = _validate_number("t0", t0)
    y0 = _validate_number("y0", y0)
    tf = _validate_number("tf", tf)
    step_size = _validate_number("step_size", step_size)

    if step_size <= 0:
        raise DifferentialEquationsError(
            "step_size must be greater than zero."
        )

    _validate_step_count(t0, tf, step_size)

    parsed_expression = _SafeExpression(expression)

    if operation == "euler":
        t, y, steps = _solve_euler(
            parsed_expression,
            t0,
            y0,
            tf,
            step_size,
        )
    else:
        t, y, steps = _solve_rk4(
            parsed_expression,
            t0,
            y0,
            tf,
            step_size,
        )

    return {
        "operation": operation,
        "t": float(t),
        "y": float(y),
        "steps": steps,
    }


def differential_equations_handler(
    context: Any,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    context.raise_if_cancelled()

    result = differential_equations(
        operation=arguments["operation"],
        expression=arguments["expression"],
        t0=arguments["t0"],
        y0=arguments["y0"],
        tf=arguments["tf"],
        step_size=arguments["step_size"],
    )

    context.raise_if_cancelled()

    return result
