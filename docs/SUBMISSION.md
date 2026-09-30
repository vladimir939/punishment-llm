# Submission mechanics and pre-submission checklist

**Deadline: CJSJ closes 30 September 2026.**

## Gating items — start these now, they depend on other people

- [ ] **Mentor signature** on the Permission to Publish form. Send the request
      today even if they are away. It is not needed until the final step, so a
      two-week reply window is fine — but it is the one item that depends on
      someone else.
- [ ] **API access.** The account holder must be 18 or older; that is the
      minimum age in every major provider's terms. If the account is not yours,
      that arrangement needs to be settled before any collection.
- [ ] **Repository** created (GitHub or OSF), public, link ready for the paper.

## Submission mechanics

- [ ] Use the **Original Research Paper Template (.docx)** — papers in the wrong
      format are not reviewed
- [ ] Figures duplicated in a separate **.pptx**
- [ ] File names exactly:
      - `VyatchaninVladimir_paper.docx`
      - `VyatchaninVladimir_figures.pptx`
      - `VyatchaninVladimir_form.pdf`
- [ ] References converted from GOST to the template's style
- [ ] **Reference 9 needs its full author list** (v1 has "Zhang et al.")
- [ ] Permission to Publish form (`submission/CJSJ_Permission_to_Publish_BLANK.pdf`)
      needs THREE signatures + dates: author, parent/guardian (author under 18),
      mentor V. E. Lebedeva (scientific consultant for this study). Scan all pages into one PDF.
- [ ] Data and code on GitHub or OSF, link in the paper
- [ ] One paper per student per cycle — confirm nothing else is in flight

## Order of operations

1. Lock `predictions.md` (date + name, delete the draft banner)
2. Dry-run, read six prompts, check the arithmetic and the X/Y flip
3. Eight live calls, one reasoning model, thinking on — confirm the parser
4. Collect: arm A → B, C → D, E, F → ablation → fill gaps
5. Build and distribute the two survey forms; export to `data/humans.csv`
6. Extract the Fehr & Fischbacher benchmark numbers from the paper itself
7. `python analysis/analyze.py`
8. Fill every `{{PLACEHOLDER}}` in the manuscript from `out/`
9. Compress to 2–3 pages
10. **Translate last**
11. Convert to the .docx template, build the .pptx, name the files
12. Work the checklist below
13. Submit

## Pre-submission checklist

Copied from the study plan. Nothing gets ticked from memory — each item is
checked against the artefact.

- [ ] Every number in the text recomputed and matching the tables
- [ ] Second-party vs third-party terminology consistent throughout
- [ ] Title makes no mechanistic promise the design cannot support
- [ ] Both competing explanations presented in the discussion
- [ ] Circularity limitation stated explicitly
- [ ] Invalid-response rates published
- [ ] Every model with snapshot string and run date
- [ ] Temperature stated or noted as uncontrollable
- [ ] Full prompts and persona texts in the appendix
- [ ] Attention-check exclusion count reported
- [ ] Anonymity and consent statement present
- [ ] AI disclosure separates object-of-study from writing-aid
- [ ] Software assistance acknowledged
- [ ] Repository link live and public
- [ ] `predictions.md` unchanged since it was locked

### Verifying the last one

```bash
git log --follow -p predictions.md    # one commit after the lock date = fail
sha256sum predictions.md              # record this when you lock it
```

## Standing at the judging table

You must be able to explain every part of the pipeline unaided. The questions
that get asked, and where the answers live:

| Question | Answer |
|---|---|
| Why eight repeats? | The claim is about distributions; a single draw cannot measure one. Reasoning models are capped at 5 for cost — `spec.json`, `reasoning_model_rep_cap`. |
| How does the counterbalancing work? | The "do nothing" option is labelled X on even repeats and Y on odd ones; `opt_order` records which, and `parsed_choice` is normalised to punish/nothing regardless. Costs no extra calls. |
| What happens on an invalid response? | Retried exactly once with the identical prompt in a fresh context. If still invalid, the row is written with `valid=false` and a reason. Nothing is dropped; the per-model invalid rate is a reported result. |
| How do you know the parser is right? | It reads only the last line beginning with `CHOICE:`, after stripping reasoning blocks. 101 tests, including one built from a reasoning trace that mentions both X and Y. |
| How do you know the prompts are correct? | Every row stores the sha256 of the exact prompt sent. `--dry-run` renders them all without spending anything. |
| Did you write the software? | Answer honestly, and point at the acknowledgment. It is tooling, like setting up an instrument — normal and permitted. Omission hurts far more than disclosure. |
