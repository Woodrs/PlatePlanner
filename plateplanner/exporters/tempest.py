"""Tempest CSV export.

Schema (one row per well × stock channel with volume > 0):

    plate_format,plate_id,stock_channel,well,volume_ul

- plate_format: 96 or 384
- plate_id: destination plate identifier
- stock_channel: integer 1–12
- well: A01-style well ID
- volume_ul: transfer volume in microliters
"""

from __future__ import annotations

import csv
import io
from typing import List, Union

from plateplanner.models import TempestPlan


TEMPTEST_COLUMNS = [
    "plate_format",
    "plate_id",
    "stock_channel",
    "well",
    "volume_ul",
]


def export_tempest_csv(plan: TempestPlan) -> str:
    """Return Tempest transfer CSV as a string."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TEMPTEST_COLUMNS, lineterminator="\n")
    writer.writeheader()
    # Stable order: by stock channel, then well
    for channel in sorted(plan.stock_volumes.keys()):
        vols = sorted(plan.stock_volumes[channel], key=lambda wv: wv.well)
        for wv in vols:
            if wv.volume_ul <= 0:
                continue
            writer.writerow(
                {
                    "plate_format": plan.plate_format,
                    "plate_id": plan.plate_id,
                    "stock_channel": channel,
                    "well": wv.well,
                    "volume_ul": f"{wv.volume_ul:g}",
                }
            )
    return buf.getvalue()


def export_tempest_rows(plan: TempestPlan) -> List[dict]:
    """Return list of row dicts (useful for UI preview / tests)."""
    text = export_tempest_csv(plan)
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)
