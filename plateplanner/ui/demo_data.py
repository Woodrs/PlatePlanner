"""Built-in demo / sample data for all three instruments."""

from __future__ import annotations

from typing import Dict, List

from plateplanner.models import (
    BravoPlan,
    Floi8SourceFeature,
    Floi8Transfer,
    TempestPlan,
    WellVolume,
    assign_floi8_channels,
)
from plateplanner.plates import all_wells, well_id


def demo_tempest_plan() -> TempestPlan:
    """96-well Tempest demo: stock 1 fills row A gradient; stock 2 fills column 1."""
    plan = TempestPlan(plate_format="96", plate_id="TEMPEST_DEMO")
    # Stock 1: row A, increasing volume across columns
    stock1 = {
        well_id(0, c): round(5.0 + c * 2.5, 2) for c in range(12)
    }
    # Stock 2: column 1 (wells A01–H01), fixed 10 µL except A01 already has stock1
    stock2 = {well_id(r, 0): 10.0 for r in range(8)}
    # Stock 3: block B02–D04 at 15 µL
    stock3: Dict[str, float] = {}
    for r in range(1, 4):
        for c in range(1, 4):
            stock3[well_id(r, c)] = 15.0
    plan.assign_stock(1, stock1)
    plan.assign_stock(2, stock2)
    plan.assign_stock(3, stock3)
    return plan


def demo_bravo_plan() -> BravoPlan:
    return BravoPlan(
        source_plate_format="96",
        destination_plate_format="96",
        volume_ul=25.0,
        source_plate_id="BRAVO_SRC",
        destination_plate_id="BRAVO_DST",
    )


def demo_floi8_source_features() -> List[Floi8SourceFeature]:
    """Sample source plate annotations for Floi8 filtering demos."""
    features = [
        Floi8SourceFeature(well="A01", contents="LB Media", strain_barcode="STR001", volume_ul=100),
        Floi8SourceFeature(well="A02", contents="LB Media", strain_barcode="STR002", volume_ul=100),
        Floi8SourceFeature(well="A03", contents="Minimal", strain_barcode="STR003", volume_ul=80),
        Floi8SourceFeature(well="A04", contents="Minimal", strain_barcode="STR003", volume_ul=80),  # duplicate barcode
        Floi8SourceFeature(well="B01", contents="LB Media", strain_barcode="STR004", volume_ul=100),
        Floi8SourceFeature(well="B02", contents="YPD", strain_barcode="STR005", volume_ul=120),
        Floi8SourceFeature(well="B03", contents="YPD", strain_barcode="STR006", volume_ul=120),
        Floi8SourceFeature(well="C01", contents="Water", strain_barcode="", volume_ul=200),
        Floi8SourceFeature(well="C02", contents="LB Media", strain_barcode="STR007", volume_ul=100),
        Floi8SourceFeature(well="D01", contents="Minimal", strain_barcode="STR008", volume_ul=90),
    ]
    return features


def demo_floi8_transfers() -> List[Floi8Transfer]:
    """Map first 8 unique-ish source wells onto destination row A."""
    features = demo_floi8_source_features()
    # Prefer unique barcodes + a couple content matches
    selected = [f for f in features if f.strain_barcode in {
        "STR001", "STR002", "STR004", "STR005", "STR006", "STR007", "STR008"
    }][:8]
    transfers = []
    for i, f in enumerate(selected):
        transfers.append(
            Floi8Transfer(
                source_well=f.well,
                destination_well=well_id(0, i),
                volume_ul=10.0 + i * 2.5,
                contents=f.contents,
                strain_barcode=f.strain_barcode,
            )
        )
    return assign_floi8_channels(transfers)


def floi8_source_csv_text() -> str:
    lines = ["well,contents,strain_barcode,volume_ul"]
    for f in demo_floi8_source_features():
        vol = "" if f.volume_ul is None else f"{f.volume_ul:g}"
        lines.append(f"{f.well},{f.contents},{f.strain_barcode},{vol}")
    return "\n".join(lines) + "\n"


def tempest_volume_map(plan: TempestPlan) -> Dict[str, float]:
    """Sum volumes per well across all stocks (for visualization)."""
    totals: Dict[str, float] = {}
    for vols in plan.stock_volumes.values():
        for wv in vols:
            totals[wv.well] = totals.get(wv.well, 0.0) + wv.volume_ul
    return totals
