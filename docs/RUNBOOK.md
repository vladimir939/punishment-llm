# RUNBOOK — everything, in order

Single source of truth. Supersedes all earlier instructions.

**Deadline: 30 September 2026, 11:59 PM EST** — early morning of 1 October
Moscow time. CJSJ states "there are no exceptions."

> **All commands here are PowerShell.** Open it: press `Win`, type `powershell`,
> press Enter.
>
> **First line, every time you open a new window:**
> ```powershell
> cd C:\Users\Xiaom\Claude\punishment-llm
> ```
>
> Any term you don't recognise is explained in **`docs\GLOSSARY.md`**.

---

## All links

| What | URL |
|---|---|
| OpenRouter — create key | https://openrouter.ai/settings/keys |
| OpenRouter — add credit | https://openrouter.ai/credits |
| OpenRouter — model IDs | https://openrouter.ai/models |
| OpenRouter — spend log | https://openrouter.ai/activity |
| CJSJ — paper template (.docx) | https://columbiajuniorsciencejournal.org/s/CJSJ-Original-Research-Template-1-faxy.docx |
| CJSJ — Permission to Publish | https://columbiajuniorsciencejournal.org/s/CJSJ-Permission-to-Publish-Form.pdf |
| CJSJ — submission portal | https://forms.gle/JEnyV61qMFcuVcZB6 |
| CJSJ — guidelines | https://columbiajuniorsciencejournal.org/guidelines |
| Google Forms | https://docs.google.com/forms |

---

## How much money to put in OpenRouter

**Short answer: $20.** Estimated cost **$9.98**, from *measured* token counts.

```powershell
python tools\compare_costs.py
```

| Model | Lab | Calls | Cost |
|---|---|---|---|
| xai_frontier — Grok 4.6 | xAI (US) | 1,011 | $3.43 |
| qwen_frontier — Qwen3.6 Max | Alibaba (CN) | 1,011 | $5.24 |
| nvidia_frontier — Nemotron 3 Ultra | NVIDIA (US) | 1,011 | $1.09 |
| deepseek_frontier — DeepSeek V4 Pro | DeepSeek (CN) | 1,351 | $0.99 |
| nonreasoning_anchor — DeepSeek V4 Flash | — | 1,284 | $0.03 |
| **Total** | | **5,668** | **~$10** |

These are not guesses. Each model was called on real study prompts and the
provider's own token counts were read back (`tools\measure_cost.py`,
`toolsariance_check.py`). The measured medians live in
`harness/costs.py -> MEASURED_OUTPUT_TOKENS`.

### Why Mistral was dropped

The original roster had Mistral Medium 3.5 in the fourth slot for European lab
diversity. Measurement killed it: **median 5,227 reasoning tokens per call**,
projecting **$46–61 for that slot alone** — five times the rest of the study
combined. It also ignored `reasoning_effort`, spending *more* at `low` than at
`medium`, and averaged 71 s per call.

NVIDIA Nemotron replaced it: 204–359 reasoning tokens (tight spread), 4/4 valid
responses, $1.09, and it keeps the roster at two US and two Chinese labs.

**The general lesson, worth stating in the paper:** token-count estimates are
unreliable enough to be worth measuring. A single sample is not enough either —
Mistral read 807 tokens on one call and 7,727 on another.

**Watch real spend** at https://openrouter.ai/activity.

---

## PHASE 0 — Today (~1 hour)

### 0.1 Mentor form — first, before anything else

1. Download https://columbiajuniorsciencejournal.org/s/CJSJ-Permission-to-Publish-Form.pdf
2. Fill: name, email, high school + location, graduation year, research subject.
3. Email to Лоскутова З. В., subject line with a date:
   *"Permission to Publish — подпись нужна до 20 сентября"*
4. Ask for a signed scan back as PDF.
5. When it arrives, save it as `VyatchaninVladimir_form.pdf`.

The only step gated on another person. Send it before anything else.

### 0.2 OpenRouter key

1. https://openrouter.ai/settings/keys → **Create Key** → name it
   `punishment-llm` → **copy it** (shown once only).
