from __future__ import annotations

import ast
import math
from collections.abc import Mapping

from .tool_contracts import ToolExecutionContext


MAX_EXPRESSION_LENGTH = 512
MAX_ITERATIONS = 100_000
MAX_INTEGRATION_STEPS = 100_000
MAX_ABSOLUTE_VALUE = 1e100


class NumericalMethodsError(ValueError):
    """Raised when a numerical-method operation cannot be completed safely."""


_ALLOWED_FUNCTIONS = {
    "abs": abs,
    "acos": math.acos,
    "asin": math.asin,
    "atan": math.atan,
    "cos": math.cos,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "sin": math.sin,
    "sqrt": math.sqrt,
    "tan": math.tan,
}


def _validate_finite(value: float, name: str) -> float:
    value = float(value)

    if not math.isfinite(value):
        raise NumericalMethodsError(f"{name} must be finite.")

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise NumericalMethodsError(
            f"{name} exceeds the maximum allowed magnitude."
        )

    return value


def _validate_expression(expression: str) -> str:
    if not isinstance(expression, str):
        raise NumericalMethodsError("expression must be a string.")

    expression = expression.strip()

    if not expression:
        raise NumericalMethodsError("expression must not be empty.")

    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise NumericalMethodsError(
            f"expression exceeds the maximum length of {MAX_EXPRESSION_LENGTH}."
        )

    return expression


def _compile_expression(expression: str):
    expression = _validate_expression(expression)

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise NumericalMethodsError("invalid numerical expression.") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                raise NumericalMethodsError(
                    "boolean constants are not allowed."
                )

            if not isinstance(node.value, (int, float)):
                raise NumericalMethodsError(
                    "only numeric constants are allowed."
                )

            _validate_finite(float(node.value), "constant")

        elif isinstance(node, ast.Name):
            if node.id != "x":
                raise NumericalMethodsError(
                    f"unknown variable '{node.id}'. Only x is allowed."
                )

        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise NumericalMethodsError(
                    "only approved mathematical functions are allowed."
                )

            if node.func.id not in _ALLOWED_FUNCTIONS:
                raise NumericalMethodsError(
                    f"function '{node.func.id}' is not allowed."
                )

            if node.keywords:
                raise NumericalMethodsError(
                    "keyword function arguments are not allowed."
                )

            if len(node.args) != 1:
                raise NumericalMethodsError(
                    f"function '{node.func.id}' requires exactly one argument."
                )

        elif isinstance(
            node,
            (
                ast.Expression,
                ast.BinOp,
                ast.UnaryOp,
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.Pow,
                ast.USub,
                ast.UAdd,
                ast.Call,
                ast.Load,
                ast.Name,
                ast.Constant,
            ),
        ):
            continue

        else:
            raise NumericalMethodsError(
                f"expression node '{type(node).__name__}' is not allowed."
            )

    try:
        return compile(tree, "<numerical-expression>", "eval")
    except Exception as exc:
        raise NumericalMethodsError(
            "failed to compile numerical expression."
        ) from exc


def _evaluate(compiled, x: float) -> float:
    x = _validate_finite(x, "x")

    try:
        value = eval(
            compiled,
            {"__builtins__": {}},
            {
                "x": x,
                **_ALLOWED_FUNCTIONS,
            },
        )
    except (OverflowError, ZeroDivisionError, ValueError, TypeError) as exc:
        raise NumericalMethodsError(
            f"expression could not be evaluated at x={x}."
        ) from exc

    return _validate_finite(float(value), "expression result")


def _validate_iterations(value, name: str = "max_iterations") -> int:
    if value is None:
        value = 1000

    if isinstance(value, bool):
        raise NumericalMethodsError(f"{name} must be an integer.")

    value = int(value)

    if value <= 0:
        raise NumericalMethodsError(f"{name} must be positive.")

    if value > MAX_ITERATIONS:
        raise NumericalMethodsError(
            f"{name} exceeds the maximum of {MAX_ITERATIONS}."
        )

    return value


def _validate_tolerance(value) -> float:
    if value is None:
        value = 1e-10

    value = _validate_finite(value, "tolerance")

    if value <= 0:
        raise NumericalMethodsError("tolerance must be positive.")

    return value


def _check_bracket(fa: float, fb: float) -> None:
    if fa == 0 or fb == 0:
        return

    if fa * fb > 0:
        raise NumericalMethodsError(
            "root bracket must contain a sign change."
        )


