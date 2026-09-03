"""Transfer planning data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from plateplanner.plates import PlateFormat, get_plate_format, normalize_well_id, well_in_plate


@dataclass
class WellVolume:
    """Volume dispensed into a single well from one stock/channel."""

    well: str
    volume_ul: float

    def __post_init__(self) -> None:
        self.well = normalize_well_id(self.well)
        if self.volume_ul < 0:
            raise ValueError("volume_ul must be >= 0")


@dataclass
class TempestPlan:
    """Tempest variable-volume multi-stock transfer plan."""

    plate_format: str
    # stock_channel (1-12) -> list of well volumes
    stock_volumes: Dict[int, List[WellVolume]] = field(default_factory=dict)
    plate_id: str = "DEST"

    def __post_init__(self) -> None:
        self.plate_format = str(self.plate_format)
        get_plate_format(self.plate_format)
        for channel, vols in self.stock_volumes.items():
            if channel < 1 or channel > 12:
                raise ValueError(f"Tempest stock channel must be 1–12, got {channel}")
            for wv in vols:
                if not well_in_plate(wv.well, self.plate_format):
                    raise ValueError(
                        f"Well {wv.well} outside {self.plate_format}-well plate"
                    )

    @property
    def format(self) -> PlateFormat:
        return get_plate_format(self.plate_format)

    def assign_stock(
        self, channel: int, well_volumes: Dict[str, float]
    ) -> None:
        if channel < 1 or channel > 12:
            raise ValueError(f"Tempest stock channel must be 1–12, got {channel}")
        self.stock_volumes[channel] = [
            WellVolume(well=w, volume_ul=v) for w, v in well_volumes.items() if v > 0
        ]


@dataclass
class BravoPlan:
    """Bravo uniform stamp: same volume from every source well to matching dest well."""

    source_plate_format: str
    destination_plate_format: str
    volume_ul: float
    source_plate_id: str = "SRC"
    destination_plate_id: str = "DST"

    def __post_init__(self) -> None:
        get_plate_format(self.source_plate_format)
        get_plate_format(self.destination_plate_format)
        if self.volume_ul < 0:
            raise ValueError("volume_ul must be >= 0")
        src = get_plate_format(self.source_plate_format)
        dst = get_plate_format(self.destination_plate_format)
        if src.well_count != dst.well_count and (
            src.rows > dst.rows or src.cols > dst.cols
        ):
            # Allow same geometry or source subset of dest; stamp typically same format
            pass


@dataclass
class Floi8SourceFeature:
    """Source well annotation for Floi8 (contents / strain barcode / volume)."""

    well: str
    contents: str = ""
    strain_barcode: str = ""
    volume_ul: Optional[float] = None

    def __post_init__(self) -> None:
        self.well = normalize_well_id(self.well)
        self.contents = (self.contents or "").strip()
        self.strain_barcode = (self.strain_barcode or "").strip()


@dataclass
class Floi8Transfer:
    """Single channel mapping: source well → destination well + volume."""

    source_well: str
    destination_well: str
    volume_ul: float
    contents: str = ""
    strain_barcode: str = ""
    channel: Optional[int] = None  # 1–8 when assigned

    def __post_init__(self) -> None:
        self.source_well = normalize_well_id(self.source_well)
        self.destination_well = normalize_well_id(self.destination_well)
        if self.volume_ul < 0:
            raise ValueError("volume_ul must be >= 0")
        if self.channel is not None and not (1 <= self.channel <= 8):
            raise ValueError("Floi8 channel must be 1–8")


@dataclass
class Floi8Plan:
    """Floi8 8-channel independent transfer plan."""

    source_plate_format: str = "96"
    destination_plate_format: str = "96"
    source_features: List[Floi8SourceFeature] = field(default_factory=list)
    transfers: List[Floi8Transfer] = field(default_factory=list)

    def __post_init__(self) -> None:
        get_plate_format(self.source_plate_format)
        get_plate_format(self.destination_plate_format)


# ---------------------------------------------------------------------------
# Floi8 selection helpers (unit-tested)
# ---------------------------------------------------------------------------


def select_features_by_contents(
    features: List[Floi8SourceFeature], contents: str, *, case_insensitive: bool = True
) -> List[Floi8SourceFeature]:
    """Filter source features whose contents match (exact, optionally case-insensitive)."""
    target = contents.strip()
    if case_insensitive:
        target = target.lower()
    out: List[Floi8SourceFeature] = []
    for f in features:
        val = f.contents.lower() if case_insensitive else f.contents
        if val == target:
            out.append(f)
    return out


def select_features_by_strain_barcodes(
    features: List[Floi8SourceFeature],
    barcodes: List[str],
    *,
    unique_only: bool = True,
) -> List[Floi8SourceFeature]:
    """
    Filter source features by strain barcode.

    If unique_only is True (default), only barcodes that appear exactly once
    in the feature list are eligible — matching the Floi8 "unique strain" filter.
    """
    wanted = {b.strip() for b in barcodes if b and b.strip()}
    if not wanted:
        return []

    if unique_only:
        counts: Dict[str, int] = {}
        for f in features:
            if f.strain_barcode:
                counts[f.strain_barcode] = counts.get(f.strain_barcode, 0) + 1
        wanted = {b for b in wanted if counts.get(b, 0) == 1}

    return [f for f in features if f.strain_barcode in wanted]


def unique_strain_barcodes(features: List[Floi8SourceFeature]) -> List[str]:
    """Return barcodes that appear exactly once, sorted."""
    counts: Dict[str, int] = {}
    for f in features:
        if f.strain_barcode:
            counts[f.strain_barcode] = counts.get(f.strain_barcode, 0) + 1
    return sorted(b for b, n in counts.items() if n == 1)


def apply_uniform_volume(
    transfers: List[Floi8Transfer], volume_ul: float
) -> List[Floi8Transfer]:
    if volume_ul < 0:
        raise ValueError("volume_ul must be >= 0")
    return [
        Floi8Transfer(
            source_well=t.source_well,
            destination_well=t.destination_well,
            volume_ul=volume_ul,
            contents=t.contents,
            strain_barcode=t.strain_barcode,
            channel=t.channel,
        )
        for t in transfers
    ]


def apply_linear_gradient(
    transfers: List[Floi8Transfer],
    start_ul: float,
    end_ul: float,
) -> List[Floi8Transfer]:
    """Assign a linear volume gradient across transfers in list order."""
    if start_ul < 0 or end_ul < 0:
        raise ValueError("volumes must be >= 0")
    n = len(transfers)
    if n == 0:
        return []
    if n == 1:
        return apply_uniform_volume(transfers, start_ul)
    out: List[Floi8Transfer] = []
    for i, t in enumerate(transfers):
        frac = i / (n - 1)
        vol = start_ul + frac * (end_ul - start_ul)
        out.append(
            Floi8Transfer(
                source_well=t.source_well,
                destination_well=t.destination_well,
                volume_ul=round(vol, 4),
                contents=t.contents,
                strain_barcode=t.strain_barcode,
                channel=t.channel,
            )
        )
    return out


def assign_floi8_channels(
    transfers: List[Floi8Transfer], max_channels: int = 8
) -> List[Floi8Transfer]:
    """Assign channels 1..max_channels cycling through transfers."""
    out: List[Floi8Transfer] = []
    for i, t in enumerate(transfers):
        ch = (i % max_channels) + 1
        out.append(
            Floi8Transfer(
                source_well=t.source_well,
                destination_well=t.destination_well,
                volume_ul=t.volume_ul,
                contents=t.contents,
                strain_barcode=t.strain_barcode,
                channel=ch,
            )
        )
    return out
