import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import requests

import config


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("ai_debate")


def setup_logging():
    if not config.ENABLE_LOGGING:
        return

    config.LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if logger.handlers:
        return

    logger.setLevel(
        getattr(
            logging,
            "LOG_LEVEL",
            "INFO",
        )
    )

    handler = logging.FileHandler(
        config.LOG_FILE,
        encoding="utf-8",
    )

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
    )

    logger.addHandler(handler)


# ============================================================
# FILE UTILITIES
# ============================================================

def atomic_write_text(
    path,
    text,
):
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = path.with_name(
        path.name + ".tmp"
    )

    with open(
        temp_path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(text)
        file.flush()

    temp_path.replace(path)


def atomic_write_json(
    path,
    data,
):
    atomic_write_text(
        path,
        json.dumps(
            data,
            indent=4,
            ensure_ascii=False,
        ) + "\n",
    )


def utc_now():
    return datetime.now().isoformat()


# ============================================================
# DIRECTORIES
# ============================================================

def initialize_directories():
    config.MEMORY_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    config.LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# STATE
# ============================================================

def default_state():
    now = utc_now()

    return {
        "topic": config.TOPIC,

        "central_question": config.CENTRAL_QUESTION,

        "round": 0,

        "current_speaker": None,

        "round_status": "idle",

        "speaker_1": {
            "name": config.SPEAKER_1_NAME,
            "model": config.SPEAKER_1_MODEL,
            "position": config.SPEAKER_1_POSITION,
            "responses": 0,
        },

        "speaker_2": {
            "name": config.SPEAKER_2_NAME,
            "model": config.SPEAKER_2_MODEL,
            "position": config.SPEAKER_2_POSITION,
            "responses": 0,
        },

        "memory": {
            "version": 0,
            "last_updated_round": 0,
        },

        "statistics": {
            "total_model_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,

            "speaker_1_calls": 0,
            "speaker_2_calls": 0,
            "memory_calls": 0,

            "successful_memory_updates": 0,
            "failed_memory_updates": 0,
        },

        "started_at": now,

        "last_updated": now,
    }


def merge_missing(
    target,
    defaults,
):
    for key, value in defaults.items():

        if key not in target:

            target[key] = value

        elif (
            isinstance(value, dict)
            and isinstance(target[key], dict)
        ):

            merge_missing(
                target[key],
                value,
            )


def save_state(
    state,
):
    state["last_updated"] = utc_now()

    atomic_write_json(
        config.STATE_FILE,
        state,
    )


def load_state():
    if not config.STATE_FILE.exists():

        state = default_state()

        save_state(
            state
        )

        logger.info(
            "Created new debate state."
        )

        return state

    try:

        raw = config.STATE_FILE.read_text(
            encoding="utf-8"
        ).strip()

        if not raw:

            raise ValueError(
                "state file is empty"
            )

        state = json.loads(
            raw
        )

        if not isinstance(
            state,
            dict,
        ):

            raise ValueError(
                "state root must be an object"
            )

        merge_missing(
            state,
            default_state(),
        )

        save_state(
            state
        )

        logger.info(
            "Loaded state: round=%s status=%s",
            state["round"],
            state["round_status"],
        )

        return state

    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:

        logger.error(
            "Could not load debate state: %s",
            exc,
        )

        backup = config.STATE_FILE.with_name(
            config.STATE_FILE.name
            + ".corrupt"
        )

        try:

            config.STATE_FILE.replace(
                backup
            )

            logger.warning(
                "Corrupt state backed up to %s",
                backup,
            )

        except OSError as backup_exc:

            logger.warning(
                "Could not backup corrupt state: %s",
                backup_exc,
            )

        state = default_state()

        save_state(
            state
        )

        logger.info(
            "Created fresh debate state."
        )

        return state


# ============================================================
# TRANSCRIPT
# ============================================================

def initialize_transcript():
    if config.TRANSCRIPT_FILE.exists():
        return

    content = (
        "=" * 80
        + "\n"
        + "AUTONOMOUS AI DEBATE — ITERATION 7\n"
        + "=" * 80
        + "\n\n"
        + f"Topic: {config.TOPIC}\n\n"
        + f"Central Question: "
        f"{config.CENTRAL_QUESTION}\n\n"
        + f"Speaker 1: "
        f"{config.SPEAKER_1_POSITION}\n"
        + f"Model: "
        f"{config.SPEAKER_1_MODEL}\n\n"
        + f"Speaker 2: "
        f"{config.SPEAKER_2_POSITION}\n"
        + f"Model: "
        f"{config.SPEAKER_2_MODEL}\n\n"
        + f"Neutral Analyst: "
        f"{config.MEMORY_MODEL}\n\n"
        + "=" * 80
        + "\n\n"
        + f"Debate started: "
        f"{utc_now()}\n\n"
    )

    atomic_write_text(
        config.TRANSCRIPT_FILE,
        content,
    )

    logger.info(
        "Created new transcript."
    )


def append_transcript(
    round_number,
    speaker_number,
    model,
    content,
):
    with open(
        config.TRANSCRIPT_FILE,
        "a",
        encoding="utf-8",
    ) as file:

        file.write(
            "\n"
            + "-" * 80
            + "\n"
        )

        file.write(
            f"ROUND {round_number} — "
            f"Speaker {speaker_number}\n"
        )

        file.write(
            "-" * 80
            + "\n\n"
        )

        file.write(
            f"speaker {speaker_number}: "
            f"{content.strip()}\n\n"
        )

        file.write(
            f"[model: {model}]\n"
        )

        file.write(
            f"[timestamp: {utc_now()}]\n\n"
        )


def load_transcript():
    if not config.TRANSCRIPT_FILE.exists():
        return ""

    try:

        return config.TRANSCRIPT_FILE.read_text(
            encoding="utf-8"
        )

    except OSError as exc:

        logger.error(
            "Could not read transcript: %s",
            exc,
        )

        return ""


# ============================================================
# RECENT CONTEXT
# ============================================================

def extract_round_sections(
    transcript,
):
    if not transcript:
        return []

    matches = list(
        re.finditer(
            r"(?m)^ROUND \d+ — Speaker \d+.*$",
            transcript,
        )
    )

    sections = []

    for index, match in enumerate(matches):

        if index + 1 < len(matches):

            end = matches[
                index + 1
            ].start()

        else:

            end = len(transcript)

        sections.append(
            transcript[
                match.start():end
            ].strip()
        )

    return sections


def load_recent_exchanges():
    transcript = load_transcript()

    sections = extract_round_sections(
        transcript
    )

    if not sections:
        return "(No previous debate turns.)"

    recent = sections[
        -config.RECENT_EXCHANGES:
    ]

    return (
        "\n\n"
        + (
            "\n\n"
            + "-" * 70
            + "\n\n"
        ).join(
            recent
        )
    )


# ============================================================
# ARGUMENT LEDGER
# ============================================================

def default_ledger():
    return {
        "topic": config.TOPIC,

        "central_question": config.CENTRAL_QUESTION,

        "next_argument_number": {
            "speaker_1": 1,
            "speaker_2": 1,
        },

        "speaker_1_arguments": [],

        "speaker_2_arguments": [],

        "rebuttals": [],

        "concessions": [],

        "unresolved_questions": [],

        "evidence_claims": [],

        "topic_drift": [],

        "important_distinctions": [],

        "analyst_notes": [],

        "last_analyzed_round": 0,
    }


def initialize_ledger():
    if config.ARGUMENT_LEDGER_FILE.exists():
        return

    ledger = default_ledger()

    atomic_write_json(
        config.ARGUMENT_LEDGER_FILE,
        ledger,
    )

    logger.info(
        "Created argument ledger."
    )


def load_ledger():
    initialize_ledger()

    try:

        raw = (
            config.ARGUMENT_LEDGER_FILE
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

        if not raw:
            raise ValueError(
                "argument ledger is empty"
            )

        ledger = json.loads(
            raw
        )

        if not isinstance(
            ledger,
            dict,
        ):

            raise ValueError(
                "argument ledger must be an object"
            )

        merge_missing(
            ledger,
            default_ledger(),
        )

        return ledger

    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:

        logger.error(
            "Could not load argument ledger: %s",
            exc,
        )

        backup = config.ARGUMENT_LEDGER_FILE.with_name(
            config.ARGUMENT_LEDGER_FILE.name
            + ".corrupt"
        )

        try:

            config.ARGUMENT_LEDGER_FILE.replace(
                backup
            )

        except OSError:
            pass

        ledger = default_ledger()

        atomic_write_json(
            config.ARGUMENT_LEDGER_FILE,
            ledger,
        )

        return ledger


def save_ledger(
    ledger,
):
    atomic_write_json(
        config.ARGUMENT_LEDGER_FILE,
        ledger,
    )


# ============================================================
# MEMORY TEXT
# ============================================================

def initialize_memory():
    if config.CURRENT_MEMORY_FILE.exists():
        return

    content = f"""# LONG-TERM DEBATE MEMORY

## TOPIC

{config.TOPIC}

## CENTRAL QUESTION

{config.CENTRAL_QUESTION}

## SYSTEM STATUS

No analytical memory has been created yet.

The authoritative machine-readable debate memory is:

{config.ARGUMENT_LEDGER_FILE}
"""

    atomic_write_text(
        config.CURRENT_MEMORY_FILE,
        content,
    )


def generate_human_memory(
    ledger,
):
    lines = []

    lines.append(
        "# LONG-TERM DEBATE MEMORY"
    )

    lines.append("")

    lines.append(
        "## TOPIC"
    )

    lines.append(
        ledger["topic"]
    )

    lines.append("")

    lines.append(
        "## CENTRAL QUESTION"
    )

    lines.append(
        ledger["central_question"]
    )

    lines.append("")

    lines.append(
        "## SPEAKER 1 — FOR"
    )

    for argument in ledger[
        "speaker_1_arguments"
    ][
        -20:
    ]:

        lines.append(
            f"- {argument.get('id')}: "
            f"{argument.get('claim')}"
        )

        lines.append(
            f"  Status: "
            f"{argument.get('status')}"
        )

    lines.append("")

    lines.append(
        "## SPEAKER 2 — AGAINST"
    )

    for argument in ledger[
        "speaker_2_arguments"
    ][
        -20:
    ]:

        lines.append(
            f"- {argument.get('id')}: "
            f"{argument.get('claim')}"
        )

        lines.append(
            f"  Status: "
            f"{argument.get('status')}"
        )

    lines.append("")

    lines.append(
        "## MAJOR REBUTTALS"
    )

    for rebuttal in ledger[
        "rebuttals"
    ][
        -20:
    ]:

        lines.append(
            "- "
            + rebuttal.get(
                "description",
                "",
            )
        )

    lines.append("")

    lines.append(
        "## CONCESSIONS"
    )

    for concession in ledger[
        "concessions"
    ][
        -20:
    ]:

        lines.append(
            "- "
            + concession.get(
                "description",
                "",
            )
        )

    lines.append("")

    lines.append(
        "## UNRESOLVED QUESTIONS"
    )

    for question in ledger[
        "unresolved_questions"
    ][
        -20:
    ]:

        lines.append(
            "- "
            + question.get(
                "question",
                "",
            )
        )

    lines.append("")

    lines.append(
        "## EVIDENCE STATUS"
    )

    for evidence in ledger[
        "evidence_claims"
    ][
        -20:
    ]:

        lines.append(
            "- "
            + evidence.get(
                "claim",
                "",
            )
            + " | Status: "
            + evidence.get(
                "status",
                "unknown",
            )
        )

    lines.append("")

    lines.append(
        "## IMPORTANT DISTINCTIONS"
    )

    for distinction in ledger[
        "important_distinctions"
    ][
        -20:
    ]:

        lines.append(
            "- "
            + distinction.get(
                "distinction",
                "",
            )
        )

    lines.append("")

    lines.append(
        "## TOPIC DRIFT"
    )

    for drift in ledger[
        "topic_drift"
    ][
        -20:
    ]:

        lines.append(
            "- "
            + drift.get(
                "description",
                "",
            )
        )

    lines.append("")

    return "\n".join(
        lines
    )


def save_human_memory(
    ledger,
):
    memory = generate_human_memory(
        ledger
    )

    atomic_write_text(
        config.CURRENT_MEMORY_FILE,
        memory,
    )


# ============================================================
# OLLAMA
# ============================================================

def check_ollama():
    try:

        response = requests.get(
            config.OLLAMA_PS_URL,
            timeout=10,
        )

        response.raise_for_status()

        return True

    except requests.RequestException as exc:

        logger.error(
            "Ollama connection failed: %s",
            exc,
        )

        return False


def get_loaded_models():
    try:

        response = requests.get(
            config.OLLAMA_PS_URL,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        return [
            model.get("name")
            for model in data.get(
                "models",
                [],
            )
            if model.get("name")
        ]

    except (
        requests.RequestException,
        ValueError,
        json.JSONDecodeError,
    ) as exc:

        logger.warning(
            "Could not query Ollama loaded models: %s",
            exc,
        )

        return []


def unload_model(
    model,
):
    logger.info(
        "Attempting to unload model: %s",
        model,
    )

    payload = {
        "model": model,
        "messages": [],
        "stream": False,
        "keep_alive": 0,
    }

    try:

        response = requests.post(
            config.OLLAMA_CHAT_URL,
            json=payload,
            timeout=30,
        )

        if response.status_code >= 400:

            logger.warning(
                "Unload request returned HTTP %s",
                response.status_code,
            )

    except requests.RequestException as exc:

        logger.warning(
            "Unload request failed for %s: %s",
            model,
            exc,
        )

    time.sleep(
        config.MODEL_UNLOAD_DELAY
    )

    if not config.VERIFY_MODEL_UNLOAD:

        return True

    loaded = get_loaded_models()

    if model in loaded:

        logger.warning(
            "Model still appears loaded: %s",
            model,
        )

        return False

    logger.info(
        "Verified model unloaded: %s",
        model,
    )

    return True


def unload_all_models():
    loaded = get_loaded_models()

    for model in loaded:

        unload_model(
            model
        )


# ============================================================
# MODEL CALL
# ============================================================

def generate_response(
    model,
    system_prompt,
    user_prompt,
    state,
    call_type="debate",
    temperature=None,
    num_predict=None,
):
    if temperature is None:
        temperature = config.TEMPERATURE

    if num_predict is None:
        num_predict = config.NUM_PREDICT

    payload = {
        "model": model,

        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],

        "stream": False,

        "keep_alive": config.OLLAMA_KEEP_ALIVE,

        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }

    retries = max(
        1,
        config.MAX_RETRIES,
    )

    for attempt in range(
        1,
        retries + 1,
    ):

        state[
            "statistics"
        ][
            "total_model_calls"
        ] += 1

        if call_type == "speaker_1":
            state[
                "statistics"
            ][
                "speaker_1_calls"
            ] += 1

        elif call_type == "speaker_2":
            state[
                "statistics"
            ][
                "speaker_2_calls"
            ] += 1

        elif call_type == "memory":
            state[
                "statistics"
            ][
                "memory_calls"
            ] += 1

        save_state(
            state
        )

        logger.info(
            "Calling %s (%s) "
            "attempt %s/%s",
            model,
            call_type,
            attempt,
            retries,
        )

        try:

            response = requests.post(
                config.OLLAMA_CHAT_URL,
                json=payload,
                timeout=config.REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            data = response.json()

            content = (
                data
                .get(
                    "message",
                    {},
                )
                .get(
                    "content",
                    "",
                )
                .strip()
            )

            if not content:

                raise ValueError(
                    "Ollama returned empty content"
                )

            state[
                "statistics"
            ][
                "successful_calls"
            ] += 1

            save_state(
                state
            )

            logger.info(
                "Successful response from %s "
                "(%d characters)",
                model,
                len(content),
            )

            return content

        except (
            requests.RequestException,
            ValueError,
            json.JSONDecodeError,
        ) as exc:

            state[
                "statistics"
            ][
                "failed_calls"
            ] += 1

            save_state(
                state
            )

            logger.error(
                "Model request failed: %s",
                exc,
            )

            if attempt < retries:

                time.sleep(
                    config.RETRY_DELAY
                )

    return None


# ============================================================
# SPEAKER PROMPTS
# ============================================================

def speaker_system_prompt(
    speaker_number,
):
    if speaker_number == 1:

        name = config.SPEAKER_1_NAME
        position = config.SPEAKER_1_POSITION

    else:

        name = config.SPEAKER_2_NAME
        position = config.SPEAKER_2_POSITION

    return f"""
You are {name} in a serious, continuous intellectual debate.

IMMUTABLE TOPIC:
{config.TOPIC}

IMMUTABLE CENTRAL QUESTION:
{config.CENTRAL_QUESTION}

YOUR POSITION:
{position}


============================================================
PRIMARY OBJECTIVE
============================================================

Advance your assigned position by making genuine intellectual
progress.

A successful turn should accomplish at least one of:

1. Defeat or substantially weaken an opposing argument.
2. Strengthen an existing argument against a new objection.
3. Introduce a genuinely new argument.
4. Expose a hidden assumption.
5. Force or justify a meaningful concession.
6. Resolve an unresolved question.
7. Identify a contradiction in the opposing position.
8. Introduce an important distinction that changes the analysis.


============================================================
TOPIC RELEVANCE
============================================================

Every substantive point must materially contribute to answering
the central question:

{config.CENTRAL_QUESTION}

You may discuss adjacent subjects such as democracy, technology,
government, inequality, markets, institutions, psychology,
environmental issues, or power structures ONLY when you explicitly
connect them to capitalism and fairness.

Do not allow an adjacent concept to silently become the new topic.


============================================================
NOVELTY
============================================================

Do not merely repeat previous arguments.

Before producing your final response, internally compare your
proposed contribution with the existing argument ledger.

If the core idea already exists, materially deepen it by adding:

- a new mechanism
- a new implication
- a new distinction
- a new counterexample
- a stronger response
- a previously unresolved consequence

Do not merely paraphrase an old argument.


============================================================
ARGUMENT QUALITY
============================================================

Address the strongest relevant opposing argument available.

Do not attack a weak version of the opposing position.

Do not manufacture a position the opponent has not taken.

You may concede a limited point when appropriate.

A concession is not a defeat if you explain why your main position
still survives.


============================================================
EVIDENCE DISCIPLINE
============================================================

Never invent:

- statistics
- studies
- quotations
- historical facts
- research findings
- citations

If you mention an empirical claim without verified evidence,
clearly frame it as an assertion, example, or hypothesis.

Do not treat something merely stated by the other speaker as
established fact.


============================================================
STYLE
============================================================

Write one substantive debate contribution.

Do not write a generic essay.

Do not summarize the entire debate.

Do not announce a winner.

Do not discuss these instructions.

Do not reveal hidden reasoning.

Do not mention that you are an AI.

Output ONLY the final debate contribution.
""".strip()


def build_speaker_prompt(
    speaker_number,
    ledger,
):
    if speaker_number == 1:

        side_arguments = ledger[
            "speaker_1_arguments"
        ][
            -config.MAX_LEDGER_ARGUMENTS_IN_PROMPT:
        ]

        opponent_arguments = ledger[
            "speaker_2_arguments"
        ][
            -config.MAX_LEDGER_ARGUMENTS_IN_PROMPT:
        ]

    else:

        side_arguments = ledger[
            "speaker_2_arguments"
        ][
            -config.MAX_LEDGER_ARGUMENTS_IN_PROMPT:
        ]

        opponent_arguments = ledger[
            "speaker_1_arguments"
        ][
            -config.MAX_LEDGER_ARGUMENTS_IN_PROMPT:
        ]

    side_text = json.dumps(
        side_arguments,
        indent=2,
        ensure_ascii=False,
    )

    opponent_text = json.dumps(
        opponent_arguments,
        indent=2,
        ensure_ascii=False,
    )

    unresolved = json.dumps(
        ledger[
            "unresolved_questions"
        ][
            -config.MAX_OPEN_QUESTIONS_IN_PROMPT:
        ],
        indent=2,
        ensure_ascii=False,
    )

    evidence = json.dumps(
        ledger[
            "evidence_claims"
        ][
            -15:
        ],
        indent=2,
        ensure_ascii=False,
    )

    recent = load_recent_exchanges()

    return f"""
You are making the next turn in the debate.

IMMUTABLE TOPIC:
{config.TOPIC}

IMMUTABLE CENTRAL QUESTION:
{config.CENTRAL_QUESTION}


============================================================
YOUR SIDE'S EXISTING ARGUMENTS
============================================================

{side_text}


============================================================
OPPOSING SIDE'S ARGUMENTS
============================================================

{opponent_text}


============================================================
UNRESOLVED QUESTIONS
============================================================

{unresolved}


============================================================
EVIDENCE STATUS
============================================================

{evidence}


============================================================
RECENT DEBATE
============================================================

{recent}


============================================================
YOUR TASK
============================================================

Produce the next substantive debate contribution.

Priority order:

1. Respond to the strongest relevant opposing argument.
2. Preserve your position.
3. Make intellectual progress.
4. Introduce something genuinely new OR materially deepen an
   unresolved issue.
5. Avoid repeating the core substance of your existing arguments.
6. Keep every argument anchored to the central question.

If you cannot introduce a completely new argument, select the most
important unresolved objection and deepen the existing argument
against it.

Do not discuss the ledger.

Do not output argument IDs.

Do not reveal internal reasoning.

Output ONLY the debate contribution.
""".strip()


# ============================================================
# ANALYST PROMPT
# ============================================================

def build_analyst_prompt(
    state,
    ledger,
):
    recent = load_recent_exchanges()

    return f"""
You are the NEUTRAL ANALYST of an ongoing intellectual debate.

You are NOT a debater.

You must NOT take either side.

Your job is to analyze the newest debate material and produce
STRUCTURED UPDATES to the persistent argument ledger.

IMMUTABLE TOPIC:
{config.TOPIC}

IMMUTABLE CENTRAL QUESTION:
{config.CENTRAL_QUESTION}


============================================================
EXISTING ARGUMENT LEDGER
============================================================

{json.dumps(
    ledger,
    indent=2,
    ensure_ascii=False,
)}


============================================================
NEWEST DEBATE MATERIAL
============================================================

{recent}


============================================================
CURRENT ROUND
============================================================

{state["round"]}


============================================================
ANALYSIS REQUIREMENTS
============================================================

Identify:

1. New substantive arguments.

2. Meaningful rebuttals.

3. Meaningful concessions.

4. Unresolved questions.

5. Important conceptual distinctions.

6. Important empirical/factual claims and their evidence status.

7. Topic drift.

8. Arguments that are substantially repetitive.

9. Arguments whose status changed because of the newest debate.


============================================================
ARGUMENT RULES
============================================================

An argument is NEW only when its core claim or reasoning is
meaningfully different from existing arguments.

Do not create duplicate argument entries simply because wording
changed.

Each new argument must receive a new ID.

Speaker 1 IDs:
S1-A01, S1-A02, ...

Speaker 2 IDs:
S2-A01, S2-A02, ...


============================================================
STATUS RULES
============================================================

Use only these statuses:

NEW
ACTIVE
CHALLENGED
PARTIALLY_DEFENDED
DEFENDED
CONCEDED
UNRESOLVED
SUPERSEDED


============================================================
EVIDENCE STATUS
============================================================

Use only:

SUPPORTED_WITHIN_DEBATE
ASSERTED_UNSUPPORTED
DISPUTED
ILLUSTRATIVE_EXAMPLE
UNKNOWN


IMPORTANT:

"Speaker X said that studies show Y"

does NOT mean Y is supported.

Record the claim as ASSERTED_UNSUPPORTED unless the debate itself
contains enough actual evidence to justify a stronger status.


============================================================
TOPIC DRIFT
============================================================

Flag an idea as topic drift when it becomes disconnected from:

"{config.TOPIC}"

However, an adjacent concept is NOT drift if it is explicitly
connected back to capitalism, fairness, or the central question.

For example:

"Algorithmic governance affects concentration of economic power
under capitalism."

This can be relevant.

But:

"Algorithmic governance is a superior political system."

is potentially off-topic unless connected back to the proposition.


============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

Use EXACTLY this structure:

{{
    "new_arguments": [],
    "rebuttals": [],
    "concessions": [],
    "unresolved_questions": [],
    "evidence_claims": [],
    "important_distinctions": [],
    "topic_drift": [],
    "argument_status_updates": [],
    "repetitive_arguments": [],
    "analyst_notes": []
}}

Do not wrap JSON in markdown.

Do not include commentary outside JSON.
""".strip()


# ============================================================
# ANALYST JSON EXTRACTION
# ============================================================

def extract_json_object(
    text,
):
    if not text:
        return None

    cleaned = text.strip()

    if cleaned.startswith(
        "```"
    ):

        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

    try:

        return json.loads(
            cleaned
        )

    except json.JSONDecodeError:
        pass

    start = cleaned.find(
        "{"
    )

    end = cleaned.rfind(
        "}"
    )

    if (
        start >= 0
        and end > start
    ):

        candidate = cleaned[
            start:end + 1
        ]

        try:

            return json.loads(
                candidate
            )

        except json.JSONDecodeError:
            return None

    return None


# ============================================================
# LEDGER MERGING
# ============================================================

def normalize_list(
    value,
):
    if isinstance(
        value,
        list,
    ):
        return value

    return []


def next_argument_id(
    ledger,
    speaker_number,
):
    key = (
        "speaker_1"
        if speaker_number == 1
        else "speaker_2"
    )

    number = ledger[
        "next_argument_number"
    ][
        key
    ]

    ledger[
        "next_argument_number"
    ][
        key
    ] = number + 1

    return (
        f"S{speaker_number}-A{number:02d}"
    )


def argument_is_duplicate(
    existing_arguments,
    candidate,
):
    candidate_claim = (
        candidate
        .get(
            "claim",
            "",
        )
        .strip()
        .lower()
    )

    if not candidate_claim:
        return True

    candidate_core = set(
        re.findall(
            r"\b[a-zA-Z]{4,}\b",
            candidate_claim,
        )
    )

    if not candidate_core:
        return True

    for existing in existing_arguments:

        existing_claim = (
            existing
            .get(
                "claim",
                "",
            )
            .strip()
            .lower()
        )

        existing_core = set(
            re.findall(
                r"\b[a-zA-Z]{4,}\b",
                existing_claim,
            )
        )

        if not existing_core:
            continue

        intersection = (
            candidate_core
            & existing_core
        )

        union = (
            candidate_core
            | existing_core
        )

        similarity = (
            len(intersection)
            / len(union)
        )

        if similarity >= 0.82:
            return True

    return False


def merge_argument(
    ledger,
    argument,
):
    speaker = argument.get(
        "speaker"
    )

    if speaker not in (
        1,
        2,
        "1",
        "2",
    ):
        return

    speaker = int(
        speaker
    )

    target_key = (
        "speaker_1_arguments"
        if speaker == 1
        else "speaker_2_arguments"
    )

    existing = ledger[
        target_key
    ]

    if argument_is_duplicate(
        existing,
        argument,
    ):

        logger.info(
            "Rejected duplicate argument."
        )

        return

    new_argument = {
        "id": next_argument_id(
            ledger,
            speaker,
        ),

        "round": argument.get(
            "round",
            ledger.get(
                "last_analyzed_round",
                0,
            ),
        ),

        "claim": argument.get(
            "claim",
            "",
        ).strip(),

        "reasoning": argument.get(
            "reasoning",
            "",
        ).strip(),

        "status": argument.get(
            "status",
            "NEW",
        ),

        "strongest_opponent_response":
            argument.get(
                "strongest_opponent_response",
                "",
            ).strip(),

        "remaining_issue":
            argument.get(
                "remaining_issue",
                "",
            ).strip(),

        "evidence_status":
            argument.get(
                "evidence_status",
                "UNKNOWN",
            ),

        "source_round": argument.get(
            "source_round",
            ledger.get(
                "last_analyzed_round",
                0,
            ),
        ),
    }

    existing.append(
        new_argument
    )

    logger.info(
        "Added argument %s",
        new_argument["id"],
    )


def merge_status_updates(
    ledger,
    updates,
):
    updates = normalize_list(
        updates
    )

    all_arguments = (
        ledger[
            "speaker_1_arguments"
        ]
        +
        ledger[
            "speaker_2_arguments"
        ]
    )

    by_id = {
        argument.get("id"): argument
        for argument in all_arguments
    }

    for update in updates:

        argument_id = update.get(
            "id"
        )

        if argument_id not in by_id:
            continue

        argument = by_id[
            argument_id
        ]

        if update.get(
            "status"
        ):

            argument[
                "status"
            ] = update[
                "status"
            ]

        if update.get(
            "strongest_opponent_response"
        ):

            argument[
                "strongest_opponent_response"
            ] = update[
                "strongest_opponent_response"
            ]

        if update.get(
            "remaining_issue"
        ):

            argument[
                "remaining_issue"
            ] = update[
                "remaining_issue"
            ]


def merge_analyst_result(
    ledger,
    result,
    round_number,
):
    if not isinstance(
        result,
        dict,
    ):

        raise ValueError(
            "Analyst result is not a JSON object"
        )

    for argument in normalize_list(
        result.get(
            "new_arguments"
        )
    ):

        argument[
            "round"
        ] = round_number

        merge_argument(
            ledger,
            argument,
        )

    merge_status_updates(
        ledger,
        result.get(
            "argument_status_updates"
        ),
    )

    for item in normalize_list(
        result.get(
            "rebuttals"
        )
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        ledger[
            "rebuttals"
        ].append(
            {
                "round": round_number,
                "description": item.get(
                    "description",
                    "",
                ),
                "attacker": item.get(
                    "attacker",
                    "",
                ),
                "target_argument": item.get(
                    "target_argument",
                    "",
                ),
            }
        )

    for item in normalize_list(
        result.get(
            "concessions"
        )
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        ledger[
            "concessions"
        ].append(
            {
                "round": round_number,
                "description": item.get(
                    "description",
                    "",
                ),
                "speaker": item.get(
                    "speaker",
                    "",
                ),
            }
        )

    for item in normalize_list(
        result.get(
            "unresolved_questions"
        )
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        question = item.get(
            "question",
            "",
        ).strip()

        if not question:
            continue

        existing_questions = [
            x.get(
                "question",
                "",
            ).strip().lower()
            for x in ledger[
                "unresolved_questions"
            ]
        ]

        if (
            question.lower()
            not in existing_questions
        ):

            ledger[
                "unresolved_questions"
            ].append(
                {
                    "round": round_number,
                    "question": question,
                    "importance": item.get(
                        "importance",
                        "medium",
                    ),
                }
            )

    for item in normalize_list(
        result.get(
            "evidence_claims"
        )
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        claim = item.get(
            "claim",
            "",
        ).strip()

        if not claim:
            continue

        ledger[
            "evidence_claims"
        ].append(
            {
                "round": round_number,
                "claim": claim,
                "speaker": item.get(
                    "speaker",
                    "",
                ),
                "status": item.get(
                    "status",
                    "UNKNOWN",
                ),
                "context": item.get(
                    "context",
                    "",
                ),
            }
        )

    for item in normalize_list(
        result.get(
            "important_distinctions"
        )
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        distinction = item.get(
            "distinction",
            "",
        ).strip()

        if not distinction:
            continue

        ledger[
            "important_distinctions"
        ].append(
            {
                "round": round_number,
                "distinction": distinction,
            }
        )

    for item in normalize_list(
        result.get(
            "topic_drift"
        )
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        description = item.get(
            "description",
            "",
        ).strip()

        if not description:
            continue

        ledger[
            "topic_drift"
        ].append(
            {
                "round": round_number,
                "description": description,
                "severity": item.get(
                    "severity",
                    "low",
                ),
                "recovery":
                    item.get(
                        "recovery",
                        "",
                    ),
            }
        )

    for item in normalize_list(
        result.get(
            "repetitive_arguments"
        )
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        ledger[
            "analyst_notes"
        ].append(
            {
                "round": round_number,
                "type": "repetition",
                "note": item.get(
                    "description",
                    "",
                ),
            }
        )

    for item in normalize_list(
        result.get(
            "analyst_notes"
        )
    ):

        if isinstance(
            item,
            dict,
        ):

            note = item.get(
                "note",
                "",
            )

        else:

            note = str(
                item
            )

        if note.strip():

            ledger[
                "analyst_notes"
            ].append(
                {
                    "round": round_number,
                    "type": "general",
                    "note": note.strip(),
                }
            )

    ledger[
        "last_analyzed_round"
    ] = round_number

    # Keep the machine-readable ledger bounded.

    ledger[
        "rebuttals"
    ] = ledger[
        "rebuttals"
    ][
        -100:
    ]

    ledger[
        "concessions"
    ] = ledger[
        "concessions"
    ][
        -100:
    ]

    ledger[
        "unresolved_questions"
    ] = ledger[
        "unresolved_questions"
    ][
        -50:
    ]

    ledger[
        "evidence_claims"
    ] = ledger[
        "evidence_claims"
    ][
        -100:
    ]

    ledger[
        "topic_drift"
    ] = ledger[
        "topic_drift"
    ][
        -50:
    ]

    ledger[
        "important_distinctions"
    ] = ledger[
        "important_distinctions"
    ][
        -50:
    ]

    ledger[
        "analyst_notes"
    ] = ledger[
        "analyst_notes"
    ][
        -100:
    ]


# ============================================================
# ANALYST EXECUTION
# ============================================================

def update_analytical_memory(
    state,
):
    logger.info(
        "Starting neutral analysis at round %s",
        state["round"],
    )

    ledger = load_ledger()

    prompt = build_analyst_prompt(
        state,
        ledger,
    )

    system_prompt = """
You are a neutral structured-data analyst.

Return valid JSON only.

Do not take sides.

Do not rewrite the historical record.

Do not invent facts.

Do not declare a winner.
""".strip()

    try:

        result_text = generate_response(
            model=config.MEMORY_MODEL,
            system_prompt=system_prompt,
            user_prompt=prompt,
            state=state,
            call_type="memory",
            temperature=config.MEMORY_TEMPERATURE,
            num_predict=config.MEMORY_NUM_PREDICT,
        )

        if not result_text:

            state[
                "statistics"
            ][
                "failed_memory_updates"
            ] += 1

            save_state(
                state
            )

            return False

        if config.SHOW_ANALYST_OUTPUT:

            print(
                "\n"
                + "=" * 80
            )

            print(
                "NEUTRAL ANALYST OUTPUT"
            )

            print(
                "=" * 80
            )

            print(
                result_text
            )

        result = extract_json_object(
            result_text
        )

        if result is None:

            logger.error(
                "Analyst returned invalid JSON."
            )

            state[
                "statistics"
            ][
                "failed_memory_updates"
            ] += 1

            save_state(
                state
            )

            return False

        merge_analyst_result(
            ledger,
            result,
            state["round"],
        )

        save_ledger(
            ledger
        )

        save_human_memory(
            ledger
        )

        state[
            "memory"
        ][
            "version"
        ] += 1

        state[
            "memory"
        ][
            "last_updated_round"
        ] = state["round"]

        state[
            "statistics"
        ][
            "successful_memory_updates"
        ] += 1

        save_state(
            state
        )

        save_memory_snapshot(
            state,
            ledger,
        )

        logger.info(
            "Neutral analysis completed. "
            "Memory version=%s",
            state[
                "memory"
            ][
                "version"
            ],
        )

        return True

    finally:

        unload_model(
            config.MEMORY_MODEL
        )


def save_memory_snapshot(
    state,
    ledger,
):
    version = state[
        "memory"
    ][
        "version"
    ]

    filename = (
        config.SUMMARY_FILE_TEMPLATE
        .format(
            version
        )
    )

    path = (
        config.MEMORY_DIR
        / filename
    )

    snapshot = {
        "created_at": utc_now(),

        "round": state[
            "round"
        ],

        "memory_version": version,

        "topic": config.TOPIC,

        "central_question":
            config.CENTRAL_QUESTION,

        "ledger": ledger,
    }

    atomic_write_json(
        path,
        snapshot,
    )

    logger.info(
        "Saved memory snapshot: %s",
        path,
    )


# ============================================================
# SPEAKER TURN
# ============================================================

def run_speaker_turn(
    state,
    speaker_number,
):
    if speaker_number == 1:

        model = config.SPEAKER_1_MODEL

    else:

        model = config.SPEAKER_2_MODEL

    ledger = load_ledger()

    system_prompt = speaker_system_prompt(
        speaker_number
    )

    user_prompt = build_speaker_prompt(
        speaker_number,
        ledger,
    )

    state[
        "current_speaker"
    ] = speaker_number

    state[
        "round_status"
    ] = (
        f"speaker_{speaker_number}_thinking"
    )

    save_state(
        state
    )

    try:

        response = generate_response(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            state=state,
            call_type=(
                "speaker_1"
                if speaker_number == 1
                else "speaker_2"
            ),
            temperature=config.TEMPERATURE,
            num_predict=config.NUM_PREDICT,
        )

        if not response:

            state[
                "round_status"
            ] = (
                f"speaker_{speaker_number}_failed"
            )

            save_state(
                state
            )

            return False

        append_transcript(
            round_number=state["round"],
            speaker_number=speaker_number,
            model=model,
            content=response,
        )

        state[
            f"speaker_{speaker_number}"
        ][
            "responses"
        ] += 1

        state[
            "round_status"
        ] = (
            f"speaker_{speaker_number}_complete"
        )

        save_state(
            state
        )

        if config.SHOW_RESPONSES:

            print(
                "\n"
                + "-" * 80
            )

            print(
                f"ROUND {state['round']} "
                f"— SPEAKER {speaker_number}"
            )

            print(
                "-" * 80
            )

            print(
                response
            )

        return True

    finally:

        unload_model(
            model
        )


# ============================================================
# CHECKPOINT
# ============================================================

def create_checkpoint(
    state,
):
    checkpoint_number = (
        state["round"]
        // config.CHECKPOINT_INTERVAL
    )

    filename = (
        config.CHECKPOINT_FILE_TEMPLATE
        .format(
            checkpoint_number
        )
    )

    path = (
        config.MEMORY_DIR
        / filename
    )

    checkpoint = {
        "created_at": utc_now(),

        "state": state,

        "ledger": load_ledger(),

        "memory_text": (
            config.CURRENT_MEMORY_FILE
            .read_text(
                encoding="utf-8"
            )
            if config.CURRENT_MEMORY_FILE.exists()
            else ""
        ),
    }

    atomic_write_json(
        path,
        checkpoint,
    )

    logger.info(
        "Created checkpoint: %s",
        path,
    )


# ============================================================
# ROUND EXECUTION / RECOVERY
# ============================================================

def run_round(
    state,
):
    status = state[
        "round_status"
    ]

    # --------------------------------------------------------
    # START A NEW ROUND
    # --------------------------------------------------------

    if status in {
        "idle",
        "complete",
    }:

        state[
            "round"
        ] += 1

        state[
            "current_speaker"
        ] = None

        state[
            "round_status"
        ] = "starting"

        save_state(
            state
        )

        logger.info(
            "Starting round %s",
            state["round"],
        )

    # --------------------------------------------------------
    # RECOVER SPEAKER 1
    # --------------------------------------------------------

    if state[
        "round_status"
    ] in {
        "starting",
        "speaker_1_thinking",
        "speaker_1_failed",
    }:

        success = run_speaker_turn(
            state,
            speaker_number=1,
        )

        if not success:
            return False

    # --------------------------------------------------------
    # RECOVER SPEAKER 2
    # --------------------------------------------------------

    if state[
        "round_status"
    ] in {
        "speaker_1_complete",
        "speaker_2_thinking",
        "speaker_2_failed",
    }:

        success = run_speaker_turn(
            state,
            speaker_number=2,
        )

        if not success:
            return False

    # --------------------------------------------------------
    # COMPLETE ROUND
    # --------------------------------------------------------

    if state[
        "round_status"
    ] == "speaker_2_complete":

        state[
            "current_speaker"
        ] = None

        state[
            "round_status"
        ] = "complete"

        save_state(
            state
        )

        logger.info(
            "Round %s completed.",
            state["round"],
        )

        # ----------------------------------------------------
        # MEMORY UPDATE
        # ----------------------------------------------------

        if (
            config.MEMORY_UPDATE_INTERVAL > 0
            and state["round"]
            % config.MEMORY_UPDATE_INTERVAL
            == 0
        ):

            state[
                "round_status"
            ] = "memory_update"

            save_state(
                state
            )

            memory_success = (
                update_analytical_memory(
                    state
                )
            )

            if not memory_success:

                logger.warning(
                    "Memory update failed at round %s. "
                    "Debate will continue.",
                    state["round"],
                )

            state[
                "round_status"
            ] = "complete"

            state[
                "current_speaker"
            ] = None

            save_state(
                state
            )

        # ----------------------------------------------------
        # CHECKPOINT
        # ----------------------------------------------------

        if (
            config.CHECKPOINT_INTERVAL > 0
            and state["round"]
            % config.CHECKPOINT_INTERVAL
            == 0
        ):

            create_checkpoint(
                state
            )

        return True

    return False


# ============================================================
# STARTUP DISPLAY
# ============================================================

def print_startup(
    state,
):
    print(
        "\n"
        + "=" * 80
    )

    print(
        "AUTONOMOUS AI DEBATE — ITERATION 7"
    )

    print(
        "=" * 80
    )

    print(
        f"Topic:\n{config.TOPIC}"
    )

    print(
        f"\nCentral Question:\n"
        f"{config.CENTRAL_QUESTION}"
    )

    print(
        "\n"
        + "-" * 80
    )

    print(
        f"Speaker 1: "
        f"{config.SPEAKER_1_MODEL} "
        f"[{config.SPEAKER_1_POSITION}]"
    )

    print(
        f"Speaker 2: "
        f"{config.SPEAKER_2_MODEL} "
        f"[{config.SPEAKER_2_POSITION}]"
    )

    print(
        f"Neutral Analyst: "
        f"{config.MEMORY_MODEL}"
    )

    print(
        "-" * 80
    )

    print(
        f"Saved round: "
        f"{state['round']}"
    )

    print(
        f"Saved status: "
        f"{state['round_status']}"
    )

    print(
        f"Maximum rounds: "
        f"{config.MAX_ROUNDS}"
    )

    print(
        f"Memory interval: "
        f"{config.MEMORY_UPDATE_INTERVAL}"
    )

    print(
        f"Recent exchanges: "
        f"{config.RECENT_EXCHANGES}"
    )

    print(
        f"Model keep-alive: "
        f"{config.OLLAMA_KEEP_ALIVE}"
    )

    print(
        "=" * 80
        + "\n"
    )


# ============================================================
# MAIN
# ============================================================

def run_debate():
    initialize_directories()

    setup_logging()

    initialize_transcript()

    initialize_memory()

    initialize_ledger()

    state = load_state()

    print_startup(
        state
    )

    logger.info(
        "Checking Ollama..."
    )

    print(
        "Checking Ollama..."
    )

    if not check_ollama():

        print(
            "ERROR: Ollama is unavailable."
        )

        logger.error(
            "Ollama unavailable."
        )

        return

    print(
        "Ollama connection OK."
    )

    logger.info(
        "Ollama connection successful."
    )

    # --------------------------------------------------------
    # Remove any model left loaded from a previous run.
    # --------------------------------------------------------

    unload_all_models()

    try:

        while True:

            # ------------------------------------------------
            # Stop only after a COMPLETE round.
            # ------------------------------------------------

            if (
                state["round"]
                >= config.MAX_ROUNDS
                and state["round_status"]
                == "complete"
            ):

                logger.info(
                    "Maximum rounds reached."
                )

                break

            success = run_round(
                state
            )

            if not success:

                logger.error(
                    "Debate stopped because "
                    "the current turn failed."
                )

                break

    except KeyboardInterrupt:

        logger.warning(
            "Keyboard interrupt received."
        )

        state[
            "round_status"
        ] = "interrupted"

        save_state(
            state
        )

        print(
            "\nDebate interrupted safely."
        )

    except Exception as exc:

        logger.exception(
            "Unexpected fatal error: %s",
            exc,
        )

        state[
            "round_status"
        ] = "error"

        save_state(
            state
        )

        print(
            "\nUnexpected error occurred."
        )

        raise

    finally:

        logger.info(
            "Performing final model cleanup."
        )

        unload_all_models()

        print()
        print(
            "=" * 80
        )

        print(
            "DEBATE SESSION ENDED"
        )

        print(
            "=" * 80
        )

        print(
            f"Round: "
            f"{state['round']}"
        )

        print(
            f"Status: "
            f"{state['round_status']}"
        )

        print(
            f"Speaker 1 responses: "
            f"{state['speaker_1']['responses']}"
        )

        print(
            f"Speaker 2 responses: "
            f"{state['speaker_2']['responses']}"
        )

        print(
            f"Successful model calls: "
            f"{state['statistics']['successful_calls']}"
        )

        print(
            f"Failed model calls: "
            f"{state['statistics']['failed_calls']}"
        )

        print(
            f"Memory updates: "
            f"{state['statistics']['successful_memory_updates']}"
        )

        print(
            "\nFiles:"
        )

        print(
            f"  Transcript: "
            f"{config.TRANSCRIPT_FILE}"
        )

        print(
            f"  State: "
            f"{config.STATE_FILE}"
        )

        print(
            f"  Memory: "
            f"{config.CURRENT_MEMORY_FILE}"
        )

        print(
            f"  Ledger: "
            f"{config.ARGUMENT_LEDGER_FILE}"
        )

        print(
            f"  Logs: "
            f"{config.LOG_FILE}"
        )

        print(
            "=" * 80
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_debate()