def _result(
    operation: str,
    value: float,
    *,
    iterations: int | None = None,
) -> Mapping[str, object]:
    result: dict[str, object] = {
        "operation": operation,
        "result": _validate_finite(value, "result"),
        "converged": True,
    }

    if iterations is not None:
        result["iterations"] = iterations

    return result


def _bisection(
    compiled,
    lower: float,
    upper: float,
    tolerance: float,
    max_iterations: int,
) -> tuple[float, int]:
    a = _validate_finite(lower, "lower")
    b = _validate_finite(upper, "upper")

    if a == b:
        raise NumericalMethodsError(
            "bisection requires distinct lower and upper bounds."
        )

    if a > b:
        a, b = b, a

    fa = _evaluate(compiled, a)
    fb = _evaluate(compiled, b)

    _check_bracket(fa, fb)

    if fa == 0:
        return a, 0

    if fb == 0:
        return b, 0

    for iteration in range(1, max_iterations + 1):
        midpoint = a + (b - a) / 2.0
        fm = _evaluate(compiled, midpoint)

        if abs(fm) <= tolerance or abs(b - a) <= tolerance:
            return midpoint, iteration

        if fa * fm < 0:
            b = midpoint
            fb = fm
        else:
            a = midpoint
            fa = fm

    raise NumericalMethodsError(
        "bisection did not converge within max_iterations."
    )





def _brent(
    compiled,
    lower: float,
    upper: float,
    tolerance: float,
    max_iterations: int,
) -> tuple[float, int]:
    """
    Safeguarded bracketed root solver.

    Uses secant interpolation when the proposed point is safely inside
    the sign-changing bracket; otherwise falls back to bisection.
    """

    a = _validate_finite(lower, "lower")
    b = _validate_finite(upper, "upper")

    if a == b:
        raise NumericalMethodsError(
            "Brent's method requires distinct lower and upper bounds."
        )

    if a > b:
        a, b = b, a

    fa = _evaluate(compiled, a)
    fb = _evaluate(compiled, b)

    _check_bracket(fa, fb)

    if fa == 0:
        return a, 0

    if fb == 0:
        return b, 0

    for iteration in range(1, max_iterations + 1):
        midpoint = (a + b) / 2.0
        width = b - a

        if abs(width) <= tolerance:
            return midpoint, iteration

        denominator = fb - fa

        if denominator != 0.0 and math.isfinite(denominator):
            candidate = b - fb * (b - a) / denominator
        else:
            candidate = midpoint

        # Safeguard interpolation.
        #
        # The candidate must remain strictly inside the bracket.
        # If it is unsafe, use bisection.
        margin = max(
            tolerance * 0.01,
            math.ulp(max(abs(a), abs(b), 1.0)),
        )

        if (
            not math.isfinite(candidate)
            or candidate <= a + margin
            or candidate >= b - margin
        ):
            candidate = midpoint

        fc = _evaluate(compiled, candidate)

        if abs(fc) <= tolerance:
            return candidate, iteration

        # Maintain the sign-changing bracket.
        if fa * fc < 0:
            b = candidate
            fb = fc
        elif fb * fc < 0:
            a = candidate
            fa = fc
        else:
            # Numerically, candidate is effectively a root.
            return candidate, iteration

    raise NumericalMethodsError(
        "Brent's method did not converge within max_iterations."
    )

def _newton(
    compiled,
    initial_guess: float,
    tolerance: float,
    max_iterations: int,
) -> tuple[float, int]:
    x = _validate_finite(initial_guess, "initial_guess")

    for iteration in range(1, max_iterations + 1):
        fx = _evaluate(compiled, x)

        if abs(fx) <= tolerance:
            return x, iteration

        derivative_step = max(
            math.sqrt(math.ulp(1.0)) * max(abs(x), 1.0),
            1e-8,
        )

        forward = _evaluate(compiled, x + derivative_step)
        backward = _evaluate(compiled, x - derivative_step)

        derivative = (
            forward - backward
        ) / (2.0 * derivative_step)

        derivative_threshold = (
            math.sqrt(math.ulp(1.0))
            * max(abs(fx), 1.0)
        )

        if abs(derivative) <= derivative_threshold:
            raise NumericalMethodsError(
                "Newton method encountered a zero or near-zero derivative."
            )

        next_x = x - fx / derivative
        next_x = _validate_finite(next_x, "Newton iterate")

        if abs(next_x - x) <= tolerance:
            return next_x, iteration

        x = next_x

    raise NumericalMethodsError(
        "Newton method did not converge within max_iterations."
    )


