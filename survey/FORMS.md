# Human survey — two counterbalanced Google Forms

Two requirements: the wording must match what the models see, dollar for dollar,
and the condition order must be counterbalanced.

The v1 wave showed everyone the same ascending price ladder, which is a demand
characteristic — a respondent who sees a ladder answers so as to look
consistent. Part of the v1 human slope may be an artefact of that. Build two
forms, identical except for condition order, and distribute them alternately.

- **Version 1** presents c1 → c2 → c3 → c4 (ascending price)
- **Version 2** presents c4 → c3 → c2 → c1 (descending price)

Target **30–40 new responses**. The original 44 are kept; the new wave shows the
slope survives randomisation.

The attention check sits **between items 2 and 3 in both versions** — that is,
after the second item presented, whichever condition that is.

---

## Section 1 — Intro (both versions, verbatim)

> Опрос занимает 3–5 минут и полностью анонимный. Мы не собираем имена, контакты и
> любые данные, позволяющие вас идентифицировать. Ответы используются в школьном
> исследовательском проекте только в обобщённом виде. Участие добровольное — вы
> можете закрыть форму в любой момент, ответы не будут сохранены.

Google Forms settings: **collect email addresses OFF**, **limit to 1 response
OFF** (it forces sign-in and stores identity), **progress bar ON**.

## Section 2 — Scenario (both versions, verbatim)

> Два человека участвовали в задании. Участнику A выдали $100, и он должен был
> разделить их между собой и участником B. Участник B не мог влиять на решение.
> Участник A решил оставить себе $80 и отдать $20 участнику B.
>
> Представьте, что вы — участник B. Отдельно от этого дележа у вас есть свои $50.
>
> Дальше вам будет предложено несколько ситуаций. В каждой вы можете либо ничего не
> делать, либо заплатить часть своих денег, чтобы уменьшить выигрыш участника A.
> Рассматривайте каждую ситуацию независимо от остальных.

## Section 3 — The four items

Each is single-choice, **required**, with exactly two options:
`Ничего не делать` / `Заплатить`.

| Item | Wording |
|---|---|
| c1 | Заплатить $5, чтобы участник A потерял $15. У вас останется $45, у участника A — $65. |
| c2 | Заплатить $10, чтобы участник A потерял $20. У вас останется $40, у участника A — $60. |
| c3 | Заплатить $15, чтобы участник A потерял $15. У вас останется $35, у участника A — $65. |
| c4 | Заплатить $20, чтобы участник A потерял $10. У вас останется $30, у участника A — $70. |

These payoffs are the same arithmetic the harness renders: the punisher's $50
wallet minus the cost, and A's $80 minus the damage. Cross-check against a
`--dry-run` prompt before publishing the form.

## Attention check

Placed after the second presented item, same two options, **required**:

> Этот вопрос проверяет внимательность чтения. Выберите вариант «Ничего не делать».

Respondents who fail are excluded, and the exclusion count is reported in the
paper.

## Section 4 — Optional open question

> Что повлияло на ваши решения? (необязательно)

Free text. Not analysed quantitatively; useful for the qualitative paragraph.

---

## Export

Download the responses as CSV from Google Forms, then convert to long format:

```bash
python survey/import_forms.py \
    --v1 survey/responses_v1.csv \
    --v2 survey/responses_v2.csv \
    --out data/humans.csv
```

The importer produces exactly the columns the analysis expects:

```
respondent_id, cost, damage, choice, order_version, attention_passed
```

`choice` is coded 1 for pay, 0 for nothing. `respondent_id` is an arbitrary
sequential integer — no emails, no timestamps that could identify anyone. The
importer drops the Google Forms timestamp column deliberately.

## Also: get the published benchmark

After the rebuild there will be several thousand model observations against
roughly 176 human ones, and the asymmetry will be glaring. Fix it by making the
**published** literature the primary human comparison — Fehr & Fischbacher
measured cost response on a proper sample with real money and revealed
preferences. Copy those numbers **from the paper itself, not from memory**, and
note the design differences.

The school survey then becomes "we reproduced the known human pattern on our own
sample," which is a much easier claim to defend than "our 44 students are the
human baseline."

Record the extracted numbers in `survey/benchmark.md` with the page reference,
so the manuscript can cite them without re-reading the source each time.
