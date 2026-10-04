# AI Debate — Experiment History

This document records the experiments conducted while developing the autonomous multi-agent debate system.

The project investigates whether multiple local LLM agents can conduct a sustained, structured debate while maintaining context, tracking arguments, detecting repetition, preserving evidence status, and remaining anchored to a central question.

---

# Project Objective

Build an autonomous multi-agent debate system in which locally hosted language models:

1. Represent opposing positions.
2. Generate arguments and rebuttals.
3. Read the preceding debate context.
4. Maintain persistent debate state.
5. Maintain long-term memory across rounds.
6. Detect repetition and unresolved disagreements.
7. Track evidence claims and their status.
8. Detect topic drift.
9. Recover safely from interruptions and failures.
10. Eventually support multiple specialized agents such as debaters, analysts, judges, and evidence validators.

The current debate topic used for experimentation is:

> **Capitalism is needed for a fair world**

Central question:

> **Is capitalism necessary for achieving a fair world, and if so, under what conditions?**

---

# Hardware and Runtime Architecture

## Compute

The primary model host is PC1 running Ollama inside WSL.

GPU:

- NVIDIA RTX 4070 Ti Super
- 16 GB VRAM

The debate orchestration process runs separately on PC2.

PC2 communicates with the Ollama server on PC1 over the network/Tailscale.

Ollama endpoint used during the experiments:

```text
http://100.75.129.88:11434
```

Because the GPU has limited VRAM, models are loaded sequentially rather than kept simultaneously in GPU memory.

The system uses:

```text
keep_alive = 0
```

and explicitly verifies model unloading through Ollama's process/model status endpoint.

---

# Iteration 1 — Initial Autonomous Debate

## Objective

Create the simplest possible autonomous two-agent debate.

## Architecture

Two local LLMs were assigned opposing positions:

- Speaker 1 — FOR
- Speaker 2 — AGAINST

The agents alternated responses and consumed the preceding debate context.

The initial architecture was intentionally simple.

```text
Speaker 1
    ↓
Speaker 2
    ↓
Speaker 1
    ↓
Speaker 2
    ↓
...
```

## Result

The basic multi-agent debate loop worked.

The models were able to generate alternating arguments and consume previous debate content.

## Problems identified

The initial system lacked:

- persistent structured state
- robust recovery
- long-term memory
- argument identity
- evidence tracking
- repetition detection
- topic-drift detection
- structured debate analysis

The experiment established the basic feasibility of the architecture.

## Key lesson

A simple alternating LLM loop is easy to build, but sustained debate requires much stronger state management and reasoning controls.

---

# Iteration 2 — Persistent Debate State

## Objective

Introduce persistent state so that the debate could survive interruptions and maintain information about its current progress.

## Added

A `debate_state.json` file was introduced.

The state tracked information such as:

- topic
- current round
- current speaker
- speaker models
- speaker positions
- response counts
- round status

## Result

The system became recoverable from interruptions and could determine where the debate had stopped.

## Problems identified

State persistence introduced additional edge cases:

- incomplete state files
- invalid JSON
- inconsistent round state
- interruption during a model call
- interruption between transcript writing and state updates

## Key lesson

A long-running autonomous system requires explicit state-machine behavior rather than relying only on the Python process itself.

---

# Iteration 3 — Robust Execution and Model Management

## Objective

Make the runtime reliable enough for long autonomous runs.

## Added

The system was improved to handle:

- Ollama request failures
- retries
- request timeouts
- model loading
- model unloading
- model-unload verification
- execution logging
- persistent transcript writing

The sequential model-loading architecture was established because the available GPU VRAM could not comfortably hold all required models simultaneously.

## Result

The system became substantially more reliable as a long-running local process.

## Key lesson

Model orchestration and debate reasoning are separate problems.

The infrastructure can be reliable even when the debate quality is poor.

---

# Iteration 4 — Longer Autonomous Runs

## Objective

Determine whether the two agents could maintain a coherent debate across more rounds.

## Result

The system successfully performed longer autonomous debates.

However, the quality degraded as the number of rounds increased.

The models increasingly:

- repeated earlier arguments
- restated the same positions
- introduced loosely related concepts
- treated previous model statements as established facts
- failed to maintain a clear distinction between new arguments and repeated arguments

## Key lesson

Increasing the number of rounds does not automatically produce deeper reasoning.

Without structured memory and argument tracking, longer debates primarily increase repetition and semantic drift.

---

# Iteration 5 — Baseline Two-Agent Debate

## Models

Speaker 1:

```text
qwen3:8b
```

Position:

```text
FOR
```

Speaker 2:

```text
llama3.1:latest
```

Position:

```text
AGAINST
```

## Objective

Establish a reliable baseline for the autonomous debate architecture.

## Result

The system successfully completed:

- Round 10
- 21/21 successful model calls
- 0 failed calls

The system successfully performed sequential:

```text
Qwen → unload → Llama → unload
```

## Findings

The debate demonstrated persistent problems with:

### Repetition

The same arguments were repeatedly rephrased.

### Unsupported claims

