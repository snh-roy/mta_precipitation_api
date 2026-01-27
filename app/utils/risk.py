from typing import Optional

from app.config import get_settings
from app.models import RiskLevel


def calculate_risk(
    structure: str,
    precip_rate_in_hr: float,
    accum_6hr_in: float,
    tide_level_ft: Optional[float] = None,
    is_coastal: bool = False,
) -> RiskLevel:
    """
    Calculate flood risk level for a station based on precipitation,
    structure type, and tide levels.

    Args:
        structure: Station structure type (Subway, Elevated, Open Cut, At-Grade)
        precip_rate_in_hr: Current precipitation rate in inches/hour
        accum_6hr_in: 6-hour accumulated precipitation in inches
        tide_level_ft: Current tide level in feet (MLLW datum)
        is_coastal: Whether station is in a coastal flood zone

    Returns:
        RiskLevel enum value (HIGH, AT RISK, or LOW)
    """
    settings = get_settings()
    structure_lower = structure.lower() if structure else ""

    # Handle missing values
    precip_rate = precip_rate_in_hr or 0.0
    accum_6hr = accum_6hr_in or 0.0

    # Underground stations (most vulnerable)
    if "subway" in structure_lower:
        if precip_rate > settings.subway_high_precip_rate or accum_6hr > settings.subway_high_accum_6hr:
            return RiskLevel.HIGH
        if precip_rate > settings.subway_atrisk_precip_rate or accum_6hr > settings.subway_atrisk_accum_6hr:
            return RiskLevel.AT_RISK

    # Open cut stations
    if "open cut" in structure_lower:
        if precip_rate > settings.opencut_high_precip_rate or accum_6hr > settings.opencut_high_accum_6hr:
            return RiskLevel.HIGH
        if precip_rate > settings.opencut_atrisk_precip_rate or accum_6hr > settings.opencut_atrisk_accum_6hr:
            return RiskLevel.AT_RISK

    # Coastal flooding factor
    if is_coastal and tide_level_ft is not None:
        if tide_level_ft > settings.tide_high_level:
            if precip_rate > settings.coastal_high_precip_rate:
                return RiskLevel.HIGH
            if precip_rate > settings.coastal_atrisk_precip_rate:
                return RiskLevel.AT_RISK

    # Elevated stations (safest from flooding)
    if "elevated" in structure_lower:
        if precip_rate > settings.elevated_atrisk_precip_rate:
            return RiskLevel.AT_RISK
        return RiskLevel.LOW

    # At-grade or other structures - use default thresholds
    if precip_rate > settings.default_high_precip_rate or accum_6hr > settings.default_high_accum_6hr:
        return RiskLevel.HIGH
    if precip_rate > settings.default_atrisk_precip_rate or accum_6hr > settings.default_atrisk_accum_6hr:
        return RiskLevel.AT_RISK

    return RiskLevel.LOW


def calculate_risk_with_reason(
    structure: str,
    precip_rate_in_hr: float,
    accum_6hr_in: float,
    tide_level_ft: Optional[float] = None,
    is_coastal: bool = False,
) -> tuple[RiskLevel, str]:
    """
    Calculate flood risk level and return a short reason string.
    """
    settings = get_settings()
    structure_lower = structure.lower() if structure else ""

    precip_rate = precip_rate_in_hr or 0.0
    accum_6hr = accum_6hr_in or 0.0

    if "subway" in structure_lower:
        if precip_rate > settings.subway_high_precip_rate:
            return (
                RiskLevel.HIGH,
                f"Subway: precip rate {precip_rate:.3f} > {settings.subway_high_precip_rate:.3f} in/hr",
            )
        if accum_6hr > settings.subway_high_accum_6hr:
            return (
                RiskLevel.HIGH,
                f"Subway: 6hr accumulation {accum_6hr:.3f} > {settings.subway_high_accum_6hr:.3f} in",
            )
        if precip_rate > settings.subway_atrisk_precip_rate:
            return (
                RiskLevel.AT_RISK,
                f"Subway: precip rate {precip_rate:.3f} > {settings.subway_atrisk_precip_rate:.3f} in/hr",
            )
        if accum_6hr > settings.subway_atrisk_accum_6hr:
            return (
                RiskLevel.AT_RISK,
                f"Subway: 6hr accumulation {accum_6hr:.3f} > {settings.subway_atrisk_accum_6hr:.3f} in",
            )

    if "open cut" in structure_lower:
        if precip_rate > settings.opencut_high_precip_rate:
            return (
                RiskLevel.HIGH,
                f"Open Cut: precip rate {precip_rate:.3f} > {settings.opencut_high_precip_rate:.3f} in/hr",
            )
        if accum_6hr > settings.opencut_high_accum_6hr:
            return (
                RiskLevel.HIGH,
                f"Open Cut: 6hr accumulation {accum_6hr:.3f} > {settings.opencut_high_accum_6hr:.3f} in",
            )
        if precip_rate > settings.opencut_atrisk_precip_rate:
            return (
                RiskLevel.AT_RISK,
                f"Open Cut: precip rate {precip_rate:.3f} > {settings.opencut_atrisk_precip_rate:.3f} in/hr",
            )
        if accum_6hr > settings.opencut_atrisk_accum_6hr:
            return (
                RiskLevel.AT_RISK,
                f"Open Cut: 6hr accumulation {accum_6hr:.3f} > {settings.opencut_atrisk_accum_6hr:.3f} in",
            )

    if is_coastal and tide_level_ft is not None and tide_level_ft > settings.tide_high_level:
        if precip_rate > settings.coastal_high_precip_rate:
            return (
                RiskLevel.HIGH,
                f"Coastal: tide {tide_level_ft:.2f}ft > {settings.tide_high_level:.2f}ft and precip rate {precip_rate:.3f} > {settings.coastal_high_precip_rate:.3f} in/hr",
            )
        if precip_rate > settings.coastal_atrisk_precip_rate:
            return (
                RiskLevel.AT_RISK,
                f"Coastal: tide {tide_level_ft:.2f}ft > {settings.tide_high_level:.2f}ft and precip rate {precip_rate:.3f} > {settings.coastal_atrisk_precip_rate:.3f} in/hr",
            )

    if "elevated" in structure_lower:
        if precip_rate > settings.elevated_atrisk_precip_rate:
            return (
                RiskLevel.AT_RISK,
                f"Elevated: precip rate {precip_rate:.3f} > {settings.elevated_atrisk_precip_rate:.3f} in/hr",
            )
        return RiskLevel.LOW, f"Elevated: precip rate {precip_rate:.3f} <= {settings.elevated_atrisk_precip_rate:.3f} in/hr"

    if precip_rate > settings.default_high_precip_rate:
        return (
            RiskLevel.HIGH,
            f"Default: precip rate {precip_rate:.3f} > {settings.default_high_precip_rate:.3f} in/hr",
        )
    if accum_6hr > settings.default_high_accum_6hr:
        return (
            RiskLevel.HIGH,
            f"Default: 6hr accumulation {accum_6hr:.3f} > {settings.default_high_accum_6hr:.3f} in",
        )
    if precip_rate > settings.default_atrisk_precip_rate:
        return (
            RiskLevel.AT_RISK,
            f"Default: precip rate {precip_rate:.3f} > {settings.default_atrisk_precip_rate:.3f} in/hr",
        )
    if accum_6hr > settings.default_atrisk_accum_6hr:
        return (
            RiskLevel.AT_RISK,
            f"Default: 6hr accumulation {accum_6hr:.3f} > {settings.default_atrisk_accum_6hr:.3f} in",
        )

    return (
        RiskLevel.LOW,
        f"Below thresholds: rate {precip_rate:.3f} in/hr, 6hr {accum_6hr:.3f} in",
    )


