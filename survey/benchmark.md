# Human benchmark: Fehr & Fischbacher (2004)

Extracted from the paper itself (`submission/FehrFischbacher2004.pdf`), not from
memory or secondary sources. Cite as:

> Fehr, E., & Fischbacher, U. (2004). Third-party punishment and social norms.
> *Evolution and Human Behavior*, 25(2), 63–87.

## Their third-party dictator game (TP-DG)

| Feature | Value |
|---|---|
| Participants | 66, each played once |
| Player A endowment | 100 points, could transfer 0/10/20/30/40/50 to B |
| Player B | no endowment, could not affect anyone's payoff |
| Player C (third party) | endowed with **50 points**, observed A's transfer |
| Punishment technology | 1 point spent by C reduced A by **3 points** (1:3) |
| Maximum punishment | C could spend the whole 50-point endowment |
| Exchange rate | 1 point = CHF 0.3 |
| Wording | "deduction points" — the words "punish"/"sanction" were never used |

## Their results

- **Almost two-thirds of third parties punished** the violation of the
  distribution norm.
- Punishment **increased monotonically the more the norm was violated**: mean
  punishment was **14 deduction points when A transferred nothing** (reducing A
  by 42 points), falling to near zero as transfers approached half.
- OLS of punishment on (50 − transfer) is highly significant.
- **Second parties punished more than third parties at every transfer below
  50%.** Low transfers were profitable for dictators under third-party
  punishment but not under second-party punishment.

## Why this is the right benchmark for us

Our design mirrors theirs closely: A keeps 80 of 100, the punisher holds a
separate 50-unit wallet, and our cheapest condition uses exactly their 1:3
cost-to-damage ratio. So their numbers are a published human comparison for
both arms we report.

**The contrast that matters:** in humans, second parties punish *more* than
third parties. Every model we tested does the opposite (arm A vs arm F).
This is what makes prediction P12 a substantive failure rather than noise.
