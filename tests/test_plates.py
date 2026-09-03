"""Tests for plate geometry and well IDs."""

import pytest

from plateplanner.plates import (
    all_wells,
    get_plate_format,
    normalize_well_id,
    parse_well_id,
    validate_wells,
    well_id,
    well_in_plate,
)


def test_well_id_format():
    assert well_id(0, 0) == "A01"
    assert well_id(0, 11) == "A12"
    assert well_id(7, 11) == "H12"
    assert well_id(15, 23) == "P24"


def test_parse_and_normalize():
    assert parse_well_id("A01") == (0, 0)
    assert parse_well_id("a1") == (0, 0)
    assert normalize_well_id("b2") == "B02"
    assert normalize_well_id("H12") == "H12"


def test_all_wells_counts():
    assert len(all_wells("96")) == 96
    assert len(all_wells("384")) == 384
    assert all_wells("96")[0] == "A01"
    assert all_wells("96")[-1] == "H12"


def test_well_in_plate():
    assert well_in_plate("A01", "96")
    assert not well_in_plate("I01", "96")
    assert well_in_plate("P24", "384")
    assert not well_in_plate("P25", "384")


def test_validate_wells():
    assert validate_wells(["a1", "H12"], "96") == ["A01", "H12"]
    with pytest.raises(ValueError):
        validate_wells(["I01"], "96")


def test_get_plate_format_rejects_unknown():
    with pytest.raises(ValueError):
        get_plate_format("24")
