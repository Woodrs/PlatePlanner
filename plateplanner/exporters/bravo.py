"""Bravo CSV export.

Uniform stamp schema (one summary row plus optional per-well expansion):

Summary mode (default) — one row describing the stamp:

    source_plate_format,destination_plate_format,source_plate_id,destination_plate_id,volume_ul,transfer_type

Per-well mode — one row per well (source well stamped to same-ID destination well):

    source_plate_format,destination_plate_format,source_plate_id,destination_plate_id,source_well,destination_well,volume_ul,transfer_type
"""

from __future__ import annotations

import csv
import io
from typing import List

from plateplanner.models import BravoPlan
from plateplanner.plates import all_wells, get_plate_format


BRAVO_SUMMARY_COLUMNS = [
    "source_plate_format",
    "destination_plate_format",
    "source_plate_id",
    "destination_plate_id",
    "volume_ul",
    "transfer_type",
]

BRAVO_WELL_COLUMNS = [
    "source_plate_format",
    "destination_plate_format",
    "source_plate_id",
    "destination_plate_id",
    "source_well",
    "destination_well",
    "volume_ul",
    "transfer_type",
]


def export_bravo_csv(plan: BravoPlan, *, expand_wells: bool = False) -> str:
    """Return Bravo stamp CSV as a string."""
    buf = io.StringIO()
    if not expand_wells:
        writer = csv.DictWriter(
            buf, fieldnames=BRAVO_SUMMARY_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_plate_format": plan.source_plate_format,
                "destination_plate_format": plan.destination_plate_format,
                "source_plate_id": plan.source_plate_id,
                "destination_plate_id": plan.destination_plate_id,
                "volume_ul": f"{plan.volume_ul:g}",
                "transfer_type": "uniform_stamp",
            }
        )
        return buf.getvalue()

    src_fmt = get_plate_format(plan.source_plate_format)
    dst_fmt = get_plate_format(plan.destination_plate_format)
    # Stamp wells that exist on both plates (same well ID)
    src_wells = set(all_wells(src_fmt))
    dst_wells = set(all_wells(dst_fmt))
    shared = sorted(src_wells & dst_wells)

    writer = csv.DictWriter(buf, fieldnames=BRAVO_WELL_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for well in shared:
        writer.writerow(
            {
                "source_plate_format": plan.source_plate_format,
                "destination_plate_format": plan.destination_plate_format,
                "source_plate_id": plan.source_plate_id,
                "destination_plate_id": plan.destination_plate_id,
                "source_well": well,
                "destination_well": well,
                "volume_ul": f"{plan.volume_ul:g}",
                "transfer_type": "uniform_stamp",
            }
        )
    return buf.getvalue()


def export_bravo_rows(plan: BravoPlan, *, expand_wells: bool = False) -> List[dict]:
    text = export_bravo_csv(plan, expand_wells=expand_wells)
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)
