"""Publication figures for the CJSJ submission.

    python tools\\make_figures.py

Rebuilds all three figures from data/ into out/figures/ at 300 dpi with the
published model names. The versions analyze.py emits are diagnostics: they
carry internal ids (xai_frontier) and default styling, which must not appear
in print.

Figure 2 is two panels on purpose. The paper's claim is a contrast between
isolated and joint presentation, and a contrast is one figure, not two.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIGDIR = ROOT / "out" / "figures"

# Published names. Internal ids never reach a reader.
NAMES = {
    "humans": "Humans",
    "xai_frontier": "Grok 4.6",
    "qwen_frontier": "Qwen 3.6 Max",
    "nvidia_frontier": "Nemotron 3 Ultra",
    "deepseek_frontier": "DeepSeek V4 Pro",
    "nonreasoning_anchor": "DeepSeek V4 Flash",
}
# Validated categorical slots (see dataviz palette); humans carry the ink.
COLOR = {
    "Humans": "#0b0b0b",
    "DeepSeek V4 Flash": "#2a78d6",
    "DeepSeek V4 Pro": "#eb6834",
    "Nemotron 3 Ultra": "#1baf7a",
    "Qwen 3.6 Max": "#eda100",
    "Grok 4.6": "#4a3aa7",
}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#d9d8d4"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(ROOT / "data" / "raw.csv", low_memory=False)
    yes = lambda c: c.astype(str).str.lower() == "true"  # noqa: E731
    raw = raw[yes(raw["valid"])].copy()
    raw["thinking"] = yes(raw["thinking_enabled"])
    raw["choice"] = (raw["parsed_choice"] == "punish").astype(int)
    # Ablation rows belong to the ablation only, never to a headline figure.
    reasoning = raw.loc[raw["thinking"], "model_id"].unique()
    raw = raw[~(raw["model_id"].isin(reasoning) & ~raw["thinking"])]
    humans = pd.read_csv(ROOT / "data" / "humans.csv")
    humans = humans[humans["attention_passed"].astype(str).str.lower() == "true"]
    return raw, humans


def fig1_slopes() -> None:
    """Dot-and-interval. One series, so no legend: the axis names it."""
    s = pd.read_csv(ROOT / "out" / "slopes.csv")
    s["label"] = s["source"].map(NAMES)
    s = s.sort_values("beta")

    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    for i, r in enumerate(s.itertuples()):
        is_human = r.label == "Humans"
        c = INK if is_human else MUTED
        ax.plot([r.ci_lo, r.ci_hi], [i, i], color=c, lw=2 if is_human else 1.4,
                solid_capstyle="round", zorder=2)
        ax.plot(r.beta, i, "o", ms=8 if is_human else 6, color=c,
                markeredgecolor="white", markeredgewidth=1.2, zorder=3)
        ax.annotate(f"{r.beta:+.3f}".replace("-", "−"), (r.ci_hi, i), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=8,
                    color=INK if is_human else MUTED)

    ax.axvline(0, color=GRID, lw=1, zorder=1)
    ax.set_yticks(range(len(s)))
    ax.set_yticklabels(s["label"], fontsize=9,
                       color=INK)
    ax.set_xlabel("Cost slope (log-odds per $1), with 95% CI")
    ax.set_xlim(-0.38, 0.09)
    ax.tick_params(length=0)
    ax.spines["left"].set_visible(False)
    fig.savefig(FIGDIR / "fig1_slopes.png")
    plt.close(fig)


def fig2_rates(raw: pd.DataFrame, humans: pd.DataFrame) -> None:
    """Isolated vs joint presentation — the paper's central contrast."""
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.4), sharey=True)

    for ax, arm, title in (
        (axes[0], "A", "(a) One condition per prompt"),
        (axes[1], "B", "(b) All four in one prompt (human format)"),
    ):
        d = raw[raw["arm"] == arm]
        series = []
        for mid, g in d.groupby("model_id"):
            series.append((NAMES[mid], g.groupby("cost")["choice"].mean()))
        # The human form showed all four conditions on one page, so the human
        # data belong in panel (b). They are repeated in (a) as a dashed
        # reference so the mismatched comparison stays visible.
        human_rates = humans.groupby("cost")["choice"].mean()
        if arm == "B":
            series.append(("Humans", human_rates))

        for label, rates in series:
            human = label == "Humans"
            ax.plot(rates.index, rates.values * 100,
                    label=label if arm == "B" else None,
                    color=COLOR[label], lw=2.4 if human else 1.8,
                    marker="s" if human else "o", ms=6,
                    markeredgecolor="white", markeredgewidth=1.0,
                    zorder=3 if human else 2)

        if arm == "A":
            ax.plot(human_rates.index, human_rates.values * 100,
                    label="Humans (same data, for reference)",
                    color=INK, lw=1.6, ls=(0, (4, 3)), zorder=2)

        ax.set_title(title, fontsize=9, loc="left", color=INK)
        ax.set_xlabel("Cost of punishing ($)")
        ax.set_xticks([5, 10, 15, 20])
        ax.set_xlim(4, 21)
        ax.set_ylim(0, 100)
        ax.grid(axis="y", color=GRID, lw=0.7)
        ax.set_axisbelow(True)

    axes[0].set_ylabel("Punished (%)")
    # Six series, so identity lives in a legend rather than in end-labels,
    # which collided where the lines converge.
    h1, l1 = axes[1].get_legend_handles_labels()
    h0, l0 = axes[0].get_legend_handles_labels()
    handles, labels = h1 + h0, l1 + l0
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False,
               fontsize=8, bbox_to_anchor=(0.5, -0.30), labelcolor=INK)
    fig.savefig(FIGDIR / "fig2_rates.png")
    plt.close(fig)


def fig3_degenerate(raw: pd.DataFrame) -> None:
    """Magnitude, one series: a single hue, no legend."""
    a = raw[raw["arm"] == "A"]
    cells = a.groupby(["model_id", "persona_id", "condition_id"])["choice"].mean()
    share = cells.isin([0, 1]).groupby(level=0).mean().sort_values()
    labels = [NAMES[i] for i in share.index]

    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    ax.barh(labels, share.values * 100, color="#2a78d6", height=0.62)
    for i, v in enumerate(share.values * 100):
        ax.annotate(f"{v:.0f}%", (v, i), xytext=(5, 0),
                    textcoords="offset points", va="center", fontsize=8,
                    color=INK)
    ax.set_xlabel("Cells where every repetition gave the same answer (%)")
    ax.set_xlim(0, 108)
    ax.tick_params(length=0)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=GRID, lw=0.7)
    ax.set_axisbelow(True)
    fig.savefig(FIGDIR / "fig3_degenerate.png")
    plt.close(fig)


def main() -> int:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    raw, humans = load()
    fig1_slopes()
    fig2_rates(raw, humans)
    fig3_degenerate(raw)
    for f in ("fig1_slopes.png", "fig2_rates.png", "fig3_degenerate.png"):
        print(f"  wrote {FIGDIR / f}  ({(FIGDIR / f).stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