Statements presented by one model were increasingly treated as evidence by subsequent models.

### Memory requirements

A simple recent-context window was insufficient for maintaining the complete structure of the debate.

### Argument identity

There was no reliable mechanism for determining whether an argument was genuinely new or merely a restatement.

### Recovery

An interrupted turn required more precise recovery behavior to avoid losing generated responses.

## Key lesson

The system needed explicit argument and evidence ledgers rather than relying on raw transcript history.

---

# Iteration 6 — Long-Term Memory

## Objective

Introduce a dedicated memory model that periodically consolidated the debate into persistent long-term memory.

## Models

Speaker 1:

```text
qwen3:8b
```

Speaker 2:

```text
llama3.1:latest
```

Memory/analyst:

```text
deepseek-coder-v2:latest
```

## Architecture

```text
Speaker 1
    ↓
Speaker 2
    ↓
Speaker 1
    ↓
Speaker 2
    ↓
...
    ↓
DeepSeek memory consolidation
    ↓
Persistent memory
```

## Result

The system successfully completed:

- Round 20
- 42/42 successful model calls
- 0 failed calls
- 40 debate calls
- 2 memory-update calls
- memory version 2

Runtime infrastructure remained reliable.

## Major failure

The memory model introduced severe semantic drift.

The original topic was:

> Capitalism is needed for a fair world.

The persistent memory increasingly focused on concepts such as:

- algorithmic governance
- recursive reprogramming
- programmable ecosystems
- feedback loops
- consensus mechanisms

These concepts became increasingly disconnected from the original debate question.

The memory also began describing some unsupported model claims as "evidence-based."

## Key lesson

More memory does not necessarily produce better reasoning.

An unrestricted LLM memory-consolidation process can create coherent but incorrect summaries that gradually replace the actual history of the debate.

## Architectural conclusion

Memory should not be allowed to freely rewrite the historical state.

Future versions should use:

```text
immutable historical arguments
+
structured updates
+
validation
```

rather than unrestricted memory rewriting.

---

# Iteration 7 — Structured Argument Memory

## Objective

Address the problems discovered in Iteration 6 by introducing:

- structured argument IDs
- argument status
- rebuttals
- concessions
- unresolved questions
- evidence status
- important distinctions
- topic-drift tracking
- repetition detection
- neutral analyst output
- immutable topic anchoring
- central-question anchoring

## Models

Speaker 1:

```text
qwen3:8b
```

Position:

```text
FOR
```

Speaker 2:

```text
llama3.1:latest
```

Position:

```text
AGAINST
```

Neutral analyst:

```text
deepseek-coder-v2:latest
```

## Target architecture

The analyst was intended to return structured JSON updates rather than rewriting the entire historical memory.

The memory architecture introduced concepts such as:

```text
S1-A01
S1-A02
S1-A03

S2-A01
S2-A02
S2-A03
```

with statuses including:

```text
NEW
ACTIVE
CHALLENGED
PARTIALLY_DEFENDED
DEFENDED
CONCEDED
UNRESOLVED
SUPERSEDED
```

## Execution result

The system successfully completed:

- Round 10
- 22/22 model calls
- 0 failed calls
- 20 debate calls
- 2 memory/analyst calls

The runtime infrastructure performed correctly.

## Positive results

### Topic anchoring

The system preserved:

```text
TOPIC:
Capitalism is needed for a fair world
```

and:

```text
CENTRAL QUESTION:
Is capitalism necessary for achieving a fair world,
and if so, under what conditions?
```

### Model orchestration

Sequential model loading and unloading continued to work correctly.

### State management

The debate state successfully tracked:

- round
- current speaker
- speaker responses
- memory version
- successful calls
- failed calls

## Major problems

### 1. Semantic topic drift

The debate moved from capitalism and fairness toward:

- blockchain DAOs
- algorithmic governance
- dynamic token weighting
- temporal asymmetry
- time-weighted token dynamics

The system failed to detect this drift reliably.

### 2. Argument ledger failure

After 10 rounds:

```text
speaker_1_arguments: []
speaker_2_arguments: []
```

The argument ledger therefore failed to perform its intended function.

### 3. Analyst inconsistency

The analyst generated references such as:

```text
S1-A03
```

while the persistent argument ledger did not actually contain the corresponding argument.

### 4. Invalid structured records

The persistent memory contained records with empty fields such as:

```text
attacker: ""
target_argument: ""
speaker: ""
description: ""
context: ""
```

Invalid records should not have been allowed to enter persistent memory.

### 5. Evidence problems

The analyst recorded claims such as:

> Studies show...

with:

```text
ASSERTED_UNSUPPORTED
```

However, the system still allowed those claims to enter persistent memory without a stronger distinction between:

```text
model assertion
```

and:

```text
verified evidence
```

### 6. Repetition detection

Repetition was detected but the resulting records contained empty or non-actionable notes.

### 7. Transcript normalization

Some responses contained duplicated speaker prefixes such as:

```text
speaker 1: speaker 1:
```

## Conclusion

