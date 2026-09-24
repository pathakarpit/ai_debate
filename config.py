from pathlib import Path


# ============================================================
# PROJECT
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

STATE_FILE = BASE_DIR / "debate_state.json"

TRANSCRIPT_FILE = BASE_DIR / "transcript.txt"

MEMORY_DIR = BASE_DIR / "memory"

CURRENT_MEMORY_FILE = MEMORY_DIR / "current_memory.txt"

ARGUMENT_LEDGER_FILE = MEMORY_DIR / "argument_ledger.json"

LOG_DIR = BASE_DIR / "logs"

LOG_FILE = LOG_DIR / "debate.log"

SUMMARY_FILE_TEMPLATE = "summary_{:03d}.txt"

CHECKPOINT_FILE_TEMPLATE = "checkpoint_{:03d}.json"


# ============================================================
# DEBATE
# ============================================================

TOPIC = "Capitalism is needed for a fair world"

CENTRAL_QUESTION = (
    "Is capitalism necessary for achieving a fair world, "
    "and if so, under what conditions?"
)


# ============================================================
# SPEAKER 1
# ============================================================

SPEAKER_1_NAME = "Speaker 1"

SPEAKER_1_MODEL = "qwen3:8b"

SPEAKER_1_POSITION = "FOR"


# ============================================================
# SPEAKER 2
# ============================================================

SPEAKER_2_NAME = "Speaker 2"

SPEAKER_2_MODEL = "llama3.1:latest"

SPEAKER_2_POSITION = "AGAINST"


# ============================================================
# NEUTRAL ANALYST
# ============================================================

MEMORY_MODEL = "deepseek-coder-v2:latest"


# ============================================================
# ROUND CONTROL
# ============================================================

# Total number of completed rounds desired.

MAX_ROUNDS = 10


# ============================================================
# CONTEXT MANAGEMENT
# ============================================================

# Number of recent speaker turns included in each
# speaker's generation prompt.

RECENT_EXCHANGES = 8


# Maximum number of arguments from each side included
# in the prompt.

MAX_LEDGER_ARGUMENTS_IN_PROMPT = 30


# Maximum unresolved questions included in prompt.

MAX_OPEN_QUESTIONS_IN_PROMPT = 15


# ============================================================
# MEMORY / ANALYSIS
# ============================================================

# Run the neutral analyst every N completed rounds.

MEMORY_UPDATE_INTERVAL = 5


# Create a human-readable snapshot every N memory updates.

SUMMARY_INTERVAL = 1


# Create a complete machine-readable checkpoint every N rounds.

CHECKPOINT_INTERVAL = 10


# ============================================================
# MODEL GENERATION
# ============================================================

# Debate temperature.

TEMPERATURE = 0.65


# Neutral analyst temperature.

MEMORY_TEMPERATURE = 0.25


# Maximum generated tokens for each debate response.

NUM_PREDICT = 900


# Maximum generated tokens for the neutral analyst.

MEMORY_NUM_PREDICT = 1600


# ============================================================
# OLLAMA
# ============================================================

OLLAMA_HOST = "http://100.75.129.88:11434"

OLLAMA_CHAT_URL = (
    f"{OLLAMA_HOST}/api/chat"
)

OLLAMA_PS_URL = (
    f"{OLLAMA_HOST}/api/ps"
)


# ============================================================
# MODEL LIFECYCLE / VRAM
# ============================================================

# IMPORTANT:
#
# 0 means Ollama should unload the model immediately
# after the request.
#
# This is intentional because the machine has 16 GB VRAM.

OLLAMA_KEEP_ALIVE = 0


# Delay after unload request.

MODEL_UNLOAD_DELAY = 1.5


# Verify /api/ps after unloading.

VERIFY_MODEL_UNLOAD = True


# ============================================================
# NETWORK
# ============================================================

# Maximum time allowed for one Ollama request.

REQUEST_TIMEOUT = 900


# Number of retries.

MAX_RETRIES = 3


# Delay between retries.

RETRY_DELAY = 5


# ============================================================
# OUTPUT
# ============================================================

SHOW_RESPONSES = True

SHOW_ANALYST_OUTPUT = True


# ============================================================
# LOGGING
# ============================================================

ENABLE_LOGGING = True

LOG_LEVEL = "INFO"