2. https://openrouter.ai/credits → top up **$20**.
3. In PowerShell, paste this with your real key between the quotes:

   ```powershell
   $env:OPENROUTER_API_KEY = "sk-or-v1-paste-your-key-here"
   ```

   **What this does:** hands your key to the harness without ever writing it
   into a file. `$env:` marks it as an *environment variable* — a value the
   terminal window remembers and passes to programs you run. Keeping it out of
   files means it can't leak into GitHub or a screenshot.

   **It lasts only for that window.** Close PowerShell and it's forgotten. Open
   a new window later and you must paste that line again before running
   anything. If you ever see `OPENROUTER_API_KEY is not set`, that's all this is.

   **Check it worked:**
   ```powershell
   $env:OPENROUTER_API_KEY.Substring(0,12)
   ```
   Prints the first 12 characters of your key.

   *(`export OPENROUTER_API_KEY=...` from my earlier message is the Linux/Mac
   form. It does nothing in PowerShell. Use the `$env:` line.)*

### 0.3 Predictions — DONE ✅

You locked `predictions.md` on 2026-09-02, and its fingerprint is saved in
`docs\predictions_lock.txt`.

**What that was for:** the credibility of a pre-registered study rests on
proving the predictions were written *before* the data existed. A SHA-256 hash
is a fingerprint of a file — change one character and it changes completely.
Having recorded it, you can prove months later that nothing was quietly edited
to fit the results. Reviewers and judges do ask.

**To re-check that the file is untouched** (do this once more before submitting):

```powershell
Get-FileHash predictions.md -Algorithm SHA256
```

Compare the `Hash` it prints with the one in `docs\predictions_lock.txt`.
Identical = untouched.

*(`sha256sum` is the Linux command and doesn't exist in PowerShell.
`Get-FileHash` is the Windows equivalent.)*

### 0.4 Install the packages

```powershell
pip install openai pandas statsmodels matplotlib pytest
```

**What this does:** `pip` is Python's installer. This downloads five bundles of
pre-written code the project needs — `openai` talks to OpenRouter, `pandas` and
`statsmodels` do the statistics, `matplotlib` draws the graphs, `pytest` runs
the self-checks. **You run this once, ever.** Takes a few minutes, costs nothing.

Then confirm nothing is broken:

```powershell
python -m pytest tests -q
```

**What this does:** runs the project's 124 built-in self-checks — the parser
reads answers correctly, the payoff arithmetic is right, reruns don't duplicate
data, and so on. Expect the last line to say `124 passed`.

**Zero API calls, costs nothing.** It's not a step in the experiment; it's a
smoke alarm before you spend money. Anything other than `124 passed` → stop and
send me the output.

---

## PHASE 1 — Pilot (~20 min, under $0.50)

Never skip this. A parser or routing bug found after 5,600 calls gives you a
full dataset of plausible-looking garbage that fails silently.

```powershell
python -m harness --dry-run --arms A --show 8
```

Free — renders the prompts without sending anything. Read them and check:
- `Option X: Do nothing` … `Option Y: Pay $5`, and on `opt_order=nothing_y` the
  labels are swapped
- c1 → "keep $45 … Person A would keep $65"
- c2 → $40 / $60 · c3 → $35 / $65 · c4 → $30 / $70

Then four live probes, two calls each:

```powershell
python -m harness --sync --arms A --models xai_frontier        --limit 2
python -m harness --sync --arms A --models qwen_frontier       --limit 2
python -m harness --sync --arms A --models nvidia_frontier     --limit 2
python -m harness --sync --arms A --models deepseek_frontier   --limit 2
python -m harness --sync --arms A --models nonreasoning_anchor --limit 2
```

Open `data\raw.csv` in Excel. On the new rows check four columns:

| Column | Expect |
|---|---|
| `raw_response` | ends with a clean `CHOICE: X` or `CHOICE: Y` line |
| `parsed_choice` | `punish`/`nothing`, matching the letter (`nothing_x` ⇒ X = nothing) |
| `served_by` | which upstream company actually answered — note it |
| `reasoning_tokens` | large for the thinking models, ~0 for `deepseek` |

- **A model 404s** → its OpenRouter ID is wrong. Find the right one at
  https://openrouter.ai/models and fix that entry's `"openrouter"` field in
  `spec.json`.
- **`valid` is `false` on both rows** → stop; send me the `raw_response` text.
- **`served_by` differs between the two rows** → routing is drifting. Add the
  slug to that model's `"openrouter_only"` in `spec.json`.

Then clear the pilot rows so collection starts clean:

```powershell
Remove-Item data\raw.csv
```

---

