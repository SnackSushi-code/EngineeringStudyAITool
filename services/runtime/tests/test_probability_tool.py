import pytest

from anne_runtime.probability_tool import (
    ProbabilityError,
    probability,
)


def test_binomial_probability():
    result = probability(
        "binomial",
        n=10,
        k=3,
        p=0.5,
    )

    assert result["result"] == pytest.approx(0.1171875)


def test_normal_pdf():
    result = probability(
        "normal_pdf",
        x=0.0,
        mean=0.0,
        stddev=1.0,
    )

    assert result["result"] == pytest.approx(
        0.3989422804,
        rel=1e-9,
    )


def test_normal_cdf():
    result = probability(
        "normal_cdf",
        x=0.0,
        mean=0.0,
        stddev=1.0,
    )

    assert result["result"] == pytest.approx(0.5)


def test_invalid_probability():
    with pytest.raises(ProbabilityError):
        probability(
            "binomial",
            n=10,
            k=3,
            p=1.5,
        )


def test_invalid_normal_standard_deviation():
    with pytest.raises(ProbabilityError):
        probability(
            "normal_pdf",
            x=0.0,
            mean=0.0,
            stddev=0.0,
        )


def test_probability_dispatcher_returns_operation_and_result():
    result = probability(
        "binomial",
        n=5,
        k=2,
        p=0.5,
    )

    assert result["operation"] == "binomial"
    assert result["result"] == pytest.approx(0.3125)
import math

import pytest

from anne_runtime.probability_tool import (
    ProbabilityError,
    binomial_probability,
    normal_cdf,
    normal_pdf,
    probability,
)


def test_binomial_k_greater_than_n_rejected():
    with pytest.raises(ProbabilityError):
        binomial_probability(
            n=5,
            k=6,
            p=0.5,
        )


def test_binomial_negative_n_rejected():
    with pytest.raises(ProbabilityError):
        binomial_probability(
            n=-1,
            k=0,
            p=0.5,
        )


def test_binomial_negative_k_rejected():
    with pytest.raises(ProbabilityError):
        binomial_probability(
            n=5,
            k=-1,
            p=0.5,
        )


def test_binomial_boundary_probability_zero():
    assert binomial_probability(
        n=5,
        k=0,
        p=0.0,
    ) == pytest.approx(1.0)


def test_binomial_boundary_probability_one():
    assert binomial_probability(
        n=5,
        k=5,
        p=1.0,
    ) == pytest.approx(1.0)


def test_normal_pdf_negative_stddev_rejected():
    with pytest.raises(ProbabilityError):
        normal_pdf(
            x=0.0,
            mean=0.0,
            stddev=-1.0,
        )


def test_normal_pdf_nan_rejected():
    with pytest.raises(ProbabilityError):
        normal_pdf(
            x=math.nan,
            mean=0.0,
            stddev=1.0,
        )


def test_normal_pdf_infinity_rejected():
    with pytest.raises(ProbabilityError):
        normal_pdf(
            x=math.inf,
            mean=0.0,
            stddev=1.0,
        )


def test_normal_cdf_symmetry():
    lower = normal_cdf(
        x=-1.0,
        mean=0.0,
        stddev=1.0,
    )

    upper = normal_cdf(
        x=1.0,
        mean=0.0,
        stddev=1.0,
    )

    assert lower + upper == pytest.approx(1.0)


def test_normal_cdf_shifted_distribution():
    result = normal_cdf(
        x=10.0,
        mean=10.0,
        stddev=2.0,
    )

    assert result == pytest.approx(0.5)


def test_unsupported_probability_operation_rejected():
    with pytest.raises(ProbabilityError):
        probability("explode")


def test_empty_probability_operation_rejected():
    with pytest.raises(ProbabilityError):
        probability("")


def test_probability_operation_is_case_insensitive():
    result = probability(
        "BINOMIAL",
        n=5,
        k=2,
        p=0.5,
    )

    assert result["operation"] == "binomial"
    assert result["result"] == pytest.approx(0.3125)

def test_binomial_probability_rejects_excessive_n():
    with pytest.raises(ProbabilityError, match="n is too large"):
        probability("binomial", n=100_001, k=50_000, p=0.5)

def test_binomial_probability_rejects_k_greater_than_n():
    with pytest.raises(ProbabilityError, match="k cannot be greater than n"):
        probability("binomial", n=5, k=6, p=0.5)


def test_binomial_probability_rejects_negative_n():
    with pytest.raises(ProbabilityError):
        probability("binomial", n=-1, k=0, p=0.5)


def test_binomial_probability_rejects_negative_k():
    with pytest.raises(ProbabilityError):
        probability("binomial", n=5, k=-1, p=0.5)


def test_probability_rejects_unknown_operation():
    with pytest.raises(ProbabilityError, match="Unsupported probability operation"):
        probability("unknown_operation")


def test_probability_rejects_empty_operation():
    with pytest.raises(ProbabilityError, match="non-empty"):
        probability("")


def test_normal_pdf_rejects_nonfinite_input():
    with pytest.raises(ProbabilityError):
        probability("normal_pdf", x=float("inf"))


def test_normal_cdf_rejects_nonfinite_input():
    with pytest.raises(ProbabilityError):
        probability("normal_cdf", x=float("nan"))


def test_normal_pdf_rejects_negative_stddev():
    with pytest.raises(ProbabilityError):
        probability("normal_pdf", x=0.0, stddev=-1.0)


def test_normal_cdf_rejects_zero_stddev():
    with pytest.raises(ProbabilityError):
        probability("normal_cdf", x=0.0, stddev=0.0)


def test_binomial_boundary_n_is_allowed():
    result = probability("binomial", n=100_000, k=0, p=0.5)
    assert result["operation"] == "binomial"
    assert result["result"] == pytest.approx(0.0, abs=1e-300)
