from pathlib import Path

import pytest

from anne_runtime.calculator_tool import (
    MAX_EXPRESSION_LENGTH,
    MAX_POWER,
    CalculatorError,
    calculate_expression,
)
from anne_runtime.runtime_application import RuntimeApplication
from anne_runtime.tool_contracts import ToolCall, RetryMode


def test_basic_arithmetic():
    assert calculate_expression("2 + 3") == 5
    assert calculate_expression("12 * 4") == 48
    assert calculate_expression("(10 + 5) / 3") == 5.0
    assert calculate_expression("2 ** 8") == 256
    assert calculate_expression("100 % 7") == 2
    assert calculate_expression("-12 + 5") == -7


def test_engineering_decimal_arithmetic():
    result = calculate_expression("9.81 * 5")
    assert result == pytest.approx(49.05)


@pytest.mark.parametrize(
    "expression",
    [
        '__import__("os")',
        'open("file.txt")',
        'os.system("whoami")',
        "some_variable",
        "1 / 0",
        "10 % 0",
        f"2 ** {MAX_POWER + 1}",
        "1 << 4",
        "[1, 2, 3]",
        '{"value": 1}',
    ],
)
def test_rejects_unsafe_or_unsupported_expressions(expression):
    with pytest.raises(CalculatorError):
        calculate_expression(expression)


def test_expression_length_limit():
    expression = "1" * (MAX_EXPRESSION_LENGTH + 1)

    with pytest.raises(CalculatorError, match="exceeds"):
        calculate_expression(expression)


def test_empty_expression_rejected():
    with pytest.raises(CalculatorError, match="cannot be empty"):
        calculate_expression("   ")


def test_boolean_rejected():
    with pytest.raises(CalculatorError):
        calculate_expression("True")


def test_non_numeric_constant_rejected():
    with pytest.raises(CalculatorError):
        calculate_expression('"hello"')


def test_runtime_registers_calculator():
    app = RuntimeApplication(Path.cwd())

    descriptor = app._tool_registry.descriptor("anne.calculator")

    assert descriptor.tool_id == "anne.calculator"
    assert descriptor.version == "1.0.0"
    assert descriptor.required_permissions == ()
    assert descriptor.retry_mode is RetryMode.NONE
    assert descriptor.max_timeout_ms == 1000


def test_runtime_executes_calculator():
    app = RuntimeApplication(Path.cwd())

    call = ToolCall(
        schema_version="1.0",
        request_id="test-calculator-runtime",
        task_id="test-calculator-runtime",
        tool="anne.calculator",
        operation="run",
        arguments={"expression": "9.81 * 5"},
        permissions=(),
        timeout_ms=1000,
        retry_mode=RetryMode.NONE,
        idempotency_key="test-calculator-runtime",
    )

    result = app._tool_executor.execute(call)

    assert result.status.value == "SUCCEEDED"
    assert result.tool == "anne.calculator"
    assert result.tool_version == "1.0.0"
    assert result.error is None
    assert result.result["expression"] == "9.81 * 5"
    assert result.result["value"] == pytest.approx(49.05)
