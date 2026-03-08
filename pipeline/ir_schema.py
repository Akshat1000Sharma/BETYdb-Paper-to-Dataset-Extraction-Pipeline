from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ExtractionStatus(str, Enum):
    EXTRACTED  = "extracted"
    INFERRED   = "inferred"
    UNRESOLVED = "unresolved"


@dataclass
class IRField:
    value:       Any                   = None
    confidence:  float                 = 0.0
    source_text: str                   = ""
    page_number: Optional[int]         = None
    status:      ExtractionStatus      = ExtractionStatus.UNRESOLVED

    def __post_init__(self):
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        if isinstance(self.status, str):
            self.status = ExtractionStatus(self.status)


@dataclass
class IRSite:
    sitename:  IRField = field(default_factory=IRField)
    latitude:  IRField = field(default_factory=IRField)
    longitude: IRField = field(default_factory=IRField)
    elevation: IRField = field(default_factory=IRField)
    notes:     IRField = field(default_factory=IRField)
    sand:      IRField = field(default_factory=IRField)
    silt:      IRField = field(default_factory=IRField)
    clay:      IRField = field(default_factory=IRField)


@dataclass
class IRSpecies:
    name: IRField = field(default_factory=IRField)


@dataclass
class IRCultivar:
    name:  IRField = field(default_factory=IRField)
    notes: IRField = field(default_factory=IRField)


@dataclass
class IRTrait:
    datetime:  IRField = field(default_factory=IRField)
    crop:      IRField = field(default_factory=IRField)
    cultivar:  IRField = field(default_factory=IRField)
    sitename:  IRField = field(default_factory=IRField)
    trait:     IRField = field(default_factory=IRField)
    method:    IRField = field(default_factory=IRField)
    mean:      IRField = field(default_factory=IRField)
    units:     IRField = field(default_factory=IRField)
    n:         IRField = field(default_factory=IRField)
    statname:  IRField = field(default_factory=IRField)
    stat:      IRField = field(default_factory=IRField)


@dataclass
class IRVariable:
    name:        IRField = field(default_factory=IRField)
    units:       IRField = field(default_factory=IRField)
    description: IRField = field(default_factory=IRField)


@dataclass
class IRMethod:
    name:        IRField = field(default_factory=IRField)
    description: IRField = field(default_factory=IRField)


@dataclass
class IRTreatment:
    name:        IRField = field(default_factory=IRField)
    description: IRField = field(default_factory=IRField)


@dataclass
class IRManagementEvent:
    event:       IRField = field(default_factory=IRField)
    datetime:    IRField = field(default_factory=IRField)
    description: IRField = field(default_factory=IRField)


@dataclass
class IntermediateRepresentation:
    sites:             list = field(default_factory=list)
    species:           list = field(default_factory=list)
    cultivars:         list = field(default_factory=list)
    traits:            list = field(default_factory=list)
    variables:         list = field(default_factory=list)
    methods:           list = field(default_factory=list)
    treatments:        list = field(default_factory=list)
    management_events: list = field(default_factory=list)


# Parse raw dict to IRField
def _field(raw) -> IRField:
    if raw is None or not isinstance(raw, dict):
        return IRField(value=None, status=ExtractionStatus.UNRESOLVED)
    return IRField(
        value=raw.get("value"),
        confidence=float(raw.get("confidence", 0.0)),
        source_text=raw.get("source_text", ""),
        page_number=raw.get("page_number"),
        status=ExtractionStatus(raw.get("status", "unresolved")),
    )


# Build IR from raw extraction
def build_ir(raw: dict) -> IntermediateRepresentation:
    ir = IntermediateRepresentation()

    for s in raw.get("sites", []):
        ir.sites.append(IRSite(
            sitename=_field(s.get("sitename")),
            latitude=_field(s.get("latitude")),
            longitude=_field(s.get("longitude")),
            elevation=_field(s.get("elevation")),
            notes=_field(s.get("notes")),
            sand=_field(s.get("sand")),
            silt=_field(s.get("silt")),
            clay=_field(s.get("clay")),
        ))

    for sp in raw.get("species", []):
        ir.species.append(IRSpecies(name=_field(sp.get("name"))))

    for c in raw.get("cultivars", []):
        ir.cultivars.append(IRCultivar(
            name=_field(c.get("name")),
            notes=_field(c.get("notes")),
        ))

    for t in raw.get("traits", []):
        ir.traits.append(IRTrait(
            datetime=_field(t.get("datetime")),
            crop=_field(t.get("crop")),
            cultivar=_field(t.get("cultivar")),
            sitename=_field(t.get("sitename")),
            trait=_field(t.get("trait")),
            method=_field(t.get("method")),
            mean=_field(t.get("mean")),
            units=_field(t.get("units")),
            n=_field(t.get("n")),
            statname=_field(t.get("statname")),
            stat=_field(t.get("stat")),
        ))

    for v in raw.get("variables", []):
        ir.variables.append(IRVariable(
            name=_field(v.get("name")),
            units=_field(v.get("units")),
            description=_field(v.get("description")),
        ))

    for m in raw.get("methods", []):
        ir.methods.append(IRMethod(
            name=_field(m.get("name")),
            description=_field(m.get("description")),
        ))

    for tr in raw.get("treatments", []):
        ir.treatments.append(IRTreatment(
            name=_field(tr.get("name")),
            description=_field(tr.get("description")),
        ))

    for ev in raw.get("management_events", []):
        ir.management_events.append(IRManagementEvent(
            event=_field(ev.get("event")),
            datetime=_field(ev.get("datetime")),
            description=_field(ev.get("description")),
        ))

    return ir
