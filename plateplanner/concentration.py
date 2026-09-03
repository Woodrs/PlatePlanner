"""Tempest concentration → volume planning.

Concentrations are defined with respect to the **final target well volume**
(after base media, Tempest reagent dispenses, normalizing diluent, and later
inoculation). This matches the common lab convention that reported assay
concentrations refer to the finished well.

Formulas
--------
Free / residual dispense volume (available for Tempest reagents + diluent)::

    V_free = V_target - V_base_media - V_inoculation

Reagent volume for a requested target concentration (dilution equation)::

    V_reagent = C_target * V_target / C_stock

(capped so that the sum of reagent volumes across stocks sharing a well
does not exceed V_free).

Max achievable concentration if the entire free volume is one stock::

    C_max = C_stock * V_free / V_target

Volume normalizing (pad to identical final volume)::

    V_normalize = V_free - sum(V_reagent_i)

``V_normalize`` is exported as an additional Tempest channel (configurable;
default channel 12, label \"base media\" / diluent). After Tempest runs and
inoculation is added later, every well reaches ``V_target``.

Volume identity check per well::

    V_base + sum(V_reagent) + V_normalize + V_inoc = V_target
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from plateplanner.models import TempestPlan, WellVolume
from plateplanner.plates import normalize_well_id, well_in_plate


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ConcentrationError(ValueError):
    """Invalid concentration / volume planning input or constraint violation."""


class ConcentrationNotImplementedError(NotImplementedError):
    """Deprecated alias kept for older call sites; concentration mode is implemented."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def free_dispense_volume(
    target_volume_ul: float,
    base_media_volume_ul: float,
    inoculation_volume_ul: float,
) -> float:
    """Return V_free = V_target - V_base - V_inoc (may be negative — validate separately)."""
    return float(target_volume_ul) - float(base_media_volume_ul) - float(inoculation_volume_ul)


def max_achievable_concentration(
    stock_concentration: float,
    free_volume_ul: float,
    target_volume_ul: float,
) -> float:
    """C_max = C_stock * V_free / V_target (concentration w.r.t. final volume)."""
    if target_volume_ul <= 0:
        raise ConcentrationError("target_volume_ul must be > 0 to compute C_max")
    if stock_concentration < 0:
        raise ConcentrationError("stock_concentration must be >= 0")
    if free_volume_ul < 0:
        raise ConcentrationError("free_volume_ul must be >= 0 to compute C_max")
    return float(stock_concentration) * float(free_volume_ul) / float(target_volume_ul)


def reagent_volume_ul(
    target_concentration: float,
    stock_concentration: float,
    target_volume_ul: float,
) -> float:
    """V_reagent = C_target * V_target / C_stock (final-volume basis).

    Returns 0.0 when target_concentration is 0. Raises if stock is 0 and
    target > 0 (impossible).
    """
    if target_concentration < 0:
        raise ConcentrationError("target_concentration must be >= 0")
    if stock_concentration < 0:
        raise ConcentrationError("stock_concentration must be >= 0")
    if target_volume_ul <= 0:
        raise ConcentrationError("target_volume_ul must be > 0")
    if target_concentration == 0:
        return 0.0
    if stock_concentration == 0:
        raise ConcentrationError(
            "Cannot achieve non-zero target concentration from zero stock concentration"
        )
    return float(target_concentration) * float(target_volume_ul) / float(stock_concentration)


def validate_non_negative_volumes(
    *,
    target_volume_ul: float,
    base_media_volume_ul: float,
    inoculation_volume_ul: float,
) -> None:
    if target_volume_ul < 0:
        raise ConcentrationError("target_volume_ul must be >= 0")
    if base_media_volume_ul < 0:
        raise ConcentrationError("base_media_volume_ul must be >= 0")
    if inoculation_volume_ul < 0:
        raise ConcentrationError("inoculation_volume_ul must be >= 0")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WellVolumeInputs:
    """Per-well (or plate-default) volume budget for Tempest concentration mode."""

    target_volume_ul: float
    base_media_volume_ul: float = 0.0
    inoculation_volume_ul: float = 0.0

    def free_volume_ul(self) -> float:
        return free_dispense_volume(
            self.target_volume_ul,
            self.base_media_volume_ul,
            self.inoculation_volume_ul,
        )


