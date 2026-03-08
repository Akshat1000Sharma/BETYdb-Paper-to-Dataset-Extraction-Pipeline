from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dateutil import parser as dateutil_parser

from config import LAT_RANGE, LON_RANGE, MIN_CONFIDENCE
from pipeline.ir_schema import ExtractionStatus, IRField, IntermediateRepresentation

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    ERROR   = "ERROR"
    WARNING = "WARNING"


@dataclass
class ValidationIssue:
    severity:    Severity
    entity:      str
    message:     str
    source_text: str = ""
    page_number: int | None = None


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        return (
            f"Validation: {len(self.errors)} error(s), "
            f"{len(self.warnings)} warning(s). "
            f"{'PASS' if self.is_valid else 'FAIL'}"
        )


# Validate IR
def validate(ir: IntermediateRepresentation) -> ValidationResult:
    result = ValidationResult()

    _validate_sites(ir, result)
    _validate_traits(ir, result)
    _validate_variables(ir, result)
    _validate_methods(ir, result)
    _validate_management_events(ir, result)
    _check_low_confidence(ir, result)

    logger.info(result.summary())
    return result


# Validate sites
def _validate_sites(ir: IntermediateRepresentation, result: ValidationResult) -> None:
    for i, site in enumerate(ir.sites):
        prefix = f"sites[{i}]"

        _require_value(site.sitename, f"{prefix}.sitename", result)

        _validate_coordinate(
            site.latitude, f"{prefix}.latitude", LAT_RANGE, result
        )
        _validate_coordinate(
            site.longitude, f"{prefix}.longitude", LON_RANGE, result
        )

        sand = _to_float(site.sand.value)
        silt = _to_float(site.silt.value)
        clay = _to_float(site.clay.value)
        if sand is not None and silt is not None and clay is not None:
            total = sand + silt + clay
            if not (95.0 <= total <= 105.0):
                result.issues.append(ValidationIssue(
                    severity=Severity.WARNING,
                    entity=f"{prefix}.soil_texture",
                    message=f"Sand+Silt+Clay = {total:.1f}%, expected ~100%.",
                    source_text=site.sand.source_text,
                    page_number=site.sand.page_number,
                ))


# Validate traits
def _validate_traits(ir: IntermediateRepresentation, result: ValidationResult) -> None:
    trait_names = {v.name.value for v in ir.variables if v.name.value}

    for i, trait in enumerate(ir.traits):
        prefix = f"traits[{i}]"

        _require_value(trait.trait, f"{prefix}.trait", result)
        _require_value(trait.mean,  f"{prefix}.mean",  result)

        if trait.datetime.value and trait.datetime.status != ExtractionStatus.UNRESOLVED:
            _validate_datetime(trait.datetime, f"{prefix}.datetime", result)

        if trait.mean.value is not None:
            if _to_float(trait.mean.value) is None:
                result.issues.append(ValidationIssue(
                    severity=Severity.ERROR,
                    entity=f"{prefix}.mean",
                    message=f"Non-numeric mean value: '{trait.mean.value}'.",
                    source_text=trait.mean.source_text,
                    page_number=trait.mean.page_number,
                ))

        if trait.stat.value is not None and _to_float(trait.stat.value) is None:
            result.issues.append(ValidationIssue(
                severity=Severity.WARNING,
                entity=f"{prefix}.stat",
                message=f"Non-numeric stat value: '{trait.stat.value}'.",
                source_text=trait.stat.source_text,
                page_number=trait.stat.page_number,
            ))

        if trait.trait.value and trait_names and trait.trait.value not in trait_names:
            result.issues.append(ValidationIssue(
                severity=Severity.WARNING,
                entity=f"{prefix}.trait",
                message=(
                    f"Trait '{trait.trait.value}' not listed in variables table. "
                    "Consider adding it."
                ),
                source_text=trait.trait.source_text,
                page_number=trait.trait.page_number,
            ))


# Validate variables
def _validate_variables(ir: IntermediateRepresentation, result: ValidationResult) -> None:
    for i, var in enumerate(ir.variables):
        prefix = f"variables[{i}]"
        _require_value(var.name,  f"{prefix}.name",  result)
        _require_value(var.units, f"{prefix}.units", result)


# Validate methods
def _validate_methods(ir: IntermediateRepresentation, result: ValidationResult) -> None:
    for i, method in enumerate(ir.methods):
        _require_value(method.name, f"methods[{i}].name", result)


# Validate management events
def _validate_management_events(
    ir: IntermediateRepresentation, result: ValidationResult
) -> None:
    for i, ev in enumerate(ir.management_events):
        prefix = f"management_events[{i}]"
        _require_value(ev.event, f"{prefix}.event", result)
        if ev.datetime.value:
            _validate_datetime(ev.datetime, f"{prefix}.datetime", result)


# Flag low confidence fields
def _check_low_confidence(
    ir: IntermediateRepresentation, result: ValidationResult
) -> None:
    def _walk(entity_name: str, obj: Any) -> None:
        if isinstance(obj, IRField):
            if (
                obj.status == ExtractionStatus.EXTRACTED
                and obj.confidence < MIN_CONFIDENCE
                and obj.value is not None
            ):
                result.issues.append(ValidationIssue(
                    severity=Severity.WARNING,
                    entity=entity_name,
                    message=(
                        f"Low confidence ({obj.confidence:.2f}) for extracted "
                        f"value '{obj.value}'."
                    ),
                    source_text=obj.source_text,
                    page_number=obj.page_number,
                ))
        elif hasattr(obj, "__dict__"):
            for attr, val in obj.__dict__.items():
                _walk(f"{entity_name}.{attr}", val)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                _walk(f"{entity_name}[{idx}]", item)

    _walk("ir", ir)


# Require non-empty value
def _require_value(f: IRField, entity: str, result: ValidationResult) -> None:
    if f.value is None or f.value == "":
        result.issues.append(ValidationIssue(
            severity=Severity.ERROR,
            entity=entity,
            message="Required field is missing or unresolved.",
            source_text=f.source_text,
            page_number=f.page_number,
        ))


# Validate coordinate range
def _validate_coordinate(
    f: IRField, entity: str, valid_range: tuple[float, float], result: ValidationResult
) -> None:
    if f.value is None or f.status == ExtractionStatus.UNRESOLVED:
        return
    val = _to_float(f.value)
    if val is None:
        result.issues.append(ValidationIssue(
            severity=Severity.ERROR,
            entity=entity,
            message=f"Non-numeric coordinate value: '{f.value}'.",
            source_text=f.source_text,
            page_number=f.page_number,
        ))
    elif not (valid_range[0] <= val <= valid_range[1]):
        result.issues.append(ValidationIssue(
            severity=Severity.ERROR,
            entity=entity,
            message=f"Coordinate {val} out of range {valid_range}.",
            source_text=f.source_text,
            page_number=f.page_number,
        ))


# Validate datetime format
def _validate_datetime(f: IRField, entity: str, result: ValidationResult) -> None:
    if not f.value:
        return
    try:
        dateutil_parser.parse(str(f.value))
    except (ValueError, OverflowError):
        result.issues.append(ValidationIssue(
            severity=Severity.WARNING,
            entity=entity,
            message=f"Cannot parse datetime: '{f.value}'.",
            source_text=f.source_text,
            page_number=f.page_number,
        ))


# Safe float conversion
def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
