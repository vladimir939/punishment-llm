# Costly punishment in LLMs — study v2

Data-collection harness and analysis for a behavioural-economics experiment that
treats language models as experimental subjects.

A model role-plays a persona, is shown an unfair allocation made by another
party, and chooses between doing nothing and paying some of its own money to
reduce the unfair party's payoff. The price of punishing varies across
conditions. We measure whether the probability of punishing declines as the
price rises — humans show a clear negative slope, and the hypothesis is that
aligned LLMs do not.

## Layout

```
punishment-llm/
├── predictions.md      locked directional predictions (see "Before you run")
├── spec.json           all experimental content — models, personas, arms
├── templates/          the five prompt templates
├── harness/            the collection package
├── tests/              pytest suite, all provider calls mocked
├── analysis/analyze.py the confirmatory analysis
├── survey/             Google Forms scripts + humans.csv importer
├── manuscript/         the rewritten paper
├── data/               raw.csv (written by the harness), humans.csv
└── out/                slopes.csv + figures (written by analyze.py)
```

## Setup

```bash
python -m venv .venv && . .venv/Scripts/activate      # Windows
pip install -r requirements.txt
```

API keys come from environment variables only. They are never accepted as
arguments, never logged, and never written to disk.

```bash
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...
export GOOGLE_API_KEY=...
export DEEPSEEK_API_KEY=...
```

A model whose key is not set is skipped with a warning rather than crashing the
run, so you can collect one provider at a time.

### Or route everything through OpenRouter

One key instead of four:

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
python -m harness --dry-run --via openrouter
python -m harness --sync --via openrouter --arms A
```

`--via openrouter` rewrites every model's provider and snapshot at load time.
`spec.json` stays the single source of truth — personas, arms and conditions are
untouched — and a model with no `openrouter` id is an error rather than a silent
skip.

Three consequences the paper must state:

- **No batch endpoint.** Everything runs sync, so the ~50% batch discount is
  unavailable. Same study, roughly double the API cost.
- **Routing varies.** OpenRouter chooses an upstream provider per call. The
  `served_by` column records which one actually answered. After the pilot, check
  whether it is stable; if not, pin it with `openrouter_only` in `spec.json`.
- **Reasoning toggles are best-effort.** Some models ignore a request to turn
  reasoning off. The ablation depends on it genuinely being off, so verify:

  ```bash
  python -c "from harness.providers.openrouter_provider import verify_ablation; \
      print(verify_ablation('anthropic_frontier','data/raw.csv'))"
  ```

  If it warns, that model's ablation is invalid over OpenRouter — call it
  directly for the ablation arm.

Only official provider APIs are used. Nothing here scrapes, drives, or automates
a consumer chat interface (claude.ai, chatgpt.com, …) — that is against those
providers' terms.

## Before you run

1. **`predictions.md` must be dated and signed.** It ships as a draft. Read it,
   change anything you disagree with, delete the banner, fill in the two lines.
   No paid call goes out before that file is locked.
2. **Check the model strings in `spec.json`.** They were verified on 2026-09-01
   and the frontier list moves every few months.
3. **Fill in `harness/costs.py`.** Only Anthropic prices are on file; the
   dry-run total excludes every model without a price and says so.

## Usage

```bash
# Render every prompt, count them, estimate cost. Zero API calls.
python -m harness --dry-run
python -m harness --dry-run --arms A --models anthropic_frontier --show 6

# Pilot: eight live calls on one reasoning model, thinking on.
python -m harness --sync --arms A --models anthropic_frontier --limit 8

# Collection. Arm A first, then B and C, then D/E/F.
python -m harness --batch --arms A
python -m harness --batch --arms B,C
python -m harness --batch --arms D,E,F

# The thinking ablation.
python -m harness --batch --ablation

