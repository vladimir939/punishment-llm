# Distributing the survey

Building the forms takes minutes. Getting 30–40 people to answer is the part
that gates the whole study, so treat it as the real task.

## Rule: alternate the versions

Person 1 → v1, person 2 → v2, person 3 → v1, and so on. **Do not let people
choose.** The whole point of two versions is that condition order is randomised
rather than self-selected; letting anyone pick reintroduces the bias the second
version exists to remove.

Easiest way to keep it straight: post v1 in one chat and v2 in another, or send
v1 to the first half of a class list and v2 to the second half.

## Message to send (Russian)

> Привет! Делаю исследовательскую работу по поведенческой экономике — сравниваю,
> как люди и языковые модели принимают одно и то же решение.
>
> Нужны ответы людей. Опрос анонимный, 3–5 минут, без имён и контактов —
> я не увижу, кто отвечал.
>
> [ССЫЛКА]
>
> Там короткий сценарий и четыре ситуации, в каждой нужно выбрать один из двух
> вариантов. Правильных ответов нет — интересно именно то, как вы бы поступили.
>
> Спасибо!

Keep the "правильных ответов нет" line. Without it people try to guess what you
want, which is exactly the demand characteristic the design is trying to avoid.

**Do not** describe the hypothesis, mention that models are being compared on
the same items, or say what you expect to find. If someone asks, tell them
after they've answered.

## Where to send it

- Class chats — the highest-yield channel by far
- Parallel classes, older and younger years (widens the sample beyond one cohort)
- Family and family friends — **especially valuable**, because the biggest
  stated limitation is that the sample is one school, one academic track. Adults
  outside the school partially answer that objection.

## How many respondents you actually need

Power simulation (400 runs per point), calibrated to the v1 human effect
(slope -0.186 log-odds per $1, 47.7% punishing at $5):

| respondents | observations | power to detect the slope |
|---|---|---|
| 10 | 40 | 67% |
| 15 | 60 | 83% |
| **20** | **80** | **96%** |
| 25 | 100 | 98% |
| 30 | 120 | 99% |

**Target 25. Stop at 30.** Each person answers four items, so 25 people is 100
observations — the repeated measures are why this needs far fewer people than
a one-question survey would.

Chasing 40 buys you 1 percentage point of power and costs days you need for
writing. Reproduce `tools/power_sim.py` if a reviewer asks.

## Targets and timing

| Date | Where you should be |
|---|---|
| ~11 Sep | Both links sent, first ~10 responses in |
| ~15 Sep | 25 responses; **stop collecting** |
| ~16 Sep | Export, import, run the analysis |

**If you're below 15 by 15 September, stop chasing and run with what you have.**
The primary human comparison in the paper is the published Fehr & Fischbacher
data, not your survey. A smaller local sample degrades gracefully from "the
human baseline" to "we reproduced the known pattern on our own sample" — which
is a weaker claim but still a true one, and it costs you far less than missing
the deadline.

## What to record for the paper

Keep a note of these as you go; the methods section needs them:

- Total responses per version
- How they were distributed (which channels)
- Attention-check failures (the importer prints this count)
- Anything unusual — someone answering twice, someone asking what it was about

## Export when done

In each form: **Responses** tab → green Sheets icon → in Sheets
**File → Download → Comma Separated Values**.

Save as `survey/responses_v1.csv` and `survey/responses_v2.csv`, then:

```powershell
python survey\import_forms.py --v1 survey\responses_v1.csv --v2 survey\responses_v2.csv --out data\humans.csv
```

Those raw exports carry submission timestamps, so they are gitignored and must
not be committed. `humans.csv` carries only an arbitrary sequential id.
