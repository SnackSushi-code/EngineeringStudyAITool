from __future__ import annotations

import math
from typing import Any, Mapping

from .tool_contracts import ToolExecutionError


MAX_ABSOLUTE_VALUE = 1e100


class UnitConversionError(ToolExecutionError):
    """Raised when a unit conversion is invalid or unsafe."""


# Each unit is represented as:
#   dimension -> (multiplier_to_base_unit, additive_offset_to_base_unit)
#
# Base units:
#   length      -> meter
#   mass        -> kilogram
#   time        -> second
#   temperature -> kelvin
#   area        -> square meter
#   volume      -> cubic meter
#   speed       -> meter/second
#   force       -> newton
#   pressure    -> pascal
#   energy      -> joule
#   power       -> watt
#
# Temperature is handled separately because it requires an offset.
_UNITS: dict[str, tuple[str, float]] = {
    # Length
    "m": ("length", 1.0),
    "meter": ("length", 1.0),
    "meters": ("length", 1.0),
    "km": ("length", 1000.0),
    "kilometer": ("length", 1000.0),
    "kilometers": ("length", 1000.0),
    "cm": ("length", 0.01),
    "centimeter": ("length", 0.01),
    "centimeters": ("length", 0.01),
    "mm": ("length", 0.001),
    "millimeter": ("length", 0.001),
    "millimeters": ("length", 0.001),
    "in": ("length", 0.0254),
    "inch": ("length", 0.0254),
    "inches": ("length", 0.0254),
    "ft": ("length", 0.3048),
    "foot": ("length", 0.3048),
    "feet": ("length", 0.3048),
    "yd": ("length", 0.9144),
    "yard": ("length", 0.9144),
    "yards": ("length", 0.9144),
    "mi": ("length", 1609.344),
    "mile": ("length", 1609.344),
    "miles": ("length", 1609.344),

    # Mass
    "kg": ("mass", 1.0),
    "kilogram": ("mass", 1.0),
    "kilograms": ("mass", 1.0),
    "g": ("mass", 0.001),
    "gram": ("mass", 0.001),
    "grams": ("mass", 0.001),
    "mg": ("mass", 0.000001),
    "milligram": ("mass", 0.000001),
    "milligrams": ("mass", 0.000001),
    "lb": ("mass", 0.45359237),
    "lbs": ("mass", 0.45359237),
    "pound": ("mass", 0.45359237),
    "pounds": ("mass", 0.45359237),
    "oz": ("mass", 0.028349523125),
    "ounce": ("mass", 0.028349523125),
    "ounces": ("mass", 0.028349523125),

    # Time
    "s": ("time", 1.0),
    "sec": ("time", 1.0),
    "second": ("time", 1.0),
    "seconds": ("time", 1.0),
    "min": ("time", 60.0),
    "minute": ("time", 60.0),
    "minutes": ("time", 60.0),
    "h": ("time", 3600.0),
    "hr": ("time", 3600.0),
    "hour": ("time", 3600.0),
    "hours": ("time", 3600.0),
    "day": ("time", 86400.0),
    "days": ("time", 86400.0),

    # Area
    "m2": ("area", 1.0),
    "m^2": ("area", 1.0),
    "km2": ("area", 1_000_000.0),
    "km^2": ("area", 1_000_000.0),
    "cm2": ("area", 0.0001),
    "cm^2": ("area", 0.0001),
    "ft2": ("area", 0.09290304),
    "ft^2": ("area", 0.09290304),
    "in2": ("area", 0.00064516),
    "in^2": ("area", 0.00064516),

    # Volume
    "m3": ("volume", 1.0),
    "m^3": ("volume", 1.0),
    "cm3": ("volume", 0.000001),
    "cm^3": ("volume", 0.000001),
    "l": ("volume", 0.001),
    "liter": ("volume", 0.001),
    "liters": ("volume", 0.001),
    "ml": ("volume", 0.000001),
    "milliliter": ("volume", 0.000001),
    "milliliters": ("volume", 0.000001),
    "ft3": ("volume", 0.028316846592),
    "ft^3": ("volume", 0.028316846592),
    "in3": ("volume", 0.000016387064),
    "in^3": ("volume", 0.000016387064),

    # Speed
    "m/s": ("speed", 1.0),
    "mps": ("speed", 1.0),
    "km/h": ("speed", 1000.0 / 3600.0),
    "kph": ("speed", 1000.0 / 3600.0),
    "mph": ("speed", 1609.344 / 3600.0),
    "ft/s": ("speed", 0.3048),
    "fps": ("speed", 0.3048),

    # Force
    "n": ("force", 1.0),
    "newton": ("force", 1.0),
    "newtons": ("force", 1.0),
    "kn": ("force", 1000.0),
    "kilonewton": ("force", 1000.0),
    "kilonewtons": ("force", 1000.0),
    "lbf": ("force", 4.4482216152605),
    "lb-f": ("force", 4.4482216152605),

    # Pressure
    "pa": ("pressure", 1.0),
    "pascal": ("pressure", 1.0),
    "pascals": ("pressure", 1.0),
    "kpa": ("pressure", 1000.0),
    "kilopascal": ("pressure", 1000.0),
    "kilopascals": ("pressure", 1000.0),
    "mpa": ("pressure", 1_000_000.0),
    "megapascal": ("pressure", 1_000_000.0),
    "megapascals": ("pressure", 1_000_000.0),
    "bar": ("pressure", 100_000.0),
    "atm": ("pressure", 101_325.0),
    "psi": ("pressure", 6894.757293168),
    "ksi": ("pressure", 6_894_757.293168),

    # Energy
    "j": ("energy", 1.0),
    "joule": ("energy", 1.0),
    "joules": ("energy", 1.0),
    "kj": ("energy", 1000.0),
    "kilojoule": ("energy", 1000.0),
    "kilojoules": ("energy", 1000.0),
    "wh": ("energy", 3600.0),
    "watt-hour": ("energy", 3600.0),
    "watt-hours": ("energy", 3600.0),
    "kwh": ("energy", 3_600_000.0),
    "kilowatt-hour": ("energy", 3_600_000.0),
    "kilowatt-hours": ("energy", 3_600_000.0),

    # Power
    "w": ("power", 1.0),
    "watt": ("power", 1.0),
    "watts": ("power", 1.0),
    "kw": ("power", 1000.0),
    "kilowatt": ("power", 1000.0),
    "kilowatts": ("power", 1000.0),
    "mw": ("power", 1_000_000.0),
    "megawatt": ("power", 1_000_000.0),
    "megawatts": ("power", 1_000_000.0),
}


