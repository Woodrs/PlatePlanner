"""Unit tests for Tempest concentration / volume planning."""

import pytest

from plateplanner.concentration import (
    ConcentrationError,
    StockDefinition,
    WellVolumeInputs,
    concentration_status_message,
    free_dispense_volume,
    is_concentration_mode_available,
    max_achievable_concentration,
    plan_plate_concentrations,
    plan_well_concentrations,
    reagent_volume_ul,
    volume_from_concentration,
)
from plateplanner.exporters.tempest import export_tempest_csv, export_tempest_rows


def test_concentration_mode_available():
    assert is_concentration_mode_available() is True
    assert concentration_status_message()


def test_example_free_volume_200_100_10():
    """Product example: 200 − 100 − 10 = 90 µL free."""
    assert free_dispense_volume(200.0, 100.0, 10.0) == 90.0
    vols = WellVolumeInputs(200.0, 100.0, 10.0)
    assert vols.free_volume_ul() == 90.0


def test_free_volume_zero_and_negative():
    assert free_dispense_volume(100.0, 100.0, 0.0) == 0.0
    assert free_dispense_volume(100.0, 80.0, 30.0) == -10.0


def test_c_max_final_volume_basis():
    # C_max = C_stock * V_free / V_target = 1000 * 90 / 200 = 450
    c_max = max_achievable_concentration(1000.0, 90.0, 200.0)
    assert c_max == pytest.approx(450.0)


def test_reagent_volume_formula():
    # V = C_target * V_target / C_stock = 50 * 200 / 1000 = 10
    assert reagent_volume_ul(50.0, 1000.0, 200.0) == pytest.approx(10.0)
    assert volume_from_concentration(1000.0, 50.0, 200.0) == pytest.approx(10.0)


def test_reagent_volume_zero_target():
    assert reagent_volume_ul(0.0, 1000.0, 200.0) == 0.0


def test_reagent_volume_zero_stock_nonzero_target():
    with pytest.raises(ConcentrationError):
        reagent_volume_ul(10.0, 0.0, 200.0)


def test_plan_well_basic_single_reagent():
    stocks = [StockDefinition(channel=1, stock_concentration=1000.0, name="DrugA")]
    vols = WellVolumeInputs(200.0, 100.0, 10.0)
    result = plan_well_concentrations(
        "A01", vols, stocks, {1: 50.0}, normalize_channel=12
    )
    assert result.free_volume_ul == 90.0
    assert result.reagent_volumes_ul[1] == pytest.approx(10.0)
    assert result.normalize_volume_ul == pytest.approx(80.0)  # 90 - 10
    assert result.max_concentrations[1] == pytest.approx(450.0)
    # Volume identity: base + reagent + normalize + inoc = target
    total = (
        result.base_media_volume_ul
        + result.total_reagent_ul
        + result.normalize_volume_ul
        + result.inoculation_volume_ul
    )
    assert total == pytest.approx(200.0)


def test_plan_well_exceeds_c_max():
    stocks = [StockDefinition(channel=1, stock_concentration=1000.0)]
    vols = WellVolumeInputs(200.0, 100.0, 10.0)
    # C_max = 450; request 500
    with pytest.raises(ConcentrationError, match="exceeds"):
        plan_well_concentrations("A01", vols, stocks, {1: 500.0})


def test_plan_well_negative_free_volume():
    stocks = [StockDefinition(channel=1, stock_concentration=100.0)]
    vols = WellVolumeInputs(50.0, 40.0, 20.0)  # free = -10
    with pytest.raises(ConcentrationError, match="free volume is negative"):
        plan_well_concentrations("B02", vols, stocks, {1: 1.0})


def test_plan_well_non_negative_validation():
    stocks = [StockDefinition(channel=1, stock_concentration=100.0)]
    with pytest.raises(ConcentrationError):
        plan_well_concentrations(
            "A01",
            WellVolumeInputs(-1.0, 0.0, 0.0),
            stocks,
            {1: 0.0},
        )


def test_multi_reagent_within_free_volume():
    stocks = [
        StockDefinition(channel=1, stock_concentration=1000.0, name="A"),
        StockDefinition(channel=2, stock_concentration=500.0, name="B"),
    ]
    vols = WellVolumeInputs(200.0, 100.0, 10.0)  # free 90
    # V1 = 50*200/1000 = 10; V2 = 25*200/500 = 10; total 20 <= 90
    result = plan_well_concentrations(
        "A01", vols, stocks, {1: 50.0, 2: 25.0}, normalize_channel=12
    )
    assert result.reagent_volumes_ul[1] == pytest.approx(10.0)
    assert result.reagent_volumes_ul[2] == pytest.approx(10.0)
    assert result.normalize_volume_ul == pytest.approx(70.0)


def test_multi_reagent_exceeds_free_volume():
    stocks = [
        StockDefinition(channel=1, stock_concentration=100.0),
        StockDefinition(channel=2, stock_concentration=100.0),
    ]
    vols = WellVolumeInputs(200.0, 100.0, 10.0)  # free 90
    # V1 = 40*200/100 = 80; V2 = 20*200/100 = 40; sum 120 > 90
    with pytest.raises(ConcentrationError, match="exceeds free volume"):
        plan_well_concentrations("A01", vols, stocks, {1: 40.0, 2: 20.0})


