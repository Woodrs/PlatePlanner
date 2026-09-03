"""Tests for Tempest, Bravo, and Floi8 CSV exporters."""

import csv
import io

import pytest

from plateplanner.exporters.bravo import BRAVO_SUMMARY_COLUMNS, export_bravo_csv
from plateplanner.exporters.floi8 import (
    FLOI8_TRANSFER_COLUMNS,
    export_floi8_transfer_csv,
    parse_floi8_source_csv,
)
from plateplanner.exporters.tempest import TEMPTEST_COLUMNS, export_tempest_csv
from plateplanner.models import (
    BravoPlan,
    Floi8Transfer,
    TempestPlan,
    WellVolume,
)
from plateplanner.ui.demo_data import (
    demo_bravo_plan,
    demo_floi8_transfers,
    demo_tempest_plan,
    floi8_source_csv_text,
)


def _read(csv_text: str):
    return list(csv.DictReader(io.StringIO(csv_text)))


def test_tempest_export_schema_and_demo():
    plan = demo_tempest_plan()
    text = export_tempest_csv(plan)
    rows = _read(text)
    assert list(rows[0].keys()) == TEMPTEST_COLUMNS
    assert all(r["plate_format"] == "96" for r in rows)
    assert all(1 <= int(r["stock_channel"]) <= 12 for r in rows)
    assert any(r["well"] == "A01" for r in rows)
    # volumes positive
    assert all(float(r["volume_ul"]) > 0 for r in rows)


def test_tempest_export_empty_stocks():
    plan = TempestPlan(plate_format="96", stock_volumes={})
    text = export_tempest_csv(plan)
    rows = _read(text)
    assert rows == []
    assert "plate_format" in text.splitlines()[0]


def test_tempest_channel_bounds():
    with pytest.raises(ValueError):
        TempestPlan(
            plate_format="96",
            stock_volumes={13: [WellVolume("A01", 1.0)]},
        )


def test_bravo_summary_export():
    plan = demo_bravo_plan()
    text = export_bravo_csv(plan, expand_wells=False)
    rows = _read(text)
    assert list(rows[0].keys()) == BRAVO_SUMMARY_COLUMNS
    assert len(rows) == 1
    assert rows[0]["volume_ul"] == "25"
    assert rows[0]["transfer_type"] == "uniform_stamp"
    assert rows[0]["source_plate_id"] == "BRAVO_SRC"


def test_bravo_expanded_export_96():
    plan = BravoPlan(
        source_plate_format="96",
        destination_plate_format="96",
        volume_ul=10.0,
    )
    text = export_bravo_csv(plan, expand_wells=True)
    rows = _read(text)
    assert len(rows) == 96
    assert rows[0]["source_well"] == rows[0]["destination_well"]
    assert "source_well" in rows[0]


def test_floi8_transfer_export():
    transfers = demo_floi8_transfers()
    text = export_floi8_transfer_csv(transfers)
    rows = _read(text)
    assert list(rows[0].keys()) == FLOI8_TRANSFER_COLUMNS
    assert len(rows) == len(transfers)
    assert all(r["source_well"] and r["destination_well"] for r in rows)
    channels = {int(r["channel"]) for r in rows if r["channel"]}
    assert channels <= set(range(1, 9))


def test_floi8_parse_source_csv():
    features = parse_floi8_source_csv(floi8_source_csv_text())
    assert len(features) >= 8
    assert features[0].well == "A01"
    assert features[0].contents == "LB Media"
    assert features[0].strain_barcode == "STR001"


def test_floi8_parse_aliases():
    text = "well_id,content,barcode,vol_ul\na1,Media,BC1,50\n"
    features = parse_floi8_source_csv(text)
    assert len(features) == 1
    assert features[0].well == "A01"
    assert features[0].contents == "Media"
    assert features[0].strain_barcode == "BC1"
    assert features[0].volume_ul == 50.0


def test_floi8_parse_requires_well():
    with pytest.raises(ValueError):
        parse_floi8_source_csv("contents,strain_barcode\nLB,STR1\n")