_TEMPERATURE_UNITS = {
    "k": "K",
    "kelvin": "K",
    "kelvins": "K",
    "c": "C",
    "celsius": "C",
    "f": "F",
    "fahrenheit": "F",
}


def _normalize_unit(unit: str) -> str:
    if not isinstance(unit, str):
        raise UnitConversionError("Unit must be a string.")

    normalized = unit.strip().lower()

    if not normalized:
        raise UnitConversionError("Unit cannot be empty.")

    return normalized


def _validate_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnitConversionError("Conversion value must be numeric.")

    value = float(value)

    if not math.isfinite(value):
        raise UnitConversionError("Conversion value must be finite.")

    if abs(value) > MAX_ABSOLUTE_VALUE:
        raise UnitConversionError("Conversion value exceeds the allowed magnitude.")

    return value


def _convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    source = _TEMPERATURE_UNITS[from_unit]
    target = _TEMPERATURE_UNITS[to_unit]

    if source == "K":
        kelvin = value
    elif source == "C":
        kelvin = value + 273.15
    else:
        kelvin = (value - 32.0) * 5.0 / 9.0 + 273.15

    if target == "K":
        result = kelvin
    elif target == "C":
        result = kelvin - 273.15
    else:
        result = (kelvin - 273.15) * 9.0 / 5.0 + 32.0

    if not math.isfinite(result):
        raise UnitConversionError("Conversion result must be finite.")

    return result


def convert_units(value: int | float, from_unit: str, to_unit: str) -> float:
    """Convert a value between compatible engineering units."""
    numeric_value = _validate_number(value)
    source = _normalize_unit(from_unit)
    target = _normalize_unit(to_unit)

    if source in _TEMPERATURE_UNITS or target in _TEMPERATURE_UNITS:
        if source not in _TEMPERATURE_UNITS or target not in _TEMPERATURE_UNITS:
            raise UnitConversionError("Temperature units cannot be converted to non-temperature units.")
        return _convert_temperature(numeric_value, source, target)

    if source not in _UNITS:
        raise UnitConversionError(f"Unsupported source unit: {from_unit}")

    if target not in _UNITS:
        raise UnitConversionError(f"Unsupported target unit: {to_unit}")

    source_dimension, source_factor = _UNITS[source]
    target_dimension, target_factor = _UNITS[target]

    if source_dimension != target_dimension:
        raise UnitConversionError(
            f"Incompatible units: {from_unit} and {to_unit}."
        )

    base_value = numeric_value * source_factor
    result = base_value / target_factor

    if not math.isfinite(result):
        raise UnitConversionError("Conversion result must be finite.")

    result = round(result, 12)

    if abs(result) > MAX_ABSOLUTE_VALUE:
        raise UnitConversionError("Conversion result exceeds the allowed magnitude.")

    return result


def unit_conversion_handler(
    context: Any,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Tool handler for deterministic engineering unit conversion."""
    if context.is_cancelled():
        context.raise_if_cancelled()

    value = arguments["value"]
    from_unit = arguments["from_unit"]
    to_unit = arguments["to_unit"]

    result = convert_units(value, from_unit, to_unit)

    return {
        "value": value,
        "from_unit": from_unit,
        "to_unit": to_unit,
        "result": result,
    }
