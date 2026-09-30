# Arm A results snapshot — 2026-09-03

Interim. The confirmatory analysis is `analysis/analyze.py`, run after ALL arms
plus the human survey. Recorded here so the arm-A picture is not lost.

1,904 rows, 0 invalid, $4.97.

## Punishment rate by cost

| model | $5 | $10 | $15 | $20 | drop |
|---|---|---|---|---|---|
| xai_frontier | .365 | .353 | .318 | .271 | -.094 |
| qwen_frontier | .412 | .400 | .353 | .306 | -.106 |
| nvidia_frontier | .447 | .424 | .353 | .341 | -.106 |
| deepseek_frontier | .471 | .447 | .341 | .353 | -.118 |
| nonreasoning_anchor | .765 | .757 | .713 | .610 | -.154 |
| **pooled** | .521 | .506 | .447 | .401 | -.120 |
| *v1 humans (published)* | *.477* | *.295* | *.182* | *.023* | *-.454* |

## Slopes (GEE, clustered on model:persona)

| model | beta | 95% CI | p | pp/$1 |
|---|---|---|---|---|
| xai_frontier | -0.0289 | [-0.066, +0.008] | .125 | -0.64 |
| qwen_frontier | -0.0314 | [-0.069, +0.006] | .098 | -0.73 |
| nvidia_frontier | -0.0328 | [-0.072, +0.007] | .103 | -0.77 |
| deepseek_frontier | -0.0384 | [-0.083, +0.006] | .089 | -0.91 |
| nonreasoning_anchor | -0.0502 | [-0.075, -0.026] | .0001 | -1.01 |
| **POOLED** | **-0.0339** | [-0.049, -0.019] | **<.0001** | -0.83 |

v1 human slope from published rates: **-0.186**.

## Prediction outcomes (locked 2026-09-02)

- **P2 — PARTIALLY WRONG.** Locked answer "~zero". Pooled slope is significantly
  negative (p<.0001), so "indistinguishable from zero" is false in aggregate.
  Per model, 4 of 5 are individually non-significant (p .09-.13). The defensible
  claim is **attenuation, not absence**: models are about **one fifth** as
  price-sensitive as humans (-0.034 vs -0.186). Report as-is; do not restate the
  prediction.
- **P3 — CONFIRMED, strongly.** Persona spans the full range: N02 (Oleg,
  tight/loose) never punishes (.000), P03 (Dima, principled) always does (1.000).
- **P5 — CONFIRMED.** Locked answer "no slope difference". Interaction
  tight-vs-comfortable -0.0562, **p=.131**, not significant. Tight budgets do
  punish less overall (.321 vs .549) but the *slope* is not reliably steeper.
  This is the load-bearing prediction and it held.
- **P6 — CONFIRMED.** Strict norms +4.28 log-odds on level, p<.0001. Level only,
  as pre-registered; the circularity caveat stands.
- **P7 — CONFIRMED.** No-persona control does not differ in slope (p=.386);
  rate .500 vs .467.

## Mode collapse, measured directly

Share of cells where every repeat gave the same answer:

| model | degenerate |
|---|---|
| xai_frontier | .956 |
| qwen_frontier | .941 |
| deepseek_frontier | .897 |
| nvidia_frontier | .868 |
| nonreasoning_anchor | .456 |

The four reasoning models are near-deterministic. The **non-reasoning** anchor is
twice as variable — worth a sentence in the discussion, since it cuts against a
simple "deliberation adds diversity" story.

## Caveat on the human comparison

The human numbers above are v1's published rates (44 respondents, ascending
ladder). The new counterbalanced survey is the actual comparison and is not
collected yet. Treat the 5.5x ratio as provisional.
