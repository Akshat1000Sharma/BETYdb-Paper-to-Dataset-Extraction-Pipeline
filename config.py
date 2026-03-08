import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Directories
BASE_DIR    = Path(__file__).parent
PROMPT_DIR  = BASE_DIR / "prompts"
OUTPUT_DIR  = BASE_DIR / "outputs"
EXAMPLE_DIR = BASE_DIR / "examples"

OUTPUT_DIR.mkdir(exist_ok=True)

# Extraction model settings
LLM_MODEL       = "gemini-2.5-flash"
LLM_MAX_TOKENS  = 16384
LLM_TEMPERATURE = 0.0

# Chunking
CHUNK_SIZE    = 3000
CHUNK_OVERLAP = 300

# Validation thresholds
MIN_CONFIDENCE = 0.5
LAT_RANGE      = (-90.0, 90.0)
LON_RANGE      = (-180.0, 180.0)

# CSV filenames
CSV_FILES = {
    "traits_long":       OUTPUT_DIR / "traits_long.csv",
    "traits_wide":       OUTPUT_DIR / "traits_wide.csv",
    "sites":             OUTPUT_DIR / "sites.csv",
    "cultivars":         OUTPUT_DIR / "cultivars.csv",
    "species":           OUTPUT_DIR / "species.csv",
    "variables":         OUTPUT_DIR / "variables.csv",
    "methods":           OUTPUT_DIR / "methods.csv",
    "treatments":        OUTPUT_DIR / "treatments.csv",
    "management_events": OUTPUT_DIR / "management_events.csv",
}


# API key
def get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "API key not set. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.\n"
            "Example: export GEMINI_API_KEY=your_key_here"
        )
    return key
