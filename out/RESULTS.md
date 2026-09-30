# Results — confirmatory analysis (run 2026-09-19)

> **Correction 2026-09-24.** The human form showed all four conditions on one
> page, which matches arm B, not arm A. The preregistered humans-vs-arm-A
> contrast therefore compares two different tasks. Under matched presentation
> (humans vs arm B) no model differs from humans: Holm p = 0.14 to 0.51.
> Both comparisons are reported in the paper.

> Corrected 2026-09-19: the first run pooled DeepSeek's thinking-OFF ablation rows
> into its headline slope, and counted the non-reasoning anchor as the "off" group
> in P11. `analyze.py` now keeps ablation rows out of every analysis except P11.
> Numbers below are from the corrected run.

Full console output: `out/analysis_log.txt`. Tables: `out/slopes.csv`. Figures: `out/figures/`.

## Data
- Models: 7,117 rows (7,096 valid; 21 api_error timeouts, all retried).
- Humans: 25 respondents (v1 ascending 11, v2 descending 14), 100 observations,
  **0 attention-check failures**. 16 of 25 never punished at any price.

## Headline (arm A, cost slope, log-odds per $1; AME in pp per $1)
| source | beta | p | AME |
|---|---|---|---|
| humans | -0.239 | <.0001 | -2.49 |
| nonreasoning_anchor | -0.050 | .0001 | -1.01 |
| deepseek_frontier | -0.038 | .089 | -0.91 |
| nvidia_frontier | -0.033 | .103 | -0.77 |
| qwen_frontier | -0.031 | .098 | -0.73 |
| xai_frontier | -0.029 | .125 | -0.64 |

Every model's slope differs from the human slope: Holm-corrected p ≤ .0012 for all five.
Human punishment by cost: $5 32%, $10 20%, $15 4%, $20 0%.
Replicates v1 human slope (-0.186) in direction and size.

Order check (humans): cost×order p = .157. The slope is negative in both versions and
if anything steeper in the descending version, so it is not an artefact of ascending
presentation. Low power (11 vs 14); balanced by design, not claimed as a test.

## Prediction scorecard (predictions.md, locked 02.09.2026)
| # | locked answer | result | verdict |
|---|---|---|---|
| P1 | humans negative | -0.239, p<.0001 | **confirmed** |
| P2 | models ~zero | 4 reasoning models n.s. (p .09–.13); anchor -0.050 p<.001 | **partly** — small, 1/5–1/10 of human |
| P3 | persona shifts level | persona rates span 0–100% (see ARM_A_SNAPSHOT) | **confirmed** |
| P5 | no tight-vs-comfortable slope difference | tight -0.056, p=.131 | **confirmed** |
| P6 | strict norms → higher level | +4.28 log-odds, p<.0001 | **confirmed** |
| P7 | NONE control no slope difference | -0.032, p=.386 | **confirmed** |
| P8 | joint presentation produces a slope | arm B all five negative, p ≤ .003 (-0.09 to -0.18) | **confirmed** |
| P9 | fixed damage still ~zero | arm C all p > .05 | **confirmed** |
| P10 | fair split → near zero | 0–7% for 4 models; **anchor 79%** | **confirmed except anchor** |
| P11 | thinking-on steeper slope | on -0.038 (p=.089) vs off -0.009 (p=.55), interaction p=.30; off is flat ~44-47%, on falls 47%→35%; degenerate cells 90% on vs 59% off | **not confirmed** |
| P12 | third parties punish less | third parties punish **more** in all 5 models (e.g. DeepSeek 40%→71%) | **wrong — report as-is** |

| P4 | persona does not shift slope | LR chi2=54, df=11, p<.001 (12 estimable personas) | **wrong — report as-is** |

## Findings worth leading with
1. Humans are price-sensitive; models in isolation barely are (arm A).
2. The same models become strongly price-sensitive when the four prices sit in one
   prompt (arm B, P8) — the gradient is there when visible, absent when each
   decision is made alone.
3. Two locked predictions failed (P11, P12). They go in the paper as failures.
4. Anomaly: the non-reasoning anchor punishes 79% of the time even under a fair
   50/50 split — it is not tracking fairness at all.

Arm E (Russian prompt): punishment level higher in all five models (+7 to +31 pp),
slopes still n.s. Persona levels (P3) span 2%–100%. P4 now tested in analyze.py (LR test; GEE Wald diverges near 0%/100%).