@dataclass(frozen=True)
class StockDefinition:
    """One Tempest stock / channel with known stock concentration."""

    channel: int
    stock_concentration: float
    name: str = ""
    units: str = ""  # informational only (e.g. "uM", "mg/mL")

    def __post_init__(self) -> None:
        if not (1 <= self.channel <= 12):
            raise ConcentrationError(
                f"Tempest stock channel must be 1–12, got {self.channel}"
            )
        if self.stock_concentration < 0:
            raise ConcentrationError("stock_concentration must be >= 0")


@dataclass
class WellConcentrationResult:
    """Planned volumes and concentrations for a single well."""

    well: str
    target_volume_ul: float
    base_media_volume_ul: float
    inoculation_volume_ul: float
    free_volume_ul: float
    # channel -> planned reagent volume
    reagent_volumes_ul: Dict[int, float] = field(default_factory=dict)
    # channel -> requested target concentration (final-volume basis)
    target_concentrations: Dict[int, float] = field(default_factory=dict)
    # channel -> C_max for this well's free volume
    max_concentrations: Dict[int, float] = field(default_factory=dict)
    normalize_volume_ul: float = 0.0
    normalize_channel: Optional[int] = None

    @property
    def total_reagent_ul(self) -> float:
        return sum(self.reagent_volumes_ul.values())

    @property
    def total_tempest_ul(self) -> float:
        """Reagents + normalize (what Tempest dispenses into the well)."""
        return self.total_reagent_ul + self.normalize_volume_ul


@dataclass
class ConcentrationPlanResult:
    """Full plate concentration plan convertible to a TempestPlan."""

    plate_format: str
    plate_id: str
    wells: Dict[str, WellConcentrationResult]
    stocks: List[StockDefinition]
    normalize_channel: int
    normalize_label: str = "base media"

    def to_tempest_plan(self, *, include_normalize: bool = True) -> TempestPlan:
        """Build a TempestPlan from planned reagent (+ optional normalize) volumes."""
        plan = TempestPlan(plate_format=self.plate_format, plate_id=self.plate_id)
        # Collect per-channel well volumes
        by_channel: Dict[int, Dict[str, float]] = {}
        for well, wr in self.wells.items():
            for ch, vol in wr.reagent_volumes_ul.items():
                if vol > 0:
                    by_channel.setdefault(ch, {})[well] = vol
            if include_normalize and wr.normalize_volume_ul > 0:
                ch = wr.normalize_channel or self.normalize_channel
                by_channel.setdefault(ch, {})[well] = (
                    by_channel.get(ch, {}).get(well, 0.0) + wr.normalize_volume_ul
                )
        for ch, well_vols in by_channel.items():
            plan.assign_stock(ch, well_vols)
        return plan


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def _resolve_well_inputs(
    well: str,
    defaults: WellVolumeInputs,
    overrides: Optional[Mapping[str, WellVolumeInputs]],
) -> WellVolumeInputs:
    if not overrides:
        return defaults
    key = normalize_well_id(well)
    if key in overrides:
        return overrides[key]
    # also allow un-normalized keys
    for k, v in overrides.items():
        if normalize_well_id(k) == key:
            return v
    return defaults


