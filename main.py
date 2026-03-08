from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import config as cfg
from pipeline.pdf_parser import extract_text
from pipeline.chunker    import chunk_pages
from pipeline.ir_schema  import build_ir
from pipeline.validator  import validate, Severity
from pipeline.exporter   import export_all


# Print helpers
def _print(msg: str) -> None:
    import re
    print(re.sub(r"\[/?[^\]]+\]", "", msg))


def _rule(title: str = "") -> None:
    w = 60
    if title:
        pad = (w - len(title) - 2) // 2
        print("=" * pad + " " + title + " " + "=" * pad)
    else:
        print("=" * w)


# CLI parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Extract agronomic data from a PDF and export BETYdb-compatible CSVs."
    )
    p.add_argument("--pdf",        required=True,  help="Path to input PDF file.")
    p.add_argument("--output-dir", default=None,   help="Override output directory.")
    p.add_argument("--chunk-size", type=int, default=cfg.CHUNK_SIZE,
                   help=f"Characters per chunk (default: {cfg.CHUNK_SIZE}).")
    p.add_argument("--overlap",    type=int, default=cfg.CHUNK_OVERLAP,
                   help=f"Chunk overlap characters (default: {cfg.CHUNK_OVERLAP}).")
    p.add_argument("--use-cache", "--skip-llm", dest="use_cache", action="store_true",
                   default=False, help="Load cached raw_extraction.json instead of running extraction.")
    p.add_argument("--verbose",    action="store_true", default=False,
                   help="Enable DEBUG logging.")
    return p


# Entry point
def main(args=None) -> None:
    parser = build_parser()
    opts   = parser.parse_args(args)

    level = logging.DEBUG if opts.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    if opts.output_dir:
        out = Path(opts.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for key in cfg.CSV_FILES:
            cfg.CSV_FILES[key] = out / cfg.CSV_FILES[key].name

    pdf_path   = Path(opts.pdf)
    cache_path = cfg.OUTPUT_DIR / "raw_extraction.json"

    _rule("BETYdb Extractor")

    # Step 1: PDF parsing
    _print("Step 1: Parsing PDF...")
    pages = extract_text(pdf_path)
    if not pages:
        _print("ERROR: No text could be extracted from the PDF. Aborting.")
        sys.exit(1)
    _print(f"  => Extracted text from {len(pages)} page(s).")

    # Step 2: Chunking
    _print("Step 2: Chunking document...")
    chunks = chunk_pages(pages, chunk_size=opts.chunk_size, overlap=opts.overlap)
    _print(f"  => Produced {len(chunks)} chunk(s).")

    # Step 3: Extraction
    if opts.use_cache and cache_path.exists():
        _print("Step 3: Loading cached extraction...")
        with open(cache_path, encoding="utf-8") as fh:
            raw_extraction = json.load(fh)
        _print(f"  => Loaded from {cache_path}")
    else:
        try:
            from pipeline.llm_extractor import extract_from_chunks
        except ImportError as exc:
            _print(
                f"ERROR: Required extraction packages not installed.\n"
                f"  Run:  pip install langchain langchain-core langchain-google-genai python-dotenv\n"
                f"  Or use --use-cache to replay from a cached extraction.\n"
                f"  Detail: {exc}"
            )
            sys.exit(1)

        _print("Step 3: Running extraction...")
        raw_extraction = extract_from_chunks(chunks)
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(raw_extraction, fh, indent=2)
        _print(f"  => Raw extraction cached to {cache_path}")

    # Step 4: Build IR
    _print("Step 4: Building Intermediate Representation...")
    ir = build_ir(raw_extraction)
    _print(
        f"  => Sites: {len(ir.sites)}  "
        f"Species: {len(ir.species)}  "
        f"Cultivars: {len(ir.cultivars)}  "
        f"Traits: {len(ir.traits)}  "
        f"Variables: {len(ir.variables)}"
    )

    # Step 5: Validation
    _print("Step 5: Validating...")
    val_result = validate(ir)
    _print_validation(val_result)
    if not val_result.is_valid:
        _print("WARNING: Validation errors found. CSVs exported but require review.")

    # Step 6: Export CSVs
    _print("Step 6: Exporting CSV files...")
    written = export_all(ir)
    _print("\nExported files:")
    for name, path in written.items():
        _print(f"  {name:<22} => {path}")

    _rule("Done")


# Validation summary
def _print_validation(val_result) -> None:
    if not val_result.issues:
        _print("  => No issues found.")
        return
    for issue in val_result.issues:
        page = f" (page {issue.page_number})" if issue.page_number else ""
        _print(f"  [{issue.severity.value}] {issue.entity}: {issue.message}{page}")
    _print(f"  => {val_result.summary()}")


if __name__ == "__main__":
    main()
