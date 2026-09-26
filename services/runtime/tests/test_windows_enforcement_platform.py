from __future__ import annotations

import os

import pytest

from anne_runtime.windows_enforcement import (
    WINDOWS_ADAPTER_VERSION,
    WindowsEnforcementAdapter,
    WindowsEnforcementError,
)


def test_windows_enforcement_module_imports() -> None:
    assert isinstance(WINDOWS_ADAPTER_VERSION, str)
    assert WINDOWS_ADAPTER_VERSION == "0.2.1"


@pytest.mark.skipif(
    os.name == "nt",
    reason="Non-Windows guard is only applicable outside Windows.",
)
def test_windows_adapter_rejects_non_windows_platform() -> None:
    with pytest.raises(WindowsEnforcementError):
        WindowsEnforcementAdapter()