def _secant(
    compiled,
    initial_guess: float,
    second_guess: float,
    tolerance: float,
    max_iterations: int,
) -> tuple[float, int]:
    x0 = _validate_finite(initial_guess, "initial_guess")
    x1 = _validate_finite(second_guess, "second_guess")

    if x0 == x1:
        raise NumericalMethodsError(
            "secant method requires distinct initial guesses."
        )

    f0 = _evaluate(compiled, x0)
    f1 = _evaluate(compiled, x1)

    for iteration in range(1, max_iterations + 1):
        if abs(f0) <= tolerance:
            return x0, iteration

        if abs(f1) <= tolerance:
            return x1, iteration

        denominator = f1 - f0

        denominator_threshold = (
            math.sqrt(math.ulp(1.0))
            * max(abs(f0), abs(f1), 1.0)
        )

        if abs(denominator) <= denominator_threshold:
            raise NumericalMethodsError(
                "secant method encountered a zero or near-zero denominator."
            )

        x2 = x1 - f1 * (x1 - x0) / denominator
        x2 = _validate_finite(x2, "secant iterate")

        if abs(x2 - x1) <= tolerance:
            return x2, iteration

        x0, x1 = x1, x2
        f0, f1 = f1, _evaluate(compiled, x1)

    raise NumericalMethodsError(
        "secant method did not converge within max_iterations."
    )


def _integration_steps(value) -> int:
    if value is None:
        value = 100

    if isinstance(value, bool):
        raise NumericalMethodsError("steps must be an integer.")

    value = int(value)

    if value <= 0:
        raise NumericalMethodsError("steps must be positive.")

    if value > MAX_INTEGRATION_STEPS:
        raise NumericalMethodsError(
            f"steps exceeds the maximum of {MAX_INTEGRATION_STEPS}."
        )

    return value


def _trapezoidal(
    compiled,
    lower: float,
    upper: float,
    steps: int,
) -> tuple[float, int]:
    a = _validate_finite(lower, "lower")
    b = _validate_finite(upper, "upper")

    if a == b:
        return 0.0, 0

    direction = 1.0

    if b < a:
        a, b = b, a
        direction = -1.0

    h = (b - a) / steps

    total = 0.5 * (
        _evaluate(compiled, a)
        + _evaluate(compiled, b)
    )

    for index in range(1, steps):
        total += _evaluate(compiled, a + index * h)

    result = direction * h * total

    return _validate_finite(result, "integration result"), steps


def _simpson(
    compiled,
    lower: float,
    upper: float,
    steps: int,
) -> tuple[float, int]:
    if steps % 2 != 0:
        raise NumericalMethodsError(
            "Simpson's method requires an even number of steps."
        )

    a = _validate_finite(lower, "lower")
    b = _validate_finite(upper, "upper")

    if a == b:
        return 0.0, 0

    direction = 1.0

    if b < a:
        a, b = b, a
        direction = -1.0

    h = (b - a) / steps

    total = (
        _evaluate(compiled, a)
        + _evaluate(compiled, b)
    )

    for index in range(1, steps):
        value = _evaluate(compiled, a + index * h)

        if index % 2 == 0:
            total += 2.0 * value
        else:
            total += 4.0 * value

    result = direction * h * total / 3.0

    return _validate_finite(result, "integration result"), steps


def _validate_difference_step(value) -> float:
    if value is None:
        value = 1e-5

    value = _validate_finite(value, "step_size")

    if value <= 0:
        raise NumericalMethodsError("step_size must be positive.")

    return value


def _forward_difference(
    compiled,
    x: float,
    step_size: float,
) -> float:
    x = _validate_finite(x, "x")
    h = _validate_difference_step(step_size)

    result = (
        _evaluate(compiled, x + h)
        - _evaluate(compiled, x)
    ) / h

    return _validate_finite(result, "derivative result")


def _central_difference(
    compiled,
    x: float,
    step_size: float,
) -> float:
    x = _validate_finite(x, "x")
    h = _validate_difference_step(step_size)

    result = (
        _evaluate(compiled, x + h)
        - _evaluate(compiled, x - h)
    ) / (2.0 * h)

    return _validate_finite(result, "derivative result")


