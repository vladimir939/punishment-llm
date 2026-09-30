"""
Analysis for the costly-punishment LLM study.

Implements exactly what was locked in predictions.md. Nothing here is chosen
after seeing the data: the primary model, the primary contrast, the correction,
and the exclusion rules were all fixed in advance.

Run after data collection:
    python analysis/analyze.py

Inputs:
    data/raw.csv      -- model observations from the harness
    data/humans.csv   -- survey responses: respondent_id, cost, damage,
                         choice, order_version, attention_passed
Outputs:
    out/slopes.csv, out/marginal_effects.csv, out/figures/*.png, console summary
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.genmod.generalized_estimating_equations import GEE
from statsmodels.stats.multitest import multipletests

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
(OUT / "figures").mkdir(parents=True, exist_ok=True)

RAW = ROOT / "data" / "raw.csv"
HUMANS = ROOT / "data" / "humans.csv"


def rule(title: str) -> None:
    print(f"\n=== {title} ===")


def read_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "t"})


# ---------------------------------------------------------------- load

missing = [p.name for p in (RAW, HUMANS) if not p.exists()]
if missing:
    sys.exit(
        f"missing input file(s): {', '.join(missing)}\n"
        f"Run the harness first, and export the survey to data/humans.csv."
    )

raw = pd.read_csv(RAW)
humans = pd.read_csv(HUMANS)

raw["valid"] = read_bool(raw["valid"])
raw["thinking_enabled"] = read_bool(raw["thinking_enabled"])

# Invalid rate is a result, computed on the FULL frame before filtering.
invalid_rate = raw.groupby("model_id")["valid"].apply(lambda s: 1 - s.mean())
rule("Invalid response rate by model")
print(invalid_rate.round(3).to_string())

refusals = raw.loc[~raw["valid"], "refusal_reason"].value_counts()
if len(refusals):
    rule("Invalid rows by reason")
    print(refusals.to_string())

df = raw[raw["valid"]].copy()
df["choice"] = (df["parsed_choice"] == "punish").astype(int)
df["source"] = df["model_id"]
# Cluster ids are namespaced by source. Two reasons: a persona id and a
# respondent id must never collide in the pooled model, and GEE sorts the group
# labels, which fails outright on a mix of str and int.
df["cluster"] = df["source"] + ":" + df["persona_id"].astype(str)

# The thinking ablation reruns a reasoning model with thinking OFF. Those rows
# belong to the ablation (P11) only. Left in, they silently pool two different
# configurations of one model into its headline slope.
reasoning_models = df.loc[df["thinking_enabled"], "model_id"].unique()
is_ablation_row = df["model_id"].isin(reasoning_models) & ~df["thinking_enabled"]
ablation_rows = df[is_ablation_row].copy()
full = df
df = df[~is_ablation_row].copy()

# Attention-check exclusions are reported, not hidden.
humans["attention_passed"] = read_bool(humans["attention_passed"])
n_before = humans["respondent_id"].nunique()
humans = humans[humans["attention_passed"]].copy()
n_after = humans["respondent_id"].nunique()
print(
    f"\nHuman respondents: {n_after} retained, {n_before - n_after} excluded "
    f"on attention check"
)

humans["source"] = "humans"
humans["cluster"] = "humans:" + humans["respondent_id"].astype(str)
humans["arm"] = "A"


def fit_gee(formula: str, data: pd.DataFrame):
    return GEE.from_formula(
        formula,
        groups="cluster",
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Exchangeable(),
        data=data,
    ).fit()


def gee_slope(d: pd.DataFrame):
    """Cluster-robust logistic slope on cost. Returns (beta, se, p, lo, hi, ame)."""
    m = fit_gee("choice ~ cost", d)
    b, se, p = m.params["cost"], m.bse["cost"], m.pvalues["cost"]
    # Average marginal effect: mean over observations of dP/dcost. A CJSJ
    # reader will not interpret a log-odds coefficient of -0.186.
    linpred = m.params["Intercept"] + b * d["cost"]
    prob = 1 / (1 + np.exp(-linpred))
    ame = float(np.mean(prob * (1 - prob) * b))
    return b, se, p, b - 1.96 * se, b + 1.96 * se, ame


# ------------------------------------------------- 1. slopes by source

rule("Cost slopes, arm A (cluster-robust logistic)")
rows = []
for src, d in df[df["arm"] == "A"].groupby("source"):
    if d["cost"].nunique() < 2:
        continue
    b, se, p, lo, hi, ame = gee_slope(d)
    rows.append(
        dict(source=src, n=len(d), beta=b, se=se, p=p, ci_lo=lo, ci_hi=hi, ame_pp=ame * 100)
    )

b, se, p, lo, hi, ame = gee_slope(humans)
rows.append(
    dict(
        source="humans",
        n=len(humans),
        beta=b,
        se=se,
        p=p,
        ci_lo=lo,
        ci_hi=hi,
        ame_pp=ame * 100,
    )
)

slopes = pd.DataFrame(rows).sort_values("beta")
print(slopes.round(4).to_string(index=False))
slopes.to_csv(OUT / "slopes.csv", index=False)

rule("Marginal effects (percentage points of punishment per $1 of cost)")
for _, r in slopes.iterrows():
    print(f"  {r['source']:<22} {r['ame_pp']:+.2f} pp per $1")
slopes[["source", "n", "beta", "ame_pp"]].to_csv(
    OUT / "marginal_effects.csv", index=False
)

# --------------------------------- 2. joint model, Holm-corrected

core = pd.concat(
    [
        df[df["arm"] == "A"][["choice", "cost", "cluster", "source"]],
        humans[["choice", "cost", "cluster", "source"]],
    ],
    ignore_index=True,
)

joint = fit_gee("choice ~ cost * C(source, Treatment('humans'))", core)

inter = [k for k in joint.params.index if k.startswith("cost:")]
if inter:
    holm = multipletests(joint.pvalues[inter], method="holm")[1]
    rule("Human-vs-model slope differences (Holm-corrected)")
    for k, raw_p, adj_p in zip(inter, joint.pvalues[inter], holm):
        print(
            f"  {k:55s} diff={joint.params[k]:+.4f}  "
            f"p={raw_p:.4f}  p_holm={adj_p:.4f}"
        )

# ------------------- 2b. the comparison that matches the human instrument
#
# The human form put all four conditions on one page, so respondents saw the
# whole price ladder. That is arm B, not arm A. The preregistered contrast
# above compares humans against arm A and therefore compares two different
# tasks; this one compares like with like. Not preregistered — the mismatch
# was noticed after collection — and reported as such.

matched = pd.concat(
    [
        df[df["arm"] == "B"][["choice", "cost", "cluster", "source"]],
        humans[["choice", "cost", "cluster", "source"]],
    ],
    ignore_index=True,
)
matched_fit = fit_gee("choice ~ cost * C(source, Treatment('humans'))", matched)
inter_m = [k for k in matched_fit.params.index if k.startswith("cost:")]
if inter_m:
    holm_m = multipletests(matched_fit.pvalues[inter_m], method="holm")[1]
    rule("Humans vs arm B — matched presentation (NOT preregistered)")
    for k, raw_p, adj_p in zip(inter_m, matched_fit.pvalues[inter_m], holm_m):
        verdict = "differs" if adj_p < 0.05 else "no difference"
        print(
            f"  {k:55s} diff={matched_fit.params[k]:+.4f}  "
            f"p={raw_p:.4f}  p_holm={adj_p:.4f}  {verdict}"
        )

# ------------------------------------------- 3. budget hypothesis (P5)

bud = df[(df["arm"] == "A") & df["persona_budget"].notna()]
if len(bud) and bud["persona_budget"].nunique() > 1:
    m = fit_gee(
        "choice ~ cost * C(persona_budget, Treatment('comfortable'))", bud
    )
    rule("P5: does a tight budget steepen the slope?")
    for k in m.params.index:
        if k.startswith("cost:"):
            print(f"  {k:55s} {m.params[k]:+.4f}  p={m.pvalues[k]:.4f}")

# ------------------------------- 3b. norms manipulation check (P6, level)

nrm = df[(df["arm"] == "A") & df["persona_norms"].notna()]
if len(nrm) and nrm["persona_norms"].nunique() > 1:
    m = fit_gee("choice ~ cost + C(persona_norms, Treatment('loose'))", nrm)
    rule("P6: do strict-norms personas punish at a higher level?")
    for k in m.params.index:
        if k.startswith("C(persona_norms"):
            print(f"  {k:55s} {m.params[k]:+.4f}  p={m.pvalues[k]:.4f}")

# ----------------------------------- 3c. no-persona control (P7)

ctrl = df[df["arm"] == "A"].copy()
if "NONE" in set(ctrl["persona_id"]):
    ctrl["is_control"] = (ctrl["persona_id"] == "NONE").astype(int)
    m = fit_gee("choice ~ cost * is_control", ctrl)
    rule("P7: does the no-persona control differ in slope?")
    for k in m.params.index:
        if k.startswith("cost:"):
            print(f"  {k:55s} {m.params[k]:+.4f}  p={m.pvalues[k]:.4f}")

# ------------------------------------- 3d. persona does not shift slope (P4)

# A persona that always or never punishes has no estimable slope, and leaving
# it in makes the interaction diverge (chi2 in the hundreds of thousands).
# Those personas are dropped and counted. The GEE Wald test is still unstable
# with personas near 0%/100%, so the likelihood-ratio test is the one reported.
import statsmodels.formula.api as smf  # noqa: E402
from scipy import stats  # noqa: E402

p4 = df[df["arm"] == "A"].copy()
persona_rate = p4.groupby("persona_id")["choice"].mean()
estimable = persona_rate[(persona_rate > 0.02) & (persona_rate < 0.98)].index
p4 = p4[p4["persona_id"].isin(estimable)]
full_fit = smf.logit("choice ~ cost * C(persona_id) + C(model_id)", p4).fit(
    disp=0, maxiter=200
)
reduced_fit = smf.logit("choice ~ cost + C(persona_id) + C(model_id)", p4).fit(
    disp=0, maxiter=200
)
lr = 2 * (full_fit.llf - reduced_fit.llf)
lr_df = full_fit.df_model - reduced_fit.df_model
rule("P4: does persona shift the slope?")
print(
    f"  personas tested: {len(estimable)} of {len(persona_rate)} "
    f"(dropped, no variation: {sorted(set(persona_rate.index) - set(estimable))})"
)
print(f"  LR test cost x persona: chi2={lr:.1f}  df={lr_df:.0f}  p={stats.chi2.sf(lr, lr_df):.4f}")

# ------------------------------------------- 4. direct diversity metrics

cells = df[df["arm"] == "A"].groupby(["model_id", "persona_id", "condition_id"])[
    "choice"
]

degenerate = cells.apply(lambda s: s.nunique() == 1).groupby("model_id").mean()
rule("Share of degenerate cells (all repeats identical)")
print(degenerate.round(3).to_string())


def binary_entropy(s: pd.Series) -> float:
    p = s.mean()
    return 0.0 if p in (0.0, 1.0) else -(p * np.log2(p) + (1 - p) * np.log2(1 - p))


entropy = cells.apply(binary_entropy).groupby("model_id").mean()
rule("Mean within-cell entropy (bits)")
print(entropy.round(3).to_string())

diversity = pd.DataFrame(
    {"degenerate_share": degenerate, "mean_entropy_bits": entropy}
).reset_index()
diversity.to_csv(OUT / "diversity.csv", index=False)

# ------------------------------------- 5. arm comparisons (B, C, E, F)

rule("Slopes by arm")
arm_rows = []
for arm in ["A", "B", "C", "E", "F"]:
    sub = df[df["arm"] == arm]
    if not len(sub):
        continue
    for src, d in sub.groupby("model_id"):
        if d["cost"].nunique() < 2:
            continue
        b, se, p, lo, hi, ame = gee_slope(d)
        print(
            f"  arm {arm}  {src:22s} beta={b:+.4f}  p={p:.3f}  "
            f"({ame * 100:+.2f} pp/$1)"
        )
        arm_rows.append(
            dict(arm=arm, model_id=src, n=len(d), beta=b, se=se, p=p, ame_pp=ame * 100)
        )
if arm_rows:
    pd.DataFrame(arm_rows).to_csv(OUT / "slopes_by_arm.csv", index=False)

d_arm = df[df["arm"] == "D"]
if len(d_arm):
    rule("P10: punishment rate under a fair split")
    print(d_arm.groupby("model_id")["choice"].mean().round(3).to_string())
    unfair_ref = df[(df["arm"] == "A") & (df["condition_id"] == "c2")]
    if len(unfair_ref):
        print("\n  same condition (c2) under the unfair split, for comparison:")
        print(unfair_ref.groupby("model_id")["choice"].mean().round(3).to_string())

# ----------------------------- 5b. second vs third party (P12)

both = df[df["arm"].isin(["A", "F"])]
if both["arm"].nunique() > 1:
    rule("P12: third parties vs victims")
    print(both.groupby(["model_id", "arm"])["choice"].mean().round(3).to_string())

# ----------------------------------------- 6. thinking ablation (P11)

# Only models run in BOTH states. The non-reasoning anchor is always off and
# must not be counted as the "off" group.
abl_models = ablation_rows["model_id"].unique()
abl = full[(full["arm"] == "A") & full["model_id"].isin(abl_models)]
if len(abl) and abl["thinking_enabled"].nunique() > 1:
    m = fit_gee("choice ~ cost * thinking_enabled", abl)
    rule("P11: thinking on vs off")
    for k in m.params.index:
        if k.startswith("cost:"):
            print(f"  {k:45s} {m.params[k]:+.4f}  p={m.pvalues[k]:.4f}")
    print("\n  punishment rate by thinking state and cost:")
    print(
        abl.groupby(["thinking_enabled", "cost"])["choice"]
        .mean()
        .round(3)
        .to_string()
    )

# ----------------------------------------------------- figures

fig, ax = plt.subplots(figsize=(7, 4))
s = slopes.sort_values("beta")
ax.errorbar(
    s["beta"],
    range(len(s)),
    xerr=[s["beta"] - s["ci_lo"], s["ci_hi"] - s["beta"]],
    fmt="o",
    capsize=4,
    color="black",
)
ax.axvline(0, color="grey", linestyle="--", linewidth=1)
ax.set_yticks(range(len(s)))
ax.set_yticklabels(s["source"])
ax.set_xlabel("Cost slope (log-odds per $1)")
ax.set_title("Sensitivity to punishment cost, with 95% CI")
fig.tight_layout()
fig.savefig(OUT / "figures" / "fig1_slopes.png", dpi=200)
plt.close(fig)

rates = (
    df[df["arm"] == "A"].groupby(["model_id", "cost"])["choice"].mean().reset_index()
)
hr = humans.groupby("cost")["choice"].mean().reset_index()
fig, ax = plt.subplots(figsize=(7, 4))
for src, d in rates.groupby("model_id"):
    ax.plot(d["cost"], d["choice"], marker="o", label=src, alpha=0.8)
ax.plot(
    hr["cost"], hr["choice"], marker="s", color="black", linewidth=2.5, label="humans"
)
ax.set_xlabel("Cost of punishing ($)")
ax.set_ylabel("Punishment rate")
ax.set_ylim(0, 1)
ax.legend(fontsize=8)
ax.set_title("Punishment rate by cost")
fig.tight_layout()
fig.savefig(OUT / "figures" / "fig2_rates.png", dpi=200)
plt.close(fig)

# Mode collapse measured directly, rather than inferred from an absent slope.
fig, ax = plt.subplots(figsize=(7, 4))
order = diversity.sort_values("degenerate_share")
ax.barh(order["model_id"], order["degenerate_share"], color="0.35")
ax.set_xlim(0, 1)
ax.set_xlabel("Share of cells where every repeat gave the same answer")
ax.set_title("Degenerate cells by model (arm A)")
fig.tight_layout()
fig.savefig(OUT / "figures" / "fig3_degenerate.png", dpi=200)
plt.close(fig)

print(f"\nWrote {OUT / 'slopes.csv'} and 3 figures to {OUT / 'figures'}/")