Iteration 7 successfully improved infrastructure and introduced the intended structured-memory architecture, but it failed the semantic-quality test.

The experiment demonstrated that:

> Structured memory alone is insufficient.

A reliable debate system requires strict validation between LLM-generated proposals and persistent state.

## Key lesson

The next iteration should prioritize:

1. validation
2. topic relevance
3. argument identity
4. evidence discipline
5. repetition control
6. analyst reliability

rather than simply adding more memory.

---

# Cross-Iteration Findings

Several conclusions have now become consistent across the experiments.

## Finding 1 — Infrastructure is not the main bottleneck

The system can now:

- communicate with Ollama
- load models
- unload models
- verify unloading
- maintain state
- write transcripts
- recover from interruptions
- execute many model calls

The main remaining challenge is reasoning quality.

---

## Finding 2 — More context is not necessarily better

Increasing the amount of transcript or memory available to the models does not guarantee improved reasoning.

Longer context can actually increase:

- repetition
- semantic drift
- contamination from unsupported claims
- propagation of model-generated assumptions

---

## Finding 3 — LLM-generated memory must be treated as untrusted

A language model can produce a highly coherent summary that is nevertheless incorrect.

Therefore:

```text
LLM output
≠
trusted state
```

Persistent state must be validated independently.

---

## Finding 4 — Claims and evidence are different

The system must distinguish between:

```text
A model claimed X.
```

and:

```text
There is evidence supporting X.
```

An unsupported statement should never become evidence simply because a later model repeats it.

---

## Finding 5 — Debate agents naturally converge on shared concepts

When one model introduces a novel concept, the opposing model may engage with that concept rather than challenge whether the concept itself is relevant.

This creates a failure mode:

```text
New concept
    ↓
Opponent responds to concept
    ↓
Concept becomes shared context
    ↓
Both agents optimize around concept
    ↓
Original question disappears
```

This is one of the primary causes of semantic drift observed in Iteration 7.

---

## Finding 6 — Longer debates need stronger controls

A 50-round debate without strong argument tracking is unlikely to produce 5× the reasoning quality of a 10-round debate.

Instead, it can produce 5× the repetition and drift.

Therefore future experiments should use staged evaluation:

```text
5 rounds
    ↓
10 rounds
    ↓
25 rounds
    ↓
50 rounds
```

and only progress when predefined quality criteria are satisfied.

---

# Next Experimental Phase

## Iteration 7.5 — Model Benchmark

Before modifying the debate architecture further, the available local models will be benchmarked against identical reasoning tasks.

Potential models include:

- Qwen3 8B
- Qwen3 14B
- Llama 3.1
- Gemma 4 12B
- Qwen3.5 9B
- Phi-4 14B
- DeepSeek-R1 14B
- GPT-OSS 20B
- Command R7B
- DeepSeek-Coder-V2

The benchmark will evaluate:

1. Argument generation
2. Counterargument generation
3. Rebuttal quality
4. Logical consistency
5. Topic relevance
6. Repetition detection
7. Unsupported-claim detection
8. Evidence discipline
9. Debate judging
10. Structured JSON compliance

The goal is to empirically determine which model is best suited for each role.

---

# Planned Role Architecture

Future versions may use specialized models for:

```
Debater
    ↓
Counter-Debater
    ↓
Analyst
    ↓
Evidence Validator
    ↓
Judge
```

The exact model assigned to each role will be determined experimentally rather than assumed.

---

# Planned Iteration 7.1

After the model benchmark, the debate system will be modified to enforce:

1. Strict topic relevance.
2. Explicit argument IDs.
3. Structured speaker outputs.
4. Python-side validation.
5. Analyst-generated deltas instead of unrestricted memory rewriting.
6. Rejection of invalid analyst updates.
7. Explicit evidence status.
8. Actionable repetition detection.
9. Topic-drift scoring.
10. Transcript normalization.

The first test will use only five rounds.

Success criteria will be defined before execution.

---

# Planned Evaluation Progression

```text
Iteration 7.5
Model benchmark
        ↓
Iteration 7.1
5-round controlled test
        ↓
10-round validation
        ↓
25-round validation
        ↓
50-round long experiment
```

A longer experiment will only be executed after the shorter experiment satisfies the predefined quality criteria.

---

# Version Control

GitHub is now used to preserve experiment code and historical checkpoints.

Each major experiment should be associated with a Git commit and, where appropriate, a Git tag.

Example:

```text
v0.1-baseline
v0.2-memory
v0.3-iteration7
v0.4-iteration7.1
```

Experiment outputs should be separated from source code wherever practical.

The purpose of version control is to ensure that every experimental result can be traced back to the exact implementation that produced it.

---

# Overall Project Status

The project has progressed from a basic two-agent LLM loop to a distributed, persistent, multi-model debate framework.

The current bottleneck is no longer basic infrastructure.

The central research problem is now:

> **How can autonomous LLM agents maintain a coherent, evidence-disciplined, non-repetitive debate over many rounds without allowing generated concepts and unsupported claims to progressively redefine the subject of the debate?**

Future experiments will focus on answering this question.