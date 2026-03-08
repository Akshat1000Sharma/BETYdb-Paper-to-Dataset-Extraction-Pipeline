from __future__ import annotations

import json
import logging
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

from config import LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE, PROMPT_DIR, get_api_key
from pipeline.chunker import TextChunk

logger = logging.getLogger(__name__)


# Load system prompt
def _load_system_prompt() -> SystemMessage:
    text = (PROMPT_DIR / "extraction_prompt.txt").read_text(encoding="utf-8")
    return SystemMessage(content=text)


# Build extraction chain
def _build_chain(model: ChatGoogleGenerativeAI):
    system_msg = _load_system_prompt()
    template = ChatPromptTemplate.from_messages([
        system_msg,
        MessagesPlaceholder(variable_name="messages"),
    ])
    return template | model


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
    model  = build_model()
    chain  = _build_chain(model)
    all_results: list[dict] = []

    for chunk in chunks:
        logger.info(
            "Extracting chunk %d/%d (pages %s)...",
            chunk.chunk_id + 1,
            len(chunks),
            chunk.page_numbers,
        )
        result = _extract_chunk(chain, chunk)
        if result:
            all_results.append(result)

    merged = _merge_extractions(all_results)
    logger.info("Merged extractions from %d chunk(s).", len(all_results))
    return merged


# Extract single chunk
def _extract_chunk(chain, chunk: TextChunk) -> dict | None:
    user_text = f"[Pages: {chunk.page_numbers}]\n\n{chunk.text}"

    try:
        response = chain.invoke({
            "messages": [HumanMessage(content=user_text)],
        })
        return _parse_json_response(response.content.strip(), chunk.chunk_id)

    except Exception as exc:
        logger.error("Extraction error on chunk %d: %s", chunk.chunk_id, exc)
        return None


# Parse JSON response
def _parse_json_response(text: str, chunk_id: int) -> dict | None:
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$",          "", text, flags=re.MULTILINE)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning(
            "JSON parse error on chunk %d: %s - attempting repair...", chunk_id, exc
        )
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        logger.error("Could not parse JSON from chunk %d - skipping.", chunk_id)
        return None


# Merge extractions
def _merge_extractions(results: list[dict]) -> dict:
    if not results:
        return _empty_extraction()

    merged = _empty_extraction()
    for result in results:
        for key in merged:
            if key in result and isinstance(result[key], list):
                merged[key].extend(result[key])

    for key in merged:
        merged[key] = _deduplicate(merged[key])

    return merged


# Deduplicate by first field value
def _deduplicate(items: list[dict]) -> list[dict]:
    seen:   set        = set()
    unique: list[dict] = []

    for item in items:
        if not item:
            continue
        first_key = next(iter(item))
        field = item[first_key]
        val   = field.get("value") if isinstance(field, dict) else None
        if val and val in seen:
            continue
        if val:
            seen.add(val)
        unique.append(item)

    return unique


# Empty extraction template
def _empty_extraction() -> dict:
    return {
        "sites":             [],
        "species":           [],
        "cultivars":         [],
        "traits":            [],
        "variables":         [],
        "methods":           [],
        "treatments":        [],
        "management_events": [],
    }