## PHASE 2 — Collection (~2–4 days, mostly unattended)

```powershell
python -m harness --sync --arms A
python -m harness --sync --arms B,C
python -m harness --sync --arms D,E,F
python -m harness --sync --ablation
```

- Arm A first, so you hold the core result if time runs short.
- Safe to close/Ctrl-C and re-run: it resumes from the CSV and never renumbers
  repeats.
- Remember to re-paste the `$env:OPENROUTER_API_KEY` line in any new window.
- Watch spend at https://openrouter.ai/activity.

### 2.1 Verify the ablation actually ablated — required

Some models silently ignore a request to turn reasoning off. P11 is your
discriminating test between mode collapse and shallow inference; if reasoning
never stopped, that test means nothing.

```powershell
python -c "from harness.providers.openrouter_provider import verify_ablation; print(verify_ablation('deepseek_frontier','data/raw.csv'))"
```

- `-> reasoning genuinely off` → good, continue.
- `-> WARNING: reasoning did not stop` → that model ignored the disable request.
  Switch the ablation to another model by editing `thinking_ablation.models` in
  `spec.json` (try `xai_frontier`, which xAI serves first-party), then re-run
  `python -m harness --sync --ablation`.

---

## PHASE 3 — Human survey (start alongside Phase 2 — tightest dependency)

### 3.1 Build form v1

https://docs.google.com/forms → **Blank form**

1. Title: `Исследование: решения в экономической задаче (версия 1)`
2. Description ← intro text from `survey\FORMS.md` §1
3. **⚙ Settings** tab:
   - Collect email addresses → **Do not collect**
   - Limit to 1 response → **off** (it forces sign-in and stores identity)
   - Show progress bar → on
4. **Questions** tab → **⊟ Add section** → paste the scenario text (§2) as the
   section description
5. Add section, then each item: **⊕ Add question** → type **Multiple choice** →
   options exactly `Ничего не делать` and `Заплатить` → **Required** on.

   Order for v1: **c1, c2, ATTENTION CHECK, c3, c4**

   Item wording is in `survey\FORMS.md` §3. Attention check text:
   `Этот вопрос проверяет внимательность чтения. Выберите вариант «Ничего не делать».`
6. Final question: type **Paragraph**, not required:
   `Что повлияло на ваши решения? (необязательно)`

### 3.2 Form v2

⋮ (top right) → **Make a copy** → rename to `(версия 2)` → drag items into
**c4, c3, ATTENTION CHECK, c2, c1**.

### 3.3 Distribute

**Send** → 🔗 link icon → **Shorten URL** → copy both. Odd-numbered people get
v1, even get v2. **Target 30–40 total.**

### 3.4 Export

In each form: **Responses** → green Sheets icon → in Sheets **File → Download →
Comma Separated Values**. Save as `survey\responses_v1.csv` and
`survey\responses_v2.csv`, then:

```powershell
python survey\import_forms.py --v1 survey\responses_v1.csv --v2 survey\responses_v2.csv --out data\humans.csv
```

Write down the attention-check failure count it prints — the paper reports it.

### 3.5 Published benchmark

Open Fehr & Fischbacher (2004) and copy the cost-response numbers **from the
paper itself, not from memory** into `survey\benchmark.md` with page references.
This is what makes the human comparison defensible against thousands of model
observations.

---

## PHASE 4 — Analysis (~half a day)

```powershell
python analysis\analyze.py
```