def plan_well_concentrations(
    well: str,
    volumes: WellVolumeInputs,
    stocks: Sequence[StockDefinition],
    target_concentrations: Mapping[int, float],
    *,
    normalize_channel: int = 12,
    cap_to_free_volume: bool = False,
    round_digits: int = 6,
) -> WellConcentrationResult:
    """Plan reagent + normalize volumes for one well.

    Parameters
    ----------
    cap_to_free_volume:
        If True, scale down reagent volumes proportionally when their sum
        exceeds V_free (instead of raising). Default False → raise
        ConcentrationError on over-subscription or C_target > C_max.
    """
    well = normalize_well_id(well)
    validate_non_negative_volumes(
        target_volume_ul=volumes.target_volume_ul,
        base_media_volume_ul=volumes.base_media_volume_ul,
        inoculation_volume_ul=volumes.inoculation_volume_ul,
    )
    v_free = volumes.free_volume_ul()
    if v_free < 0:
        raise ConcentrationError(
            f"Well {well}: free volume is negative "
            f"({v_free:g} µL = {volumes.target_volume_ul:g} − "
            f"{volumes.base_media_volume_ul:g} − {volumes.inoculation_volume_ul:g})"
        )

    stock_by_ch = {s.channel: s for s in stocks}
    if len(stock_by_ch) != len(stocks):
        raise ConcentrationError("Duplicate stock channel in stocks list")

    if not (1 <= normalize_channel <= 12):
        raise ConcentrationError(
            f"normalize_channel must be 1–12, got {normalize_channel}"
        )

    # C_max per stock for this well
    c_max: Dict[int, float] = {}
    for s in stocks:
        c_max[s.channel] = max_achievable_concentration(
            s.stock_concentration, v_free, volumes.target_volume_ul
        )

    reagent_vols: Dict[int, float] = {}
    targets: Dict[int, float] = {}

    for ch, c_target in target_concentrations.items():
        if ch not in stock_by_ch:
            raise ConcentrationError(
                f"Well {well}: target concentration for channel {ch} "
                f"but no stock defined for that channel"
            )
        if c_target < 0:
            raise ConcentrationError(
                f"Well {well}: target concentration for channel {ch} must be >= 0"
            )
        targets[ch] = float(c_target)
        stock = stock_by_ch[ch]
        if c_target > c_max[ch] + 1e-12 and not cap_to_free_volume:
            raise ConcentrationError(
                f"Well {well}: requested C={c_target:g} on channel {ch} exceeds "
                f"C_max={c_max[ch]:g} (stock={stock.stock_concentration:g}, "
                f"V_free={v_free:g}, V_target={volumes.target_volume_ul:g})"
            )
        v = reagent_volume_ul(
            c_target, stock.stock_concentration, volumes.target_volume_ul
        )
        # If capping and over C_max, clamp to free volume for this single reagent
        # (multi-reagent over-sum handled below).
        if cap_to_free_volume and v > v_free:
            v = v_free
        reagent_vols[ch] = round(v, round_digits)

    total_reagent = sum(reagent_vols.values())
    if total_reagent > v_free + 1e-9:
        if not cap_to_free_volume:
            raise ConcentrationError(
                f"Well {well}: sum of reagent volumes ({total_reagent:g} µL) "
                f"exceeds free volume ({v_free:g} µL)"
            )
        # Scale proportionally to fit V_free
        if total_reagent > 0:
            scale = v_free / total_reagent
            reagent_vols = {
                ch: round(vol * scale, round_digits) for ch, vol in reagent_vols.items()
            }
            total_reagent = sum(reagent_vols.values())

    # Normalize: pad remaining free volume with diluent channel
    # Avoid using normalize_channel if it already has a reagent assignment —
    # still allowed (same channel can carry diluent pad) but volumes merge later.
    v_norm = round(max(0.0, v_free - total_reagent), round_digits)

    # Drop zero reagent entries for cleanliness
    reagent_vols = {ch: v for ch, v in reagent_vols.items() if v > 0}

    return WellConcentrationResult(
        well=well,
        target_volume_ul=volumes.target_volume_ul,
        base_media_volume_ul=volumes.base_media_volume_ul,
        inoculation_volume_ul=volumes.inoculation_volume_ul,
        free_volume_ul=v_free,
        reagent_volumes_ul=reagent_vols,
        target_concentrations=targets,
        max_concentrations=c_max,
        normalize_volume_ul=v_norm,
        normalize_channel=normalize_channel,
    )


