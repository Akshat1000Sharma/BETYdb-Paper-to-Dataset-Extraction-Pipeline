from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


# Provenance field
class ExtractedField(BaseModel):
    value: Optional[Any] = Field(
        default=None,
        description="The extracted value, or null if not found."
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Confidence score between 0.0 and 1.0."
    )
    source_text: str = Field(
        default="",
        description="Exact sentence(s) from the paper that justify this value."
    )
    page_number: Optional[int] = Field(
        default=None,
        description="Page number where the value was found."
    )
    status: Literal["extracted", "inferred", "unresolved"] = Field(
        default="unresolved",
        description="'extracted' = directly stated; 'inferred' = logically implied; 'unresolved' = not found."
    )


# Entity models
class SiteExtraction(BaseModel):
    sitename:  ExtractedField = Field(default_factory=ExtractedField, description="Name of the experimental site or field station.")
    latitude:  ExtractedField = Field(default_factory=ExtractedField, description="Latitude in decimal degrees.")
    longitude: ExtractedField = Field(default_factory=ExtractedField, description="Longitude in decimal degrees.")
    elevation: ExtractedField = Field(default_factory=ExtractedField, description="Elevation in metres above sea level.")
    notes:     ExtractedField = Field(default_factory=ExtractedField, description="Soil type, land use history, or other site notes.")
    sand:      ExtractedField = Field(default_factory=ExtractedField, description="Sand fraction of soil texture (%).")
    silt:      ExtractedField = Field(default_factory=ExtractedField, description="Silt fraction of soil texture (%).")
    clay:      ExtractedField = Field(default_factory=ExtractedField, description="Clay fraction of soil texture (%).")


class SpeciesExtraction(BaseModel):
    name: ExtractedField = Field(default_factory=ExtractedField, description="Scientific or common species name (e.g. 'Zea mays', 'maize').")


class CultivarExtraction(BaseModel):
    name:  ExtractedField = Field(default_factory=ExtractedField, description="Cultivar or hybrid name (e.g. 'DKC52-61').")
    notes: ExtractedField = Field(default_factory=ExtractedField, description="Cultivar notes: maturity group, brand, traits, etc.")


class TraitExtraction(BaseModel):
    datetime: ExtractedField = Field(default_factory=ExtractedField, description="ISO 8601 measurement date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS+00:00).")
    crop:     ExtractedField = Field(default_factory=ExtractedField, description="Species name for this measurement.")
    cultivar: ExtractedField = Field(default_factory=ExtractedField, description="Cultivar name for this measurement.")
    sitename: ExtractedField = Field(default_factory=ExtractedField, description="Site name for this measurement.")
    trait:    ExtractedField = Field(default_factory=ExtractedField, description="Trait variable name (e.g. 'canopy_height', 'grain_yield').")
    method:   ExtractedField = Field(default_factory=ExtractedField, description="Measurement method name.")
    mean:     ExtractedField = Field(default_factory=ExtractedField, description="Numeric mean value of the trait.")
    units:    ExtractedField = Field(default_factory=ExtractedField, description="Units of the mean value (e.g. 'm', '%', 'Mg ha-1').")
    n:        ExtractedField = Field(default_factory=ExtractedField, description="Sample size (number of replicates or plants).")
    statname: ExtractedField = Field(default_factory=ExtractedField, description="Name of the reported statistic: SE, SD, or CI.")
    stat:     ExtractedField = Field(default_factory=ExtractedField, description="Numeric value of the reported statistic.")


class VariableExtraction(BaseModel):
    name:        ExtractedField = Field(default_factory=ExtractedField, description="Variable name as used in the traits table.")
    units:       ExtractedField = Field(default_factory=ExtractedField, description="Units of measurement.")
    description: ExtractedField = Field(default_factory=ExtractedField, description="Plain-language description of what is measured.")


class MethodExtraction(BaseModel):
    name:        ExtractedField = Field(default_factory=ExtractedField, description="Short method name (e.g. 'Dumas combustion').")
    description: ExtractedField = Field(default_factory=ExtractedField, description="Full description of the method and instruments used.")


class TreatmentExtraction(BaseModel):
    name:        ExtractedField = Field(default_factory=ExtractedField, description="Short treatment name (e.g. 'High N', 'Irrigated').")
    description: ExtractedField = Field(default_factory=ExtractedField, description="Full description of the treatment level and application.")


class ManagementEventExtraction(BaseModel):
    event:       ExtractedField = Field(default_factory=ExtractedField, description="Event type (e.g. 'planting', 'fertilization', 'harvest').")
    datetime:    ExtractedField = Field(default_factory=ExtractedField, description="ISO 8601 date of the event.")
    description: ExtractedField = Field(default_factory=ExtractedField, description="Details of the management operation.")


# Response wrappers (one per API call)
class SitesResponse(BaseModel):
    sites: List[SiteExtraction] = Field(default_factory=list, description="All experimental sites found in the text.")

class SpeciesResponse(BaseModel):
    species: List[SpeciesExtraction] = Field(default_factory=list, description="All crop species found in the text.")

class CultivarsResponse(BaseModel):
    cultivars: List[CultivarExtraction] = Field(default_factory=list, description="All cultivars or genotypes found in the text.")

class TraitsResponse(BaseModel):
    traits: List[TraitExtraction] = Field(default_factory=list, description="All trait measurements found in the text.")

class VariablesResponse(BaseModel):
    variables: List[VariableExtraction] = Field(default_factory=list, description="All trait variable definitions found in the text.")

class MethodsResponse(BaseModel):
    methods: List[MethodExtraction] = Field(default_factory=list, description="All measurement methods found in the text.")

class TreatmentsResponse(BaseModel):
    treatments: List[TreatmentExtraction] = Field(default_factory=list, description="All experimental treatments found in the text.")

class ManagementEventsResponse(BaseModel):
    management_events: List[ManagementEventExtraction] = Field(default_factory=list, description="All management events found in the text.")


# Section registry: key -> (response model, list field name)
SECTION_REGISTRY: dict[str, tuple[type[BaseModel], str]] = {
    "sites":             (SitesResponse,            "sites"),
    "species":           (SpeciesResponse,           "species"),
    "cultivars":         (CultivarsResponse,         "cultivars"),
    "traits":            (TraitsResponse,            "traits"),
    "variables":         (VariablesResponse,         "variables"),
    "methods":           (MethodsResponse,           "methods"),
    "treatments":        (TreatmentsResponse,        "treatments"),
    "management_events": (ManagementEventsResponse,  "management_events"),
}
