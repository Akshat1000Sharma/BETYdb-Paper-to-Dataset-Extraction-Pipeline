from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from config import CSV_FILES
from pipeline.ir_schema import ExtractionStatus, IntermediateRepresentation

logger = logging.getLogger(__name__)


# Export all CSVs
def export_all(ir: IntermediateRepresentation) -> dict[str, Path]:
    written: dict[str, Path] = {}

    writers = {
        "traits_long":       (_traits_long_rows,       _TRAITS_LONG_COLS),
        "traits_wide":       (_traits_wide_rows,       None),
        "sites":             (_sites_rows,             _SITES_COLS),
        "cultivars":         (_cultivars_rows,         _CULTIVARS_COLS),
        "species":           (_species_rows,           _SPECIES_COLS),
        "variables":         (_variables_rows,         _VARIABLES_COLS),
        "methods":           (_methods_rows,           _METHODS_COLS),
        "treatments":        (_treatments_rows,        _TREATMENTS_COLS),
        "management_events": (_management_events_rows, _MGMT_COLS),
    }

    for table_name, (row_fn, columns) in writers.items():
        path = CSV_FILES[table_name]
        rows = row_fn(ir)

        if table_name == "traits_wide":
            columns = _traits_wide_columns(ir)

        _write_csv(path, columns, rows)
        written[table_name] = path
        logger.info("Wrote %d rows => %s", len(rows), path)

    return written


# Column definitions
_TRAITS_LONG_COLS = [
    "datetime", "crop", "variety", "sitename",
    "trait", "method", "mean", "n", "statname", "stat",
    "units", "confidence", "source_text", "page_number", "status",
]

_SITES_COLS = [
    "sitename", "latitude", "longitude", "elevation",
    "geometry", "notes", "sand", "silt", "clay",
]

_CULTIVARS_COLS = ["name", "notes"]
_SPECIES_COLS   = ["name"]
_VARIABLES_COLS = ["name", "units", "description"]
_METHODS_COLS   = ["name", "description"]
_TREATMENTS_COLS= ["name", "description"]
_MGMT_COLS      = ["event", "datetime", "description"]


# Safe value getter
def _v(field_obj: Any) -> Any:
    if hasattr(field_obj, "value"):
        v = field_obj.value
        return "" if v is None else v
    return "" if field_obj is None else field_obj


# Row builders
def _traits_long_rows(ir: IntermediateRepresentation) -> list[dict]:
    rows = []
    for t in ir.traits:
        rows.append({
            "datetime":    _v(t.datetime),
            "crop":        _v(t.crop),
            "variety":     _v(t.cultivar),
            "sitename":    _v(t.sitename),
            "trait":       _v(t.trait),
            "method":      _v(t.method),
            "mean":        _v(t.mean),
            "n":           _v(t.n),
            "statname":    _v(t.statname),
            "stat":        _v(t.stat),
            "units":       _v(t.units),
            "confidence":  t.trait.confidence,
            "source_text": t.trait.source_text,
            "page_number": t.trait.page_number or "",
            "status":      t.trait.status.value,
        })
    return rows


# Wide column builder
def _traits_wide_columns(ir: IntermediateRepresentation) -> list[str]:
    base = ["datetime", "crop", "cultivar", "sitename"]
    trait_names = sorted({_v(t.trait) for t in ir.traits if _v(t.trait)})
    return base + trait_names


# Pivot to wide
def _traits_wide_rows(ir: IntermediateRepresentation) -> list[dict]:
    key_order: list[tuple] = []
    groups: dict[tuple, dict] = {}

    for t in ir.traits:
        key = (
            str(_v(t.datetime)),
            str(_v(t.crop)),
            str(_v(t.cultivar)),
            str(_v(t.sitename)),
        )
        if key not in groups:
            key_order.append(key)
            groups[key] = {
                "datetime": key[0],
                "crop":     key[1],
                "cultivar": key[2],
                "sitename": key[3],
            }
        trait_name = _v(t.trait)
        if trait_name:
            groups[key][trait_name] = _v(t.mean)

    return [groups[k] for k in key_order]


# Sites rows
def _sites_rows(ir: IntermediateRepresentation) -> list[dict]:
    rows = []
    for s in ir.sites:
        lat = _v(s.latitude)
        lon = _v(s.longitude)
        geometry = ""
        if lat != "" and lon != "":
            try:
                geometry = f"POINT({float(lon):.6f} {float(lat):.6f})"
            except (TypeError, ValueError):
                geometry = ""
        rows.append({
            "sitename":  _v(s.sitename),
            "latitude":  lat,
            "longitude": lon,
            "elevation": _v(s.elevation),
            "geometry":  geometry,
            "notes":     _v(s.notes),
            "sand":      _v(s.sand),
            "silt":      _v(s.silt),
            "clay":      _v(s.clay),
        })
    return rows


def _cultivars_rows(ir: IntermediateRepresentation) -> list[dict]:
    return [{"name": _v(c.name), "notes": _v(c.notes)} for c in ir.cultivars]


def _species_rows(ir: IntermediateRepresentation) -> list[dict]:
    return [{"name": _v(sp.name)} for sp in ir.species]


def _variables_rows(ir: IntermediateRepresentation) -> list[dict]:
    return [
        {"name": _v(v.name), "units": _v(v.units), "description": _v(v.description)}
        for v in ir.variables
    ]


def _methods_rows(ir: IntermediateRepresentation) -> list[dict]:
    return [{"name": _v(m.name), "description": _v(m.description)} for m in ir.methods]


def _treatments_rows(ir: IntermediateRepresentation) -> list[dict]:
    return [{"name": _v(t.name), "description": _v(t.description)} for t in ir.treatments]


def _management_events_rows(ir: IntermediateRepresentation) -> list[dict]:
    return [
        {
            "event":       _v(ev.event),
            "datetime":    _v(ev.datetime),
            "description": _v(ev.description),
        }
        for ev in ir.management_events
    ]


# CSV writer
def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)