def get_risk_summary(risk_levels: list[RiskLevel]) -> dict:
    """Get summary counts of risk levels."""
    high_count = sum(1 for r in risk_levels if r == RiskLevel.HIGH)
    at_risk_count = sum(1 for r in risk_levels if r == RiskLevel.AT_RISK)
    low_count = sum(1 for r in risk_levels if r == RiskLevel.LOW)

    return {
        "high_risk_count": high_count,
        "at_risk_count": at_risk_count,
        "low_count": low_count,
        "total": len(risk_levels),
    }


def calculate_predicted_risk(
    structure: str,
    forecast_total_in: float,
    window_hours: int,
    tide_level_ft: Optional[float] = None,
    is_coastal: bool = False,
) -> RiskLevel:
    """
    Predict flood risk using forecast precipitation totals over a future window.

    Uses average rate (total/window_hours) and scales 6hr accumulation thresholds
    by the window length.
    """
    if window_hours <= 0:
        return RiskLevel.LOW

    settings = get_settings()
    structure_lower = structure.lower() if structure else ""
    avg_rate = forecast_total_in / float(window_hours)
    accum_factor = window_hours / 6.0

    subway_high_accum = settings.subway_high_accum_6hr * accum_factor
    subway_atrisk_accum = settings.subway_atrisk_accum_6hr * accum_factor
    opencut_high_accum = settings.opencut_high_accum_6hr * accum_factor
    opencut_atrisk_accum = settings.opencut_atrisk_accum_6hr * accum_factor
    default_high_accum = settings.default_high_accum_6hr * accum_factor
    default_atrisk_accum = settings.default_atrisk_accum_6hr * accum_factor

    # Underground stations
    if "subway" in structure_lower:
        if avg_rate > settings.subway_high_precip_rate or forecast_total_in > subway_high_accum:
            return RiskLevel.HIGH
        if avg_rate > settings.subway_atrisk_precip_rate or forecast_total_in > subway_atrisk_accum:
            return RiskLevel.AT_RISK

    # Open cut stations
    if "open cut" in structure_lower:
        if avg_rate > settings.opencut_high_precip_rate or forecast_total_in > opencut_high_accum:
            return RiskLevel.HIGH
        if avg_rate > settings.opencut_atrisk_precip_rate or forecast_total_in > opencut_atrisk_accum:
            return RiskLevel.AT_RISK

    # Coastal flooding factor
    if is_coastal and tide_level_ft is not None:
        if tide_level_ft > settings.tide_high_level:
            if avg_rate > settings.coastal_high_precip_rate:
                return RiskLevel.HIGH
            if avg_rate > settings.coastal_atrisk_precip_rate:
                return RiskLevel.AT_RISK

    # Elevated stations
    if "elevated" in structure_lower:
        if avg_rate > settings.elevated_atrisk_precip_rate:
            return RiskLevel.AT_RISK
        return RiskLevel.LOW

    # Default thresholds
    if avg_rate > settings.default_high_precip_rate or forecast_total_in > default_high_accum:
        return RiskLevel.HIGH
    if avg_rate > settings.default_atrisk_precip_rate or forecast_total_in > default_atrisk_accum:
        return RiskLevel.AT_RISK

    return RiskLevel.LOW
