from __future__ import annotations

import logging
from typing import Any

from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

from config import LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE, get_api_key
from pipeline.chunker import TextChunk
from pipeline.pydantic_models import SECTION_REGISTRY

logger = logging.getLogger(__name__)


# Per-section prompts
_SECTION_PROMPTS: dict[str, str] = {
    "sites": """\
Read the scientific paper excerpt below and extract ALL experimental SITE information.

For each site record:
- sitename: name of the field station or experimental farm
- latitude / longitude: decimal degrees (convert DMS if needed)
- elevation: metres above sea level
- notes: soil type, land history, climate notes
- sand / silt / clay: soil texture fractions in percent

For every field set:
  value       = extracted value (null if absent)
  confidence  = 0.0-1.0
  source_text = exact quote from the text
  page_number = page number
  status      = "extracted" | "inferred" | "unresolved"

{format_instructions}

PAPER TEXT:
{text}
""",

    "species": """\
Read the scientific paper excerpt below and extract ALL crop SPECIES mentioned (scientific and common names).

For every field set confidence, source_text, page_number, and status.

{format_instructions}

PAPER TEXT:
{text}
""",

    "cultivars": """\
Read the scientific paper excerpt below and extract ALL cultivars, varieties, hybrids, or genotypes mentioned.
Include maturity group, brand, or other notes where available.

For every field set confidence, source_text, page_number, and status.

{format_instructions}

PAPER TEXT:
{text}
""",

    "traits": """\
Read the scientific paper excerpt below and extract ALL measured trait values reported.

Create one entry per distinct (trait, cultivar, site, date) combination.
- datetime: ISO 8601 (YYYY-MM-DD)
- mean: numeric mean value
- units: units string
- n: sample size
- statname: SE / SD / CI
- stat: numeric stat value
- For ranges (e.g. 2.1-2.5), use the midpoint as mean

For every field set confidence, source_text, page_number, and status.

{format_instructions}

PAPER TEXT:
{text}
""",

    "variables": """\
Read the scientific paper excerpt below and extract definitions of all MEASURED VARIABLES (traits).
Include name, units, and a plain-language description.

For every field set confidence, source_text, page_number, and status.

{format_instructions}

PAPER TEXT:
{text}
""",

    "methods": """\
Read the scientific paper excerpt below and extract all MEASUREMENT METHODS described.
Include instrument names, protocols, and standards referenced.

For every field set confidence, source_text, page_number, and status.

{format_instructions}

PAPER TEXT:
{text}
""",

    "treatments": """\
Read the scientific paper excerpt below and extract all EXPERIMENTAL TREATMENTS applied (e.g. nitrogen rates, irrigation levels, tillage types).

For every field set confidence, source_text, page_number, and status.

{format_instructions}

PAPER TEXT:
{text}
""",

    "management_events": """\
Read the scientific paper excerpt below and extract all FIELD MANAGEMENT EVENTS (planting, fertilization, irrigation, pesticide application, harvest, etc.) with their dates.

For every field set confidence, source_text, page_number, and status.
Convert all dates to ISO 8601 (YYYY-MM-DD).

{format_instructions}

PAPER TEXT:
{text}
""",
}


# Init extraction model
def build_model() -> ChatGoogleGenerativeAI:
    load_dotenv()
    api_key = get_api_key()
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=api_key,
        temperature=LLM_TEMPERATURE,
        max_output_tokens=LLM_MAX_TOKENS,
    )


# Extract all chunks
def extract_from_chunks(chunks: list[TextChunk]) -> dict:
    model = build_model()
    merged: dict[str, list] = {key: [] for key in SECTION_REGISTRY}

    for chunk in chunks:
        logger.info(
            "Extracting chunk %d/%d (pages %s)...",
            chunk.chunk_id + 1,
            len(chunks),
            chunk.page_numbers,
        )
        chunk_text = f"[Pages: {chunk.page_numbers}]\n\n{chunk.text}"
        chunk_result = _extract_all_sections(model, chunk_text, chunk.chunk_id)

        for key, items in chunk_result.items():
            merged[key].extend(items)

    for key in merged:
        merged[key] = _deduplicate(merged[key])

    total = sum(len(v) for v in merged.values())
    logger.info("Extraction complete: %d total entities across %d section(s).", total, len(merged))
    return merged


# Extract all sections for one chunk
def _extract_all_sections(
    model: ChatGoogleGenerativeAI,
    chunk_text: str,
    chunk_id: int,
) -> dict[str, list]:
    result: dict[str, list] = {}
    for section_key, (response_model, list_field) in SECTION_REGISTRY.items():
        result[section_key] = _extract_section(
            model=model,
            section_key=section_key,
            response_model=response_model,
            list_field=list_field,
            chunk_text=chunk_text,
            chunk_id=chunk_id,
        )
    return result


# Extract one section via PydanticOutputParser
def _extract_section(
    model: ChatGoogleGenerativeAI,
    section_key: str,
    response_model: type,
    list_field: str,
    chunk_text: str,
    chunk_id: int,
) -> list[dict]:
    parser = PydanticOutputParser(pydantic_object=response_model)
    template = PromptTemplate(
        template=_SECTION_PROMPTS[section_key],
        input_variables=["text"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = template | model | parser

    try:
        parsed: Any = chain.invoke({"text": chunk_text})
        items_as_models = getattr(parsed, list_field, [])
        return [item.model_dump() for item in items_as_models]

    except ValidationError as exc:
        logger.warning("Validation error in section '%s' chunk %d: %s", section_key, chunk_id, exc)
        return []
    except Exception as exc:
        logger.error("Extraction error in section '%s' chunk %d: %s", section_key, chunk_id, exc)
        return []


# Deduplicate by first-field value
def _deduplicate(items: list[dict]) -> list[dict]:
    seen:   set        = set()
    unique: list[dict] = []

    for item in items:
        if not item:
            continue
        first_key = next(iter(item))
        field_data = item.get(first_key, {})
        val = field_data.get("value") if isinstance(field_data, dict) else None
        if val is not None and str(val) in seen:
            continue
        if val is not None:
            seen.add(str(val))
        unique.append(item)

    return unique
