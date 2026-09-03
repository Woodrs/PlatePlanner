"""Plate geometry and shared well identifiers (A01-style)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple


ROW_LETTERS_96 = "ABCDEFGH"
ROW_LETTERS_384 = "ABCDEFGHIJKLMNOP"


@dataclass(frozen=True)
class PlateFormat:
    """Well-plate layout definition."""

    name: str
    rows: int
    cols: int

    @property
    def well_count(self) -> int:
        return self.rows * self.cols

    @property
    def row_letters(self) -> str:
        if self.rows == 8:
            return ROW_LETTERS_96
        if self.rows == 16:
            return ROW_LETTERS_384
        return "".join(chr(ord("A") + i) for i in range(self.rows))


PLATE_96 = PlateFormat(name="96", rows=8, cols=12)
PLATE_384 = PlateFormat(name="384", rows=16, cols=24)

PLATE_FORMATS = {
    "96": PLATE_96,
    "384": PLATE_384,
}


def get_plate_format(name: str) -> PlateFormat:
    key = str(name).strip()
    if key not in PLATE_FORMATS:
        raise ValueError(f"Unsupported plate format: {name!r}. Use 96 or 384.")
    return PLATE_FORMATS[key]


def well_id(row_index: int, col_index: int) -> str:
    """Return A01-style well ID from 0-based row/col indices."""
    if row_index < 0 or col_index < 0:
        raise ValueError("row_index and col_index must be >= 0")
    letter = chr(ord("A") + row_index)
    return f"{letter}{col_index + 1:02d}"


def parse_well_id(well: str) -> Tuple[int, int]:
    """Parse A01-style well ID into 0-based (row, col)."""
    well = well.strip().upper()
    if len(well) < 2:
        raise ValueError(f"Invalid well ID: {well!r}")
    row_letter = well[0]
    if not row_letter.isalpha():
        raise ValueError(f"Invalid well ID: {well!r}")
    try:
        col = int(well[1:])
    except ValueError as exc:
        raise ValueError(f"Invalid well ID: {well!r}") from exc
    if col < 1:
        raise ValueError(f"Invalid well column in {well!r}")
    row_index = ord(row_letter) - ord("A")
    return row_index, col - 1


def normalize_well_id(well: str) -> str:
    """Normalize well strings like 'a1' or 'A1' to 'A01'."""
    row, col = parse_well_id(well)
    return well_id(row, col)


def all_wells(plate: PlateFormat | str) -> List[str]:
    """Return all well IDs for a plate format in row-major order."""
    fmt = plate if isinstance(plate, PlateFormat) else get_plate_format(plate)
    return [
        well_id(r, c)
        for r in range(fmt.rows)
        for c in range(fmt.cols)
    ]


def well_in_plate(well: str, plate: PlateFormat | str) -> bool:
    fmt = plate if isinstance(plate, PlateFormat) else get_plate_format(plate)
    try:
        row, col = parse_well_id(well)
    except ValueError:
        return False
    return 0 <= row < fmt.rows and 0 <= col < fmt.cols


def validate_wells(wells: Iterable[str], plate: PlateFormat | str) -> List[str]:
    fmt = plate if isinstance(plate, PlateFormat) else get_plate_format(plate)
    normalized: List[str] = []
    for w in wells:
        nw = normalize_well_id(w)
        if not well_in_plate(nw, fmt):
            raise ValueError(f"Well {w!r} is outside {fmt.name}-well plate")
        normalized.append(nw)
    return normalized


def wells_to_indices(wells: Sequence[str]) -> List[Tuple[int, int]]:
    return [parse_well_id(w) for w in wells]
