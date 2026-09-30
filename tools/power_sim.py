"""Power simulation for the human survey sample size.

    python tools\power_sim.py

Answers "how many respondents do we need?" by simulation rather than a rule of
thumb, calibrated to the v1 human effect. Each respondent answers all four
price conditions, so observations cluster within respondent -- which is exactly
why the required number of PEOPLE is much smaller than the required number of
OBSERVATIONS. Reported in the methods section.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.genmod.generalized_estimating_equations import GEE

warnings.filterwarnings("ignore")

# Calibrated to study v1: slope -0.186 log-odds per $1, 47.7% punishing at $5.
BETA = -0.186
INTERCEPT = 0.838
# Between-respondent spread in baseline willingness to punish.
SD = 1.0
COSTS = [5, 10, 15, 20]
RUNS = 400
SEED = 7


def simulate_once(n: int, rng: np.random.Generator) -> bool:
    """One synthetic survey. True if it recovers a significant negative slope."""
    rows = []
    for respondent in range(n):
        baseline = rng.normal(INTERCEPT, SD)
        for cost in COSTS:
            p = 1 / (1 + np.exp(-(baseline + BETA * cost)))
            rows.append((respondent, cost, int(rng.random() < p)))
    data = pd.DataFrame(rows, columns=["rid", "cost", "choice"])
    try:
        fit = GEE.from_formula(
            "choice ~ cost",
            groups="rid",
            family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Exchangeable(),
            data=data,
        ).fit()
    except Exception:
        return False
    return bool(fit.pvalues["cost"] < 0.05 and fit.params["cost"] < 0)


def main() -> int:
    rng = np.random.default_rng(SEED)
    print(f"\nPower to detect the human cost slope (p<0.05, correct sign)")
    print(f"{RUNS} simulations per row, seed {SEED}\n")
    print(f"{'respondents':>12} {'observations':>13} {'power':>7}")
    for n in (10, 15, 20, 25, 30, 40, 50):
        hits = sum(simulate_once(n, rng) for _ in range(RUNS))
        print(f"{n:>12} {n * 4:>13} {hits / RUNS:>6.0%}")
    print("\nTarget 25 respondents. Below 15 the study is underpowered.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