def _backward_difference(
    compiled,
    x: float,
    step_size: float,
) -> float:
    x = _validate_finite(x, "x")
    h = _validate_difference_step(step_size)

    result = (
        _evaluate(compiled, x)
        - _evaluate(compiled, x - h)
    ) / h

    return _validate_finite(result, "derivative result")


def numerical_methods(
    operation: str,
    **arguments,
) -> Mapping[str, object]:
    if not isinstance(operation, str):
        raise NumericalMethodsError("operation must be a string.")

    operation = operation.strip().lower()

    expression = arguments.get("expression")

    supported_operations = {
        "bisection",
        "brent",
        "newton",
        "secant",
        "trapezoidal",
        "simpson",
        "forward_difference",
        "central_difference",
        "backward_difference",
    }

    if operation not in supported_operations:
        raise NumericalMethodsError(
            f"Unsupported numerical method operation '{operation}'."
        )

    compiled = _compile_expression(expression)

    if operation in {"bisection", "brent"}:
        if arguments.get("lower") is None:
            raise NumericalMethodsError("lower is required.")

        if arguments.get("upper") is None:
            raise NumericalMethodsError("upper is required.")

        tolerance = _validate_tolerance(arguments.get("tolerance"))
        max_iterations = _validate_iterations(
            arguments.get("max_iterations")
        )

        if operation == "bisection":
            value, iterations = _bisection(
                compiled,
                arguments["lower"],
                arguments["upper"],
                tolerance,
                max_iterations,
            )
        else:
            value, iterations = _brent(
                compiled,
                arguments["lower"],
                arguments["upper"],
                tolerance,
                max_iterations,
            )

        result = _result(
            operation,
            value,
            iterations=iterations,
        )

        result["root"] = result["result"]

        return result

    if operation == "newton":
        if arguments.get("initial_guess") is None:
            raise NumericalMethodsError("initial_guess is required.")

        tolerance = _validate_tolerance(arguments.get("tolerance"))
        max_iterations = _validate_iterations(
            arguments.get("max_iterations")
        )

        value, iterations = _newton(
            compiled,
            arguments["initial_guess"],
            tolerance,
            max_iterations,
        )

        result = _result(
            operation,
            value,
            iterations=iterations,
        )

        result["root"] = result["result"]

        return result

    if operation == "secant":
        if arguments.get("initial_guess") is None:
            raise NumericalMethodsError("initial_guess is required.")

        if arguments.get("second_guess") is None:
            raise NumericalMethodsError("second_guess is required.")

        tolerance = _validate_tolerance(arguments.get("tolerance"))
        max_iterations = _validate_iterations(
            arguments.get("max_iterations")
        )

        value, iterations = _secant(
            compiled,
            arguments["initial_guess"],
            arguments["second_guess"],
            tolerance,
            max_iterations,
        )

        result = _result(
            operation,
            value,
            iterations=iterations,
        )

        result["root"] = result["result"]

        return result

    if operation in {"trapezoidal", "simpson"}:
        if arguments.get("lower") is None:
            raise NumericalMethodsError("lower is required.")

        if arguments.get("upper") is None:
            raise NumericalMethodsError("upper is required.")

        steps = _integration_steps(arguments.get("steps"))

        if operation == "trapezoidal":
            value, iterations = _trapezoidal(
                compiled,
                arguments["lower"],
                arguments["upper"],
                steps,
            )
        else:
            value, iterations = _simpson(
                compiled,
                arguments["lower"],
                arguments["upper"],
                steps,
            )

        return _result(
            operation,
            value,
            iterations=iterations,
        )

    if arguments.get("x") is None:
        raise NumericalMethodsError("x is required.")

    step_size = _validate_difference_step(
        arguments.get("step_size")
    )

    if operation == "forward_difference":
        value = _forward_difference(
            compiled,
            arguments["x"],
            step_size,
        )
    elif operation == "central_difference":
        value = _central_difference(
            compiled,
            arguments["x"],
            step_size,
        )
    else:
        value = _backward_difference(
            compiled,
            arguments["x"],
            step_size,
        )

    return _result(operation, value)


def numerical_methods_handler(
    context: ToolExecutionContext,
    arguments: Mapping[str, object],
) -> Mapping[str, object]:
    context.raise_if_cancelled()

    result = numerical_methods(
        str(arguments.get("operation", "")),
        **dict(arguments),
    )

    context.raise_if_cancelled()

    return result