def test_multi_reagent_cap_scales():
    stocks = [
        StockDefinition(channel=1, stock_concentration=100.0),
        StockDefinition(channel=2, stock_concentration=100.0),
    ]
    vols = WellVolumeInputs(200.0, 100.0, 10.0)  # free 90
    result = plan_well_concentrations(
        "A01",
        vols,
        stocks,
        {1: 40.0, 2: 20.0},
        cap_to_free_volume=True,
    )
    assert result.total_reagent_ul == pytest.approx(90.0)
    assert result.normalize_volume_ul == pytest.approx(0.0)
    # Proportional: 80:40 → 60:30
    assert result.reagent_volumes_ul[1] == pytest.approx(60.0)
    assert result.reagent_volumes_ul[2] == pytest.approx(30.0)


def test_volume_normalizing_fills_remainder():
    stocks = [StockDefinition(channel=1, stock_concentration=2000.0)]
    vols = WellVolumeInputs(200.0, 100.0, 10.0)
    # V_reagent = 100*200/2000 = 10 → normalize 80
    result = plan_well_concentrations(
        "C03", vols, stocks, {1: 100.0}, normalize_channel=12
    )
    assert result.normalize_channel == 12
    assert result.normalize_volume_ul == pytest.approx(80.0)


def test_plan_plate_and_tempest_export_includes_normalize():
    stocks = [
        StockDefinition(channel=1, stock_concentration=1000.0, name="DrugA"),
        StockDefinition(channel=2, stock_concentration=500.0, name="DrugB"),
    ]
    result = plan_plate_concentrations(
        plate_format="96",
        plate_id="CONC_001",
        wells=["A01", "A02"],
        defaults=WellVolumeInputs(200.0, 100.0, 10.0),
        stocks=stocks,
        plate_targets={1: 50.0, 2: 25.0},
        normalize_channel=12,
        normalize_label="base media",
    )
    assert set(result.wells) == {"A01", "A02"}
    plan = result.to_tempest_plan(include_normalize=True)
    rows = export_tempest_rows(plan)
    channels = {int(r["stock_channel"]) for r in rows}
    assert 1 in channels and 2 in channels and 12 in channels
    # Each well: ch1=10, ch2=10, ch12=70
    by = {(r["well"], int(r["stock_channel"])): float(r["volume_ul"]) for r in rows}
    assert by[("A01", 1)] == pytest.approx(10.0)
    assert by[("A01", 2)] == pytest.approx(10.0)
    assert by[("A01", 12)] == pytest.approx(70.0)
    assert by[("A02", 12)] == pytest.approx(70.0)
    csv_text = export_tempest_csv(plan)
    assert "stock_channel" in csv_text


def test_plan_plate_per_well_targets_and_volume_overrides():
    stocks = [StockDefinition(channel=1, stock_concentration=1000.0)]
    result = plan_plate_concentrations(
        plate_format="96",
        plate_id="OV",
        wells=["A01", "A02"],
        defaults=WellVolumeInputs(200.0, 100.0, 10.0),
        stocks=stocks,
        plate_targets={1: 50.0},
        well_targets={"A02": {1: 100.0}},
        well_volume_overrides={
            "A02": WellVolumeInputs(200.0, 50.0, 10.0),  # free 140
        },
        normalize_channel=12,
    )
    assert result.wells["A01"].reagent_volumes_ul[1] == pytest.approx(10.0)
    assert result.wells["A01"].free_volume_ul == 90.0
    # A02: V = 100*200/1000 = 20; free = 140; normalize = 120
    assert result.wells["A02"].reagent_volumes_ul[1] == pytest.approx(20.0)
    assert result.wells["A02"].free_volume_ul == 140.0
    assert result.wells["A02"].normalize_volume_ul == pytest.approx(120.0)


def test_exclude_normalize_from_tempest_plan():
    stocks = [StockDefinition(channel=1, stock_concentration=1000.0)]
    result = plan_plate_concentrations(
        plate_format="96",
        plate_id="X",
        wells=["A01"],
        defaults=WellVolumeInputs(200.0, 100.0, 10.0),
        stocks=stocks,
        plate_targets={1: 50.0},
        normalize_channel=12,
    )
    plan = result.to_tempest_plan(include_normalize=False)
    assert 12 not in plan.stock_volumes
    assert 1 in plan.stock_volumes


def test_stock_channel_bounds():
    with pytest.raises(ConcentrationError):
        StockDefinition(channel=0, stock_concentration=1.0)
    with pytest.raises(ConcentrationError):
        StockDefinition(channel=13, stock_concentration=1.0)


def test_unknown_channel_in_targets():
    stocks = [StockDefinition(channel=1, stock_concentration=100.0)]
    with pytest.raises(ConcentrationError, match="no stock defined"):
        plan_well_concentrations(
            "A01",
            WellVolumeInputs(200.0, 100.0, 10.0),
            stocks,
            {3: 1.0},
        )


def test_c_max_requires_positive_target():
    with pytest.raises(ConcentrationError):
        max_achievable_concentration(100.0, 10.0, 0.0)
