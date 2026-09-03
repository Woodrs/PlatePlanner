"""Concentration feature must remain a stub in the MVP."""

import pytest

from plateplanner.concentration import (
    ConcentrationNotImplementedError,
    concentration_status_message,
    is_concentration_mode_available,
    volume_from_concentration,
)


def test_concentration_not_available():
    assert is_concentration_mode_available() is False
    assert concentration_status_message()


def test_volume_from_concentration_raises():
    with pytest.raises(ConcentrationNotImplementedError):
        volume_from_concentration(100.0, 10.0, 50.0)
