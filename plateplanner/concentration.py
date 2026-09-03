"""Concentration-based volume calculation — STUB / TODO.

Volume transfers only are supported in the MVP. This module is a placeholder
for future concentration → volume conversion (e.g. C1V1 = C2V2, stock molarity
to target concentration in destination wells).
"""

from __future__ import annotations

from typing import Optional


# TODO(concentration): Implement concentration-based volume calculation.
# Planned API sketch (not implemented):
#
#   def volume_from_concentration(
#       stock_concentration: float,
#       target_concentration: float,
#       destination_final_volume_ul: float,
#       *,
#       units: str = "uM",
#   ) -> float:
#       """Return transfer volume (uL) to achieve target concentration.
#
#       Uses V_stock = C_target * V_final / C_stock (dilution equation).
#       """
#       raise NotImplementedError
#
# Integration points:
# - TempestPlan / Floi8Transfer: optional concentration fields
# - UI: toggle "volume mode" vs "concentration mode"
# - Exporters: still emit volume_ul after conversion


class ConcentrationNotImplementedError(NotImplementedError):
    """Raised when concentration-based planning is requested before implementation."""


def volume_from_concentration(
    stock_concentration: float,
    target_concentration: float,
    destination_final_volume_ul: float,
    *,
    units: str = "uM",
) -> float:
    """TODO: Convert concentrations to transfer volume (uL).

    Currently raises ConcentrationNotImplementedError. MVP supports volume
    transfers only.
    """
    _ = (stock_concentration, target_concentration, destination_final_volume_ul, units)
    raise ConcentrationNotImplementedError(
        "Concentration-based volume calculation is not implemented yet. "
        "Use explicit volume_ul transfers. See plateplanner/concentration.py."
    )


def is_concentration_mode_available() -> bool:
    """Return False until concentration support ships."""
    return False


def concentration_status_message() -> Optional[str]:
    return (
        "Concentration mode is planned but not available in this MVP. "
        "Plan transfers using volumes (µL) only."
    )