def plan_plate_concentrations(
    *,
    plate_format: str,
    plate_id: str = "DEST",
    wells: Sequence[str],
    defaults: WellVolumeInputs,
    stocks: Sequence[StockDefinition],
    # well -> channel -> C_target  OR  use plate_targets for all wells
    well_targets: Optional[Mapping[str, Mapping[int, float]]] = None,
    plate_targets: Optional[Mapping[int, float]] = None,
    well_volume_overrides: Optional[Mapping[str, WellVolumeInputs]] = None,
    normalize_channel: int = 12,
    normalize_label: str = "base media",
    cap_to_free_volume: bool = False,
    round_digits: int = 6,
) -> ConcentrationPlanResult:
    """Plan concentrations for many wells; returns ConcentrationPlanResult.

    Prefer ``plate_targets`` (same C_target per channel for every well) and/or
    ``well_targets`` (per-well overrides; well-specific dict replaces plate
    targets for that well entirely when both are provided for a well).
    """
    if not wells:
        raise ConcentrationError("wells list must not be empty")
    if plate_targets is None and well_targets is None:
        raise ConcentrationError("Provide plate_targets and/or well_targets")

    # Validate stocks unique channels
    seen = set()
    for s in stocks:
        if s.channel in seen:
            raise ConcentrationError(f"Duplicate stock channel {s.channel}")
        seen.add(s.channel)

    # Normalize channel must not collide with a reagent stock that has targets,
    # unless user deliberately reuses it for diluent-only — we allow it but warn
    # via docs; validation only ensures 1–12.
    if not (1 <= normalize_channel <= 12):
        raise ConcentrationError(
            f"normalize_channel must be 1–12, got {normalize_channel}"
        )

    results: Dict[str, WellConcentrationResult] = {}
    for w in wells:
        nw = normalize_well_id(w)
        if not well_in_plate(nw, plate_format):
            raise ConcentrationError(
                f"Well {nw} outside {plate_format}-well plate"
            )
        vols = _resolve_well_inputs(nw, defaults, well_volume_overrides)

        if well_targets and (
            nw in well_targets
            or any(normalize_well_id(k) == nw for k in well_targets)
        ):
            raw = well_targets.get(nw)
            if raw is None:
                for k, v in well_targets.items():
                    if normalize_well_id(k) == nw:
                        raw = v
                        break
            targets = dict(raw or {})
        else:
            targets = dict(plate_targets or {})

        results[nw] = plan_well_concentrations(
            nw,
            vols,
            stocks,
            targets,
            normalize_channel=normalize_channel,
            cap_to_free_volume=cap_to_free_volume,
            round_digits=round_digits,
        )

    return ConcentrationPlanResult(
        plate_format=str(plate_format),
        plate_id=plate_id,
        wells=results,
        stocks=list(stocks),
        normalize_channel=normalize_channel,
        normalize_label=normalize_label,
    )


# ---------------------------------------------------------------------------
# Convenience / status API (replaces MVP stub)
# ---------------------------------------------------------------------------


def volume_from_concentration(
    stock_concentration: float,
    target_concentration: float,
    destination_final_volume_ul: float,
    *,
    units: str = "uM",
) -> float:
    """Return transfer volume (µL) for C_target w.r.t. final well volume.

    Uses ``V = C_target * V_final / C_stock``. ``units`` is informational.
    """
    _ = units
    return reagent_volume_ul(
        target_concentration, stock_concentration, destination_final_volume_ul
    )


def is_concentration_mode_available() -> bool:
    """Return True — Tempest concentration planning is implemented."""
    return True


def concentration_status_message() -> Optional[str]:
    return (
        "Concentration mode is available for Tempest. "
        "Concentrations are defined w.r.t. the final target well volume. "
        "V_reagent = C_target × V_target / C_stock; "
        "V_free = V_target − V_base − V_inoc; "
        "C_max = C_stock × V_free / V_target. "
        "Remaining free volume is filled via a normalizing diluent channel."
    )