# Then the analysis.
python analysis/analyze.py
```

`--batch` uses each provider's batch endpoint where one exists — roughly half
price, higher throughput, up to 24-hour turnaround. Results are written to CSV
the moment they are retrieved, because batch results expire server-side after
about a month. DeepSeek and Google fall back to `--sync` automatically.

Two things to know about batch mode: cancellation is best-effort, so in-flight
requests still bill; and a `--batch` run blocks while polling, so run it where
it can sit.

### Resuming

The natural key is `(model_id, arm, persona_id, condition_id, rep,
thinking_enabled)`. On startup the harness reads the existing CSV and skips any
key already present with `valid=true`. A rerun after a crash resumes rather than
duplicating, and repeats are never renumbered. Invalid rows are deliberately
*not* treated as done, so a rerun retries them.

## Volume and cost

Per model, uncapped: **1,284 calls** — A 544, B 136, C 340, D 48, E 96, F 120.
Reasoning models are capped at 5 repeats (`reasoning_model_rep_cap`), which
brings them to 1,011 each. With the roster in `spec.json` that is **5,601 calls
producing 7,182 CSV rows**, plus 340 for the ablation.

The dry-run estimate against Anthropic pricing alone is roughly **$24 sync /
$12 batch**. Fill in the remaining prices before quoting a real total. Output
tokens dominate on reasoning models, because thinking tokens bill as output.

## Model roster

| id | provider | snapshot | thinking | notes |
|---|---|---|---|---|
| `anthropic_frontier` | anthropic | `claude-opus-5` | on | carries the ablation; swap to `claude-sonnet-5` to cut cost ~40% |
| `openai_frontier` | openai | `gpt-5.6-sol` | on | |
| `google_frontier` | google | `gemini-3.7-flash` | on | no batch endpoint wired up; runs sync |
| `deepseek` | deepseek | `deepseek-v4-flash` | off | no batch endpoint; runs sync |
| `nonreasoning_anchor` | openai | `gpt-5.6-luna` | off | see below |

**On the missing legacy anchor.** The study plan asked for an old non-reasoning
model as an anchor. GPT-4o is retired and the v1 models are gone, so a true
legacy anchor cannot be collected any more. Two consequences, both of which
belong in the paper: `nonreasoning_anchor` is a *current* model run without
reasoning, not an old model; and the historical anchor is the v1 dataset itself
(Claude Sonnet 4.6, GPT-4o, DeepSeek — 120 observations), which is reported
alongside rather than re-collected.

## CSV columns

`data/raw.csv`, append mode, flushed after every row.

| column | meaning |
|---|---|
| `run_id` | one API call. Multi-condition rows share it. |
| `timestamp_utc` | ISO 8601, when the response was parsed |
| `model_id` | key from `spec.json`, e.g. `anthropic_frontier` |
| `provider` | `anthropic` / `openai` / `google` / `deepseek` |
| `model_snapshot` | the exact model string sent to the API |
| `temperature_requested` | what `spec.json` asked for; empty if null |
| `temperature_effective` | what was actually in force. Empty when the model does not accept a temperature — recorded as the effective value, never the requested one. |
| `thinking_enabled` | whether reasoning was on for this call |
| `arm` | `A`–`F` |
| `template` | template file stem used |
| `language` | `en` / `ru` |
| `role` | `victim` / `third_party` |
| `allocation` | `fair` / `unfair` |
| `persona_id` | `P01`–`P10`, `N01`–`N06`, `NONE` |
| `persona_budget` | `tight` / `moderate` / `comfortable`; empty outside the grid |
| `persona_norms` | `strict` / `loose`; empty outside the grid |
| `condition_id` | `c1`–`c4`, `f1`–`f4`, `s1` |
| `cost` | dollars the punisher pays |
| `damage` | dollars Person A loses |
| `opt_order` | `nothing_x` (even reps) / `nothing_y` (odd reps) — which label "do nothing" carried |
| `situation_order` | multi-condition presentation order, e.g. `c2,c4,c1,c3`; empty otherwise |
| `rep` | 0-indexed repeat |
| `prompt_sha256` | sha256 of the exact prompt sent — every row traces to its input |
| `raw_response` | full response text, never truncated |
| `reasoning_trace` | full reasoning summary where the provider returns one |
| `parsed_choice` | `punish` / `nothing`, normalised regardless of the X/Y mapping; empty when invalid |
| `valid` | `true` / `false` |
| `refusal_reason` | `no_choice_line` / `ambiguous` / `refused` / `off_format` / `api_error` |
| `input_tokens`, `output_tokens` | provider-reported |
| `reasoning_tokens` | thinking tokens billed as output, where reported. Use it to verify the ablation actually turned reasoning off. |
| `latency_ms` | wall-clock for the call |
| `attempt` | 1, or 2 if the first response was invalid and it was retried |
| `served_by` | `upstream_provider/resolved_model` when routing via OpenRouter; empty for direct calls. Reproducibility evidence — report it in the appendix. |

Invalid rows are never dropped. The per-model invalid rate is a reported result.

## Parsing

The single most important correctness requirement in the project. Reasoning
models routinely mention both "X" and "Y" while deliberating, so a naive
substring search would produce a full dataset of plausible-looking garbage that
fails silently. Two defences:

1. Closed reasoning blocks (`<thinking>`, `<think>`, …) are stripped before
   scanning.
2. The choice is read only from a line that *begins* with `CHOICE:`, and only
   from the **last** such line — the final answer, never an intermediate one.

Anything that does not yield exactly one of X/Y is invalid. On invalid the
harness retries exactly once with the identical prompt in a fresh context; if
the second attempt is also invalid the row is written with `valid=false`.

## Tests

```bash
python -m pytest tests -q     # 101 tests, no network
```

The suite never hits a real API. It covers: the parser ignoring X/Y inside a
reasoning trace; malformed, empty and refusal responses; `opt_order`
alternation and its match to the rendered text; `parsed_choice` normalisation
under both mappings; idempotency across reruns; config validation rejecting
unknown persona ids, missing templates and malformed conditions;
multi-condition parsing emitting one row per condition with a shared `run_id`;
and the derived payoff arithmetic for both allocations.

## Known design notes

- **Arm E mixes languages.** The persona set for the Russian arm includes
  personas whose text is English, so an English persona block sits above a
  Russian scenario. This is what the locked design specifies; it is reported as
  a limitation rather than silently changed.
- **Reasoning models are rep-capped at 5**, so arms A and B have fewer repeats
  on those models than on the non-reasoning ones. The analysis clusters on
  persona and does not assume balanced cells.
