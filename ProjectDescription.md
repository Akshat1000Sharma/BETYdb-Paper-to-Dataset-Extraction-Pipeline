# BETYdb Paper-to-Dataset Extraction Pipeline

A command-line pipeline that reads a scientific agronomic or ecological research paper (PDF), extracts all experimental data using a structured extraction model, and exports CSV tables ready to upload into [BETYdb](https://www.betydb.org/) — the Biofuel Ecophysiological Traits and Yields database.

---

## Purpose

Researchers who contribute data to BETYdb currently read papers manually and fill in a multi-sheet spreadsheet to upload trait data. This process is slow, error-prone, and does not scale to the thousands of papers that exist in the literature.

This pipeline automates the entire workflow:

1. A researcher drops a PDF into the `examples/` folder.
2. The pipeline extracts and structures all experimental data.
3. Nine BETYdb-compatible CSV files are written to `outputs/`, ready to review and upload.

Every extracted value retains its source sentence, page number, and a confidence score so researchers can verify or correct the output before upload.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        BETYdb Extraction Pipeline                       │
│                                                                         │
│  ┌──────────┐    ┌──────────┐    ┌─────────────────┐    ┌───────────┐  │
│  │  PDF     │    │ Document │    │   LLM Extraction │    │  IR       │  │
│  │  Parser  │───>│ Chunker  │───>│   Agent          │───>│  Builder  │  │
│  │          │    │          │    │ (Google Gemini)  │    │           │  │
│  │ Module 1 │    │ Module 2 │    │    Module 3      │    │ Module 4  │  │
│  └──────────┘    └──────────┘    └─────────────────┘    └─────┬─────┘  │
│  pdfplumber /                    LangChain LCEL pipe           │        │
│  PyMuPDF                         ChatPromptTemplate            │        │
│                                  + MessagesPlaceholder         │        │
│                                                          ┌─────▼─────┐  │
│                                                          │ Validation│  │
│                                                          │   Layer   │  │
│                                                          │ Module 5  │  │
│                                                          └─────┬─────┘  │
│                                                                │        │
│  ┌──────────────────────────────────────────────────────┐       │        │
│  │                   BETYdb Exporter  (Module 6)        │<────┘        │
│  │                                                      │              │
│  │  traits_long.csv   traits_wide.csv   sites.csv       │              │
│  │  cultivars.csv     species.csv       variables.csv   │              │
│  │  methods.csv       treatments.csv    management_     │              │
│  │                                      events.csv      │              │
│  └──────────────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────────┘

Data flow with provenance:
  Each extracted field carries: value | confidence | source_text | page_number | status
```

---

## How It Works - Module by Module

### Module 1 - PDF Parser (`pipeline/pdf_parser.py`)

Extracts the raw text from every page of the input PDF. Tries **PyMuPDF** (faster, better layout preservation) first and automatically falls back to **pdfplumber** if PyMuPDF is not installed. Returns a list of `PageContent` objects, each holding a page number and its text.

### Module 2 - Document Chunker (`pipeline/chunker.py`)

Large papers exceed a single context window. The chunker slices the full document text into overlapping windows of configurable size (default: 3,000 characters with 300-character overlap). Each `TextChunk` records which source page numbers it spans, preserving provenance through the pipeline.

### Module 3 - Extractor (`pipeline/llm_extractor.py` + `pipeline/pydantic_models.py`)

The core of the pipeline. For each chunk, it makes **8 separate API calls** — one per entity section (sites, species, cultivars, traits, variables, methods, treatments, management events). Each call uses a `PydanticOutputParser` to validate the response against a typed schema:

```
PromptTemplate (section-specific instructions + format_instructions)
    +
chunk text
    |
    v
ChatGoogleGenerativeAI (gemini-2.5-flash)
    |
    v
PydanticOutputParser -> validated Pydantic model -> dict
```

This section-by-section approach gives the model a tightly focused task per call, produces validated and type-checked output, and isolates failures — if one section fails, the others still succeed.

`pipeline/pydantic_models.py` defines the Pydantic models for each entity type and the `SECTION_REGISTRY` that maps section keys to their models.

Per-chunk results are merged and deduplicated into a single extraction dict, which is saved as `outputs/raw_extraction.json` for inspection and replay.

### Module 4 - IR Builder (`pipeline/ir_schema.py`)

Converts the raw extraction dict into a fully typed **Intermediate Representation** using Python dataclasses. Every field is wrapped in an `IRField` that carries:

| Field | Description |
|---|---|
| `value` | The extracted value |
| `confidence` | Certainty score, 0.0 - 1.0 |
| `source_text` | Exact sentence(s) from the paper |
| `page_number` | Page where found |
| `status` | `extracted` / `inferred` / `unresolved` |

The IR is the single source of truth between extraction and export. It decouples the extraction format from the BETYdb schema.

### Module 5 - Validation Layer (`pipeline/validator.py`)

Validates the IR before export and returns typed `ValidationIssue` objects (ERROR or WARNING):

- **Required fields** - sitename, trait name, mean value, variable units, method name
- **Coordinate ranges** - latitude -90/+90, longitude -180/+180
- **Datetime format** - parseable by `python-dateutil`
- **Numeric values** - mean and stat must be floats
- **Soil texture** - sand + silt + clay should sum to ~100%
- **Cross-table consistency** - trait names should appear in the variables table
- **Low confidence** - any extracted field below the `MIN_CONFIDENCE` threshold

Errors are printed with entity path and page number. Export still runs even with errors so partial results are not lost.

### Module 6 - BETYdb Exporter (`pipeline/exporter.py`)

Reads the validated IR and writes nine CSV files matching the BETYdb bulk upload schema. The traits wide table is dynamically pivoted — trait names become column headers. The sites table generates WKT geometry (`POINT(lon lat)`) from extracted coordinates. All files include provenance columns (confidence, source_text, page_number, status) on trait rows.

---

## Project Structure

```
BETYdb-Paper-to-Dataset-Extraction-Pipeline/
|
+-- main.py                    - CLI entry point (argparse, 6-step orchestrator)
+-- config.py                  - All settings: model, chunking, paths, API key
+-- requirements.txt           - Python dependencies
+-- README.md
|
+-- pipeline/
|   +-- __init__.py
|   +-- pdf_parser.py          - Module 1: PDF text extraction
|   +-- chunker.py             - Module 2: Overlapping text chunking
|   +-- pydantic_models.py     - Module 3a: Pydantic output schema models
|   +-- llm_extractor.py       - Module 3b: Per-section extraction
|   +-- ir_schema.py           - Module 4: Intermediate representation dataclasses
|   +-- validator.py           - Module 5: Field-level validation
|   +-- exporter.py            - Module 6: BETYdb CSV generation
|
+-- examples/
|   +-- sample_paper.pdf       - Example input: maize nitrogen trial paper
|
+-- outputs/                   - Auto-created; all generated files go here
    +-- raw_extraction.json    - Cached extraction output (auto-saved, used by --use-cache)
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

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-org/BETYdb-Paper-to-Dataset-Extraction-Pipeline.git
cd BETYdb-Paper-to-Dataset-Extraction-Pipeline
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

**Core dependencies:**

| Package | Purpose |
|---|---|
| `langchain` | Pipeline orchestration |
| `langchain-core` | Prompt templates, output parsers |
| `langchain-google-genai` | Google Gemini chat model |
| `pydantic` | Structured output validation |
| `python-dotenv` | Load API key from `.env` file |
| `pdfplumber` | PDF text extraction (fallback) |
| `pymupdf` | PDF text extraction (preferred, optional) |
| `python-dateutil` | Datetime validation |

### 4. Set your Google API key

**Option A - `.env` file (recommended):**

Create a file named `.env` in the project root:

```
GOOGLE_API_KEY=your-key-here
```

**Option B - environment variable:**

```bash
# Windows PowerShell
$env:GOOGLE_API_KEY = "your-key-here"

# macOS / Linux
export GOOGLE_API_KEY="your-key-here"
```

Get a free API key at [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).

---

## Running the Pipeline

### Process a PDF paper

```bash
python main.py --pdf examples/sample_paper.pdf
```

### Replay from cached extraction (no API call, no key needed)

After the first run, `outputs/raw_extraction.json` is saved. You can re-run all downstream steps (IR build -> validate -> export) without calling the API:

```bash
python main.py --pdf examples/sample_paper.pdf --use-cache
```

This is useful for:
- Testing the pipeline before obtaining an API key
- Re-running validation or export after manual edits to `raw_extraction.json`
- Faster iteration when tuning the exporter

### All CLI options

```
python main.py --help

  --pdf PATH          Path to input PDF file.               [required]
  --output-dir PATH   Override output directory.
  --chunk-size INT    Characters per chunk     (default: 3000)
  --overlap INT       Overlap between chunks   (default: 300)
  --use-cache         Load cached raw_extraction.json instead of running extraction. (alias: --skip-llm)
  --verbose           Enable DEBUG logging.
```

---

## Output Files

All outputs are written to `outputs/` (or `--output-dir` if specified):

| File | BETYdb Sheet | Description |
|---|---|---|
| `traits_long.csv` | Bulk Upload Long | One row per (trait, cultivar, site, date); includes method, n, SE/SD, units, and provenance columns |
| `traits_wide.csv` | Bulk Upload Wide | Same data pivoted; trait names become columns |
| `sites.csv` | Sites | Location with lat/lon, WKT geometry, elevation, soil texture (sand/silt/clay %) |
| `cultivars.csv` | Cultivars/Varieties | Genotype names and notes |
| `species.csv` | Species/Crops | Crop species list |
| `variables.csv` | Variables | Trait definitions with units and descriptions |
| `methods.csv` | Methods | Measurement method descriptions |
| `treatments.csv` | Treatments | Experimental treatment descriptions |
| `management_events.csv` | Managements/Events | Planting, fertilization, harvest events with ISO dates |
| `raw_extraction.json` | (internal) | Full extraction output with confidence scores - saved for replay and audit |

**Provenance columns on `traits_long.csv`:**

| Column | Description |
|---|---|
| `confidence` | Certainty score for this trait extraction (0.0-1.0) |
| `source_text` | The exact sentence(s) from the paper that justified the value |
| `page_number` | Page where the value was found |
| `status` | `extracted` / `inferred` / `unresolved` |

---

## Configuration

All settings are in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `LLM_MODEL` | `gemini-2.5-flash` | Google Gemini model name |
| `LLM_TEMPERATURE` | `0.0` | Deterministic output for extraction |
| `LLM_MAX_TOKENS` | `16384` | Maximum response length |
| `CHUNK_SIZE` | `3000` | Characters per document chunk |
| `CHUNK_OVERLAP` | `300` | Overlap between consecutive chunks |
| `MIN_CONFIDENCE` | `0.5` | Warn on extractions below this score |
| `LAT_RANGE` | `(-90, 90)` | Valid latitude range |
| `LON_RANGE` | `(-180, 180)` | Valid longitude range |

---

## BETYdb Field Mappings

| Pipeline field | BETYdb table | BETYdb column |
|---|---|---|
| `sitename` | `sites` | `name` |
| `latitude` / `longitude` | `sites` | `geometry` (WKT `POINT`) |
| `crop` | `species` | `name` |
| `cultivar` | `cultivars` | `name` |
| `trait` | `traits` | `variable_id` |
| `mean` | `traits` | `mean` |
| `datetime` | `traits` | `date` |
| `method` | `methods` | `name` |
| `statname` / `stat` | `traits` | `statname` / `stat` |

---

## Known Limitations

- **Tables and figures**: The extractor reads text only. Data embedded solely in images or complex tables may not be captured.
- **API call volume**: Each chunk produces 8 API calls (one per entity section). Extraction time scales with both paper length and number of sections.
- **Unit normalisation**: Units are extracted as-written (e.g. `Mg ha-1`, `t/ha`). Manual review is recommended before upload to ensure BETYdb unit consistency.
- **Multi-site papers**: The pipeline extracts all sites mentioned; cross-referencing which trait measurement belongs to which site depends on the clarity of the paper's text.
