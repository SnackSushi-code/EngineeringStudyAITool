import math

import pytest

from anne_runtime.statistics_tool import (
    StatisticsError,
    statistics_mean,
    statistics_median,
    statistics_mode,
    statistics_variance,
    statistics_standard_deviation,
    statistics_minimum,
    statistics_maximum,
    statistics_range,
    statistics_sum,
    statistics_percentile,
    statistics_rms,
    statistics,
)


def test_calculates_mean():
    assert statistics_mean([1, 2, 3, 4, 5]) == pytest.approx(3.0)


def test_calculates_median_for_odd_dataset():
    assert statistics_median([5, 1, 3]) == pytest.approx(3.0)


def test_calculates_median_for_even_dataset():
    assert statistics_median([4, 1, 3, 2]) == pytest.approx(2.5)


def test_calculates_mode():
    assert statistics_mode([1, 2, 2, 3, 3, 3, 4]) == 3.0


def test_rejects_dataset_without_unique_mode():
    with pytest.raises(StatisticsError, match="mode"):
        statistics_mode([1, 1, 2, 2])


def test_calculates_population_variance():
    assert statistics_variance([1, 2, 3, 4, 5]) == pytest.approx(2.0)


def test_calculates_sample_variance():
    assert statistics_variance(
        [1, 2, 3, 4, 5],
        sample=True,
    ) == pytest.approx(2.5)


def test_calculates_population_standard_deviation():
    assert statistics_standard_deviation([1, 2, 3, 4, 5]) == pytest.approx(
        math.sqrt(2.0)
    )


def test_calculates_sample_standard_deviation():
    assert statistics_standard_deviation(
        [1, 2, 3, 4, 5],
        sample=True,
    ) == pytest.approx(math.sqrt(2.5))


def test_calculates_minimum():
    assert statistics_minimum([5, 2, 9, 1]) == 1.0


def test_calculates_maximum():
    assert statistics_maximum([5, 2, 9, 1]) == 9.0


def test_calculates_range():
    assert statistics_range([5, 2, 9, 1]) == 8.0


def test_calculates_sum():
    assert statistics_sum([1, 2, 3, 4]) == 10.0


def test_calculates_percentile():
    assert statistics_percentile(
        [10, 20, 30, 40],
        50,
    ) == pytest.approx(25.0)


def test_calculates_rms():
    assert statistics_rms([3, 4]) == pytest.approx(math.sqrt(12.5))


def test_rejects_empty_dataset():
    with pytest.raises(StatisticsError):
        statistics_mean([])


def test_rejects_non_numeric_values():
    with pytest.raises(StatisticsError):
        statistics_mean([1, 2, "3"])


def test_rejects_boolean_values():
    with pytest.raises(StatisticsError):
        statistics_mean([1, True, 3])


def test_rejects_non_finite_values():
    with pytest.raises(StatisticsError):
        statistics_mean([1, float("nan"), 3])


def test_rejects_dataset_that_is_too_large():
    with pytest.raises(StatisticsError, match="maximum"):
        statistics_mean(list(range(10001)))


def test_rejects_invalid_percentile():
    with pytest.raises(StatisticsError, match="percentile"):
        statistics_percentile([1, 2, 3], 101)


def test_rejects_sample_variance_with_one_value():
    with pytest.raises(StatisticsError, match="sample"):
        statistics_variance([1], sample=True)


def test_dispatcher_returns_operation_and_result():
    result = statistics(
        "mean",
        values=[1, 2, 3, 4],
    )

    assert result == {
        "operation": "mean",
        "result": 2.5,
    }