Writes `out\slopes.csv`, `out\marginal_effects.csv`, `out\diversity.csv`,
`out\slopes_by_arm.csv` and three figures in `out\figures\`.

Then the near-free qualitative section: open `data\raw.csv` and read **20–30
`reasoning_trace` cells** by hand. Does the model mention the numbers? Compute
the ratio? One paragraph, and exactly what judges find convincing.

---

## PHASE 5 — Manuscript (~4–5 days, the real work)

1. Fill every `{{PLACEHOLDER}}` in `manuscript\manuscript_ru.md` from `out\`.
2. Compress to **2–3 pages** using the cut list in
   `manuscript\REWRITE_NOTES.md` §6.
3. Work the reporting checklist (§7): snapshot strings, run dates, invalid
   rates, marginal effects, exclusion count.
4. Appendix 4 must include the `served_by` values and state that routing was
   pinned with `allow_fallbacks: false`.
5. **Translate to English last.** Three pages instead of nine.

---

## PHASE 6 — Submit

1. Download the template:
   https://columbiajuniorsciencejournal.org/s/CJSJ-Original-Research-Template-1-faxy.docx
2. Paste your text into its existing structure. **Do not restyle it** — it
   enforces Times New Roman 10pt, two columns, 0.75" margins, 0.95 line spacing.
   Wrong format = not reviewed.
3. Produce three files, each **under 10 MB**:
   - `VyatchaninVladimir_form.pdf`
   - `VyatchaninVladimir_paper.docx` — figure captions included
   - `VyatchaninVladimir_figures.ppt` — **`.ppt`**, via *Save As → PowerPoint
     97-2003*
4. Convert references from GOST to the template's style. **Reference 9 needs its
   full author list** (currently "Zhang et al.").
5. Make the GitHub/OSF repo public; put the link in the paper.
6. https://forms.gle/JEnyV61qMFcuVcZB6 → fill name, email, high school +
   location, graduation year, research subject → upload all three → **Submit** →
   screenshot the confirmation.

---

## Three things the study plan got wrong

Checked against the live CJSJ site:

1. **Figures file is `.ppt`, not `.pptx`.** Match their naming convention.
2. **AI disclosure goes in the cover letter *and* acknowledgments** — the plan
   said acknowledgments only. On a paper about LLMs, do all three: methods
   (object of study), acknowledgments (writing aid + software help), cover
   letter (both, briefly).
3. **Hard formatting spec** the plan never mentioned: TNR 10pt, two-column,
   0.75" margins, 0.95 spacing, 10 MB per file.

Also: the plan claimed "roughly two months of slack." It is under four weeks.

---

## Pre-submission checklist

- [ ] Every number in the text recomputed and matching the tables
- [ ] Second-party vs third-party terminology consistent throughout
- [ ] Title makes no mechanistic promise the design cannot support
- [ ] Both competing explanations presented in the discussion
- [ ] Circularity limitation stated explicitly
- [ ] Invalid-response rates published
- [ ] Every model with snapshot string, run date, and `served_by`
- [ ] Temperature stated or noted as uncontrollable
- [ ] Full prompts and persona texts in the appendix
- [ ] Attention-check exclusion count reported
- [ ] Anonymity and consent statement present
- [ ] AI disclosure in methods, acknowledgments **and** cover letter
- [ ] Software assistance acknowledged
- [ ] Repository link live and public
- [ ] `Get-FileHash predictions.md -Algorithm SHA256` still matches
      `docs\predictions_lock.txt`
- [ ] Three files named correctly, each under 10 MB

---

## If it goes wrong

| Symptom | Fix |
|---|---|
| `OPENROUTER_API_KEY is not set` | Paste the `$env:...` line again — it doesn't survive closing the window |
| `config error: ... needs an openrouter model id` | A model in `spec.json` lost its `"openrouter"` field |
| 404 on a model | Wrong OpenRouter ID — check https://openrouter.ai/models |
| All rows `valid=false` | Look at `raw_response` in the CSV. Send it to me |
| `served_by` varies within a model | Pin it via `"openrouter_only"` in `spec.json` |
| Want deeper deliberation | Set `"reasoning_effort": "high"` in `spec.json`; roughly doubles cost |
| Ablation warning | Change `thinking_ablation.models` in `spec.json` to another model |
| Run died midway | Just re-run the same command; it resumes |
| "file not found" | You're in the wrong folder — run the `cd` line again |
| <20 survey responses by 15 Sep | Stop chasing. The published benchmark is the primary human comparison; the survey degrades to "a replication" |
| Arm F has to be dropped | Rename every occurrence to *second-party costly punishment* and cite Fehr & Fischbacher as context only |

---

## Schedule (28 days)

| Dates | Work |
|---|---|
| 2 Sep | Phase 0 + pilot |
| 3–6 Sep | Arms A, B, C running; build and distribute both forms |
| 7–12 Sep | D, E, F + ablation; verify ablation; chase responses |
| 13–15 Sep | Export survey, Fehr & Fischbacher numbers, run analysis, read traces |
| 16–22 Sep | Write and compress the Russian draft |
| 23–26 Sep | Translate to English |
| 27–28 Sep | Template, .ppt, references, repo public, checklist |
| **29 Sep** | **Submit** — a deliberate day of buffer |
