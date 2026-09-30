# START HERE — what you do today

Pure actions. Do them in order. After each one there's what you should see.

If something doesn't match, stop at that step and tell me the step number.

---

## STEP 1 — Send the mentor email

1. Open https://columbiajuniorsciencejournal.org/s/CJSJ-Permission-to-Publish-Form.pdf
2. It downloads a PDF. Open it.
3. Type in: your name, your email, "Letovo School, Moscow", your graduation
   year, and for subject write "Behavioral Economics / Computer Science".
4. Save it.
5. Open your email. Write to Лоскутова З. В.
   - Subject: `Permission to Publish — нужна подпись до 20 сентября`
   - Attach the PDF
   - Body: ask her to sign it and send it back as a PDF scan.
6. Send.

**Done when:** the email is sent. You don't need her reply until late September.

---

## STEP 2 — Open PowerShell

1. Press the **Windows key** on your keyboard.
2. Type: `powershell`
3. Press **Enter**.

**You should see:** a dark blue window with white text and a blinking cursor.

**Keep this window open for every step below.**

---

## STEP 3 — Point it at the project

Type this line, then press Enter:

```
cd C:\Users\Xiaom\Claude\punishment-llm
```

**You should see:** nothing new — just the cursor again, with the path now
showing `punishment-llm`. That is correct. Nothing visible happening means it
worked.

---

## STEP 4 — Install (once, ~3 minutes)

Type this, press Enter:

```
pip install openai pandas statsmodels matplotlib pytest
```

**You should see:** a lot of text scrolling. Wait until the blinking cursor
comes back. Near the end look for the word **`Successfully installed`** (or
`Requirement already satisfied`, which is equally fine).

**You will never need to run this again.**

---

## STEP 5 — Check nothing is broken (~10 seconds)

Type this, press Enter:

```
python -m pytest tests -q
```

**You should see:** rows of dots, then a final line reading:

```
124 passed
```

**If the last line says anything else → stop. Send me what it says.**

---

## STEP 6 — Get your OpenRouter key

In your web browser:

1. Go to https://openrouter.ai/settings/keys
2. Sign in.
3. Click **Create Key**.
4. In the name box type: `punishment-llm`
5. Click **Create**.
6. A long code appears starting with `sk-or-v1-`. Click the copy icon next to it.

**Do not close this popup until you've done STEP 8.** The key is shown only
once.

---

## STEP 7 — Put $20 in

1. Go to https://openrouter.ai/credits
2. Click the button to add credits (labelled **Add Credits** or **Deposit**).
3. Enter **20**.
4. Pay.

**You should see:** a balance of about $20.00 on that page.

---

## STEP 8 — Give the key to the project

Back in the PowerShell window. Type this, but replace `PASTE_YOUR_KEY_HERE`
with your actual key — keep the quote marks:

```
$env:OPENROUTER_API_KEY = "PASTE_YOUR_KEY_HERE"
```

To paste in PowerShell: **right-click**.

Press Enter.

**You should see:** nothing. Correct.

Now check it. Type this, press Enter:

```
$env:OPENROUTER_API_KEY.Substring(0,12)
```

**You should see:** `sk-or-v1-abc` — the first 12 characters of your key.

**If you see red text instead:** you typed STEP 8 wrong. Do it again.

> ⚠️ **This is forgotten when you close the PowerShell window.** Every time you
> open a new one, do STEP 3 and STEP 8 again before anything else.

---

## STEP 9 — Free test, no money spent

Type this, press Enter:

```
python -m harness --dry-run --arms A --show 8
```

**You should see:** eight blocks of text, each looking roughly like this:

```
PERSONA:
You are Артем, 17 years old. ...

SITUATION:
Two people took part in a task. ...

DECISION:
Option X: Do nothing. You keep your $50 and Person A keeps $80.
Option Y: Pay $5 of your own money to reduce Person A's payoff by
$15. You would keep $45 and Person A would keep $65.
```

**Check these three things with your own eyes:**

**1. Blocks 1–4 have `Option X: Do nothing` and `Option Y: Pay ...`**

**2. Blocks 5–8 are swapped** — `Option Y: Do nothing` and `Option X: Pay ...`.
That is intentional and is the thing you most want to confirm works.

**3. The money is right.** Check all four amounts:

| Where it says | The two numbers after should be |
|---|---|
| Pay **$5** … payoff by $15 | keep **$45**, Person A keeps **$65** |
| Pay **$10** … payoff by $20 | keep **$40**, Person A keeps **$60** |
| Pay **$15** … payoff by $15 | keep **$35**, Person A keeps **$65** |
| Pay **$20** … payoff by $10 | keep **$30**, Person A keeps **$70** |

At the bottom you'll see a total call count and a cost estimate.

---

## STEP 10 — First real calls (~2 cents)

Type this, press Enter:

```
python -m harness --sync --arms A --models xai_frontier --limit 2
```

**You should see:** a few lines of progress, then `=== Finished ===`.

**How long:** anywhere from 10 seconds to several minutes.

**If it's still running after 10 minutes:** press **Ctrl+C** and tell me.

---

## STEP 11 — Look at what came back

1. Open **File Explorer**.
2. Go to `C:\Users\Xiaom\Claude\punishment-llm\data`
3. Double-click **`raw.csv`** — it opens in Excel.

You'll see 2 rows of data plus a header row. Find these columns and check them:

| Column | What you should see |
|---|---|
| `valid` | `true` |
| `parsed_choice` | `punish` or `nothing` |
| `raw_response` | text ending in `CHOICE: X` or `CHOICE: Y` |
| `served_by` | something like `xAI/x-ai/grok-4.6` |
| `reasoning_tokens` | a number in the hundreds |

**The one check that matters most:** look at `raw_response` and find the letter
after `CHOICE:`. Then look at `opt_order` in the same row.

- If `opt_order` is `nothing_x`: letter **X** should mean `parsed_choice` =
  `nothing`, letter **Y** should mean `punish`.
- If `opt_order` is `nothing_y`: it's the opposite.

Do this for both rows.

**If `valid` says `false`** → stop. Copy the `raw_response` text and send it
to me.

---

## STEP 12 — Repeat STEP 10 for the other four models

Run these one at a time, checking `raw.csv` after each (same checks as STEP 11):

```
python -m harness --sync --arms A --models qwen_frontier --limit 2
```
```
python -m harness --sync --arms A --models nvidia_frontier --limit 2
```
```
python -m harness --sync --arms A --models deepseek_frontier --limit 2
```
```
python -m harness --sync --arms A --models nonreasoning_anchor --limit 2
```

**If one of them shows a red error mentioning `404` or `not found`:** that
model's name is wrong. Tell me which one and I'll fix it.

**For `nonreasoning_anchor`, `reasoning_tokens` should be 0 or empty.** That's
expected — it is the non-thinking model, on purpose.

---

## STEP 13 — Delete the test data

Type this, press Enter:

```
Remove-Item data\raw.csv
```

**You should see:** nothing. Correct.

---

## ✅ Today is done

You have: the mentor email sent, $20 loaded, everything installed, and all five
models confirmed working.

**Tomorrow, STEP 1 is:** open PowerShell, then

```
cd C:\Users\Xiaom\Claude\punishment-llm
```
```
$env:OPENROUTER_API_KEY = "your-key"
```
```
python -m harness --sync --arms A
```

That's the real collection starting. It runs for a while — leave it going.

Then continue in `docs\RUNBOOK.md` from PHASE 2.
