# BETYdb Extractor

A command-line pipeline that extracts agronomic and ecological experiment data from scientific papers (PDF) and converts them into structured CSV tables compatible with the **BETYdb** bulk upload template.

---

## Architecture

```
PDF -> Text Extraction -> Chunking -> Extraction -> IR -> Validation -> CSV Export
```

| Module | File | Description |
|---|---|---|
| PDF Parser | `pipeline/pdf_parser.py` | Extracts text + page numbers (PyMuPDF / pdfplumber) |
| Chunker | `pipeline/chunker.py` | Splits document into overlapping chunks |
| Extractor | `pipeline/llm_extractor.py` | Per-section Pydantic-validated extraction (8 calls per chunk) |
| Output Models | `pipeline/pydantic_models.py` | Pydantic models for structured, validated extraction output |
| IR Builder | `pipeline/ir_schema.py` | Converts validated output to typed Intermediate Representation |
| Validator | `pipeline/validator.py` | Validates coordinates, datetimes, units, required fields |
| Exporter | `pipeline/exporter.py` | Writes all BETYdb-compatible CSV files |

---

## Setup

### 1. Clone / unzip the project

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Set your API key (available free of cost at aistudio.google.com)

---

## Running the pipeline

### Process a real PDF

```bash
python main.py --pdf examples/sample_paper.pdf
```

### Replay from cached extraction (no API call)

If you have already run the pipeline once, a `outputs/raw_extraction.json` file is saved. You can re-run the IR -> Validation -> Export steps without calling the API:

```bash
python main.py --pdf examples/sample_paper.pdf --use-cache
```

### All CLI options

```
python main.py --help

  --pdf PATH          Path to input PDF file.  [required]
  --output-dir PATH   Override output directory.
  --chunk-size INT    Characters per chunk (default: 3000).
  --overlap INT       Chunk overlap characters (default: 300).
  --use-cache         Load cached raw_extraction.json instead of running extraction. (alias: --skip-llm)
  --verbose           Enable DEBUG logging.
```

---

## Output files

All CSV files are written to `outputs/`:

| File | Description |
|---|---|
| `traits_long.csv` | One row per (trait, cultivar, site, date) - BETYdb long format |
| `traits_wide.csv` | Pivoted - one row per (crop, cultivar, site, date), traits as columns |
| `sites.csv` | Site locations with WKT geometry, elevation, soil texture |
| `cultivars.csv` | Genotype / variety names and notes |
| `species.csv` | Crop species list |
| `variables.csv` | Trait variable definitions with units |
| `methods.csv` | Measurement method descriptions |
| `treatments.csv` | Experimental treatment descriptions |
| `management_events.csv` | Planting, fertilization, harvest events with dates |

---

## Provenance tracking

Every extracted value carries:

- `source_text` - the exact sentence(s) from the paper
- `page_number` - where it was found
- `confidence` - certainty score (0.0-1.0)
- `status` - `extracted` | `inferred` | `unresolved`

These appear as extra columns in `traits_long.csv` so scientists can verify every extraction.

---

## Intermediate Representation (IR)

All data passes through the IR schema before export. The IR is a set of Python dataclasses in `pipeline/ir_schema.py`. Each field is wrapped in an `IRField` carrying value + provenance metadata.

The raw extraction output is also saved as `outputs/raw_extraction.json` for inspection and replay.

---

## Configuration

Edit `config.py` to change:

- `LLM_MODEL` - model name (default: gemini-2.5-flash)
- `CHUNK_SIZE` / `CHUNK_OVERLAP` - chunking parameters
- `MIN_CONFIDENCE` - warning threshold for low-confidence extractions
- `CSV_FILES` - output file paths

---

## Project structure

```
Project-Directory/
+-- main.py                   - CLI entry point
+-- config.py                 - Configuration
+-- requirements.txt
+-- pipeline/
|   +-- pdf_parser.py         - Module 1: PDF text extraction
|   +-- chunker.py            - Module 2: Document chunking
|   +-- pydantic_models.py    - Module 3a: Pydantic output models
|   +-- llm_extractor.py      - Module 3b: Per-section extraction
|   +-- ir_schema.py          - Module 4: Intermediate representation
|   +-- validator.py          - Module 5: Validation layer
|   +-- exporter.py           - Module 6: BETYdb CSV export
+-- examples/
|   +-- sample_paper.pdf      - Example input paper
+-- outputs/
    +-- raw_extraction.json   - Cached extraction output (auto-generated)
    +-- traits_long.csv
    +-- traits_wide.csv
    +-- sites.csv
    +-- cultivars.csv
    +-- species.csv
    +-- variables.csv
    +-- methods.csv
    +-- treatments.csv
    +-- management_events.csv
```
