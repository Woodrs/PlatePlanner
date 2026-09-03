"""Floi8 CSV import/export.

Source features import schema (flexible headers):

    well,contents,strain_barcode,volume_ul

Transfer export schema:

    channel,source_well,destination_well,volume_ul,contents,strain_barcode
"""

from __future__ import annotations

import csv
import io
from typing import Iterable, List, Optional, Union

from plateplanner.models import Floi8SourceFeature, Floi8Transfer
from plateplanner.plates import normalize_well_id


FLOI8_SOURCE_COLUMNS = ["well", "contents", "strain_barcode", "volume_ul"]
FLOI8_TRANSFER_COLUMNS = [
    "channel",
    "source_well",
    "destination_well",
    "volume_ul",
    "contents",
    "strain_barcode",
]

# Accept common aliases when importing
_HEADER_ALIASES = {
    "well": "well",
    "well_id": "well",
    "source_well": "well",
    "contents": "contents",
    "content": "contents",
    "reagent": "contents",
    "strain_barcode": "strain_barcode",
    "barcode": "strain_barcode",
    "strain": "strain_barcode",
    "volume_ul": "volume_ul",
    "volume": "volume_ul",
    "vol_ul": "volume_ul",
}


def _normalize_header(name: str) -> Optional[str]:
    key = name.strip().lower().replace(" ", "_")
    return _HEADER_ALIASES.get(key)


def parse_floi8_source_csv(text: Union[str, Iterable[str]]) -> List[Floi8SourceFeature]:
    """Parse Floi8 source-feature CSV into feature objects."""
    if not isinstance(text, str):
        text = "".join(text)
    # Strip BOM if present
    if text.startswith("\ufeff"):
        text = text[1:]
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []

    colmap = {}
    for raw in reader.fieldnames:
        canon = _normalize_header(raw)
        if canon:
            colmap[canon] = raw

    if "well" not in colmap:
        raise ValueError(
            "Floi8 source CSV must include a 'well' column "
            f"(got columns: {list(reader.fieldnames)})"
        )

    features: List[Floi8SourceFeature] = []
    for row in reader:
        well_raw = (row.get(colmap["well"]) or "").strip()
        if not well_raw:
            continue
        contents = ""
        if "contents" in colmap:
            contents = (row.get(colmap["contents"]) or "").strip()
        barcode = ""
        if "strain_barcode" in colmap:
            barcode = (row.get(colmap["strain_barcode"]) or "").strip()
        vol: Optional[float] = None
        if "volume_ul" in colmap:
            raw_vol = (row.get(colmap["volume_ul"]) or "").strip()
            if raw_vol:
                vol = float(raw_vol)
        features.append(
            Floi8SourceFeature(
                well=normalize_well_id(well_raw),
                contents=contents,
                strain_barcode=barcode,
                volume_ul=vol,
            )
        )
    return features


def export_floi8_transfer_csv(transfers: List[Floi8Transfer]) -> str:
    """Return Floi8 transfer CSV as a string."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=FLOI8_TRANSFER_COLUMNS, lineterminator="\n"
    )
    writer.writeheader()
    for t in transfers:
        writer.writerow(
            {
                "channel": t.channel if t.channel is not None else "",
                "source_well": t.source_well,
                "destination_well": t.destination_well,
                "volume_ul": f"{t.volume_ul:g}",
                "contents": t.contents,
                "strain_barcode": t.strain_barcode,
            }
        )
    return buf.getvalue()


def export_floi8_rows(transfers: List[Floi8Transfer]) -> List[dict]:
    text = export_floi8_transfer_csv(transfers)
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)
