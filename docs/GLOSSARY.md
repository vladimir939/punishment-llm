# Plain-language glossary

Every technical term used in the runbook, explained once.

## The basics

**Terminal / PowerShell** — a window where you type commands instead of
clicking. On Windows: press `Win`, type `powershell`, press Enter. A blue window
opens with a blinking cursor. You type one line, press Enter, it does the thing.

**Command** — one line you type into that window. Everything in this project is
copy-paste; you never have to compose one yourself.

**`cd`** — "change directory". Tells the terminal which folder to work in.
`cd C:\Users\Xiaom\Claude\punishment-llm` means "work in the project folder".
You do this once each time you open a new terminal window.

**Working directory** — the folder the terminal is currently "inside". Commands
act on files there. If a command says "file not found", you are usually in the
wrong folder — run the `cd` line again.

## Installing things

**Python** — the programming language this project is written in. Already
installed on your machine (version 3.12.10).

**`pip`** — Python's installer. `pip install X` downloads and installs the
add-on package X. You run it once; after that X is available forever.

**Package / library** — pre-written code someone else published so you don't
have to write it. This project uses:
- `openai` — the code that talks to OpenRouter
- `pandas`, `statsmodels` — the statistics for `analyze.py`
- `matplotlib` — draws the graphs
- `pytest` — runs the self-checks

**`python -m pytest tests -q`** — runs the project's ~124 built-in self-checks.
`-q` means "quiet, just the summary". Seeing `122 passed` means the code is
healthy. This makes **zero** API calls and costs nothing. It is a smoke alarm,
not a step in the study — run it whenever you want reassurance.

## Environment variables

**Environment variable** — a named value the terminal remembers and hands to any
program you run. API keys go here rather than in a file, so the key never ends
up in your code, your screenshots, or GitHub.

**Setting one in PowerShell:**
```powershell
$env:OPENROUTER_API_KEY = "sk-or-v1-...."
```
`$env:NAME = "value"`. The quotes matter. The `$env:` prefix is what makes it an
environment variable rather than an ordinary one.

**`export`** — the *Linux/Mac* way of doing the same thing. **It does not work
in PowerShell.** Ignore any `export ...` line you see; use the `$env:` form.

**It disappears when you close the window.** The value lives only in that one
terminal window. Open a new one, and you must set it again. If you see
`OPENROUTER_API_KEY is not set`, that is all this is.

**To check it is set:**
```powershell
$env:OPENROUTER_API_KEY.Substring(0,12)
```
Prints the first 12 characters. If it errors, it is not set.

## Checksums

**SHA-256 / hash / checksum** — a fingerprint of a file: a long string of
letters and digits computed from the contents. Change one character in the file
and the fingerprint changes completely.

**Why the project uses it** — `predictions.md` must be provably unchanged since
you locked it. That is the whole point of pre-registration. Recording the
fingerprint on the day you lock it means you can prove later that nothing was
edited to fit the results.

**`sha256sum`** — the Linux/Mac command. **Does not exist in PowerShell.**

**The PowerShell version:**
```powershell
Get-FileHash predictions.md -Algorithm SHA256
```

Your lock is already recorded in `docs\predictions_lock.txt`. To check later
that the file has not changed, run the command above and compare the `Hash`
value to what is in that file. Same string = untouched.

## Files and formats

**CSV** — "comma-separated values". A spreadsheet saved as plain text. Opens in
Excel by double-clicking. `data\raw.csv` is where every model answer lands.

**JSON** — a text format for settings. `spec.json` holds all the experiment's
content: models, personas, conditions. Editable in Notepad, but the punctuation
(`{ } " ,`) must stay exactly as it is.

**Markdown / `.md`** — plain text with light formatting (`#` for a heading,
`**bold**`). All the documentation here is Markdown. Opens in Notepad or any
editor.

**Repository / repo** — a folder of code published online (GitHub) so others can
read it. CJSJ wants a link to yours in the paper.

## Terms specific to this project

**API** — the paid, official way for a program to send a question to a model and
get an answer back. Different from typing into a chat window, and the only way
this study collects data.

**API key** — your password for the API. Looks like `sk-or-v1-abc123...`. Anyone
holding it can spend your credits, so it never goes in a file or a screenshot.

**OpenRouter** — a middleman that resells access to many companies' models
through one account and one key. You use it so you need one key instead of four.

**Token** — roughly ¾ of a word. Models are billed per token, in and out.
One of our prompts is about 240 tokens.

**Reasoning / thinking tokens** — some models "think" before answering, and that
hidden thinking is billed as output. It is the single biggest cost in this
project, and why the thinking models cost ~100x what DeepSeek does.

**`:batch`** — a suffix on an OpenRouter model name (e.g.
`anthropic/claude-sonnet-5:batch`) meaning "I am not in a hurry". Half price,
but answers can take much longer. The default here.

**`--fast`** — the flag that removes `:batch`, so answers come back immediately
at roughly double the price. Use it only if the queue is too slow.

**Dry run** — renders every prompt and prints it without sending anything. Free.
Always do this before spending.

**Arm** — one version of the experiment (A through F). See `spec.json`.

**Ablation** — running the same model with its thinking switched off, to see
what thinking was contributing.
