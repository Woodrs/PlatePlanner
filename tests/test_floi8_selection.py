"""Tests for Floi8 selection, volume, and channel helpers."""

import pytest

from plateplanner.models import (
    Floi8SourceFeature,
    Floi8Transfer,
    apply_linear_gradient,
    apply_uniform_volume,
    assign_floi8_channels,
    select_features_by_contents,
    select_features_by_strain_barcodes,
    unique_strain_barcodes,
)
from plateplanner.ui.demo_data import demo_floi8_source_features


@pytest.fixture
def features():
    return demo_floi8_source_features()


def test_select_by_contents(features):
    lb = select_features_by_contents(features, "LB Media")
    assert len(lb) == 4
    assert all(f.contents == "LB Media" for f in lb)
    # case insensitive
    assert len(select_features_by_contents(features, "lb media")) == 4


def test_unique_strain_barcodes(features):
    uniques = unique_strain_barcodes(features)
    assert "STR003" not in uniques  # appears twice (A03, A04)
    assert "STR001" in uniques
    assert "STR008" in uniques


def test_select_by_unique_barcodes(features):
    # Request STR003 which is NOT unique — should be excluded
    selected = select_features_by_strain_barcodes(
        features, ["STR001", "STR003"], unique_only=True
    )
    barcodes = {f.strain_barcode for f in selected}
    assert barcodes == {"STR001"}

    # unique_only=False includes duplicates
    selected_all = select_features_by_strain_barcodes(
        features, ["STR003"], unique_only=False
    )
    assert len(selected_all) == 2


def test_apply_uniform_volume():
    transfers = [
        Floi8Transfer("A01", "B01", 0.0),
        Floi8Transfer("A02", "B02", 0.0),
    ]
    out = apply_uniform_volume(transfers, 15.0)
    assert all(t.volume_ul == 15.0 for t in out)


def test_apply_linear_gradient():
    transfers = [
        Floi8Transfer("A01", "B01", 0.0),
        Floi8Transfer("A02", "B02", 0.0),
        Floi8Transfer("A03", "B03", 0.0),
    ]
    out = apply_linear_gradient(transfers, 0.0, 10.0)
    assert out[0].volume_ul == 0.0
    assert out[-1].volume_ul == 10.0
    assert out[1].volume_ul == 5.0


def test_assign_floi8_channels_cycles_1_to_8():
    transfers = [
        Floi8Transfer("A01", well_dest, 1.0)
        for well_dest in [f"A{i:02d}" for i in range(1, 11)]
    ]
    out = assign_floi8_channels(transfers)
    channels = [t.channel for t in out]
    assert channels == [1, 2, 3, 4, 5, 6, 7, 8, 1, 2]


def test_empty_gradient():
    assert apply_linear_gradient([], 1.0, 2.0) == []
