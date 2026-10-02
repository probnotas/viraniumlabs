"""
plot.py — one figure comparing the three surprise signals.

Top panel   : one-step prediction error vs time for all three conditions
              (log y-axis: healthy error is orders of magnitude smaller than
              disturbed error, and a linear axis would flatten the baseline to 0).
              Shaded bands mark the PRE and LATE windows used by features.py,
              so the plot and the printed numbers can be checked against each other.
Bottom panel: the pendulum angle, for context — it shows WHAT the body was
              doing while the error evolved (e.g. knocked over and re-balanced).
"""

import matplotlib
matplotlib.use("Agg")          # file output only; no display needed
import matplotlib.pyplot as plt
import numpy as np

import config
from run_experiment import CSV_COLUMNS

# Fixed categorical colours: one per condition, never re-ordered.
COLORS = {"baseline": "#2a78d6", "body_change": "#eb6834", "world_event": "#1baf7a"}
LABELS = {
    "baseline": "Baseline (no disturbance)",
    "body_change": f"Body change ({config.BODY_PARAM} × {config.BODY_SCALE:g}, permanent)",
    "world_event": (f"World event ({config.WORLD_TORQUE:g} N·m shove "
                    f"for {config.WORLD_DURATION} steps)"),
}
INK, MUTED, GRID = "#1f1f1f", "#6b6b6b", "#e6e6e6"


def plot_error_signals(logs: dict, path):
    t0 = config.DISTURBANCE_STEP
    late0 = t0 + config.LATE_OFFSET
    col = CSV_COLUMNS.index

    fig, (ax_err, ax_th) = plt.subplots(
        2, 1, figsize=(11, 7.5), sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1]})

    for ax in (ax_err, ax_th):
        # Analysis windows (light bands) and onset marker.
        ax.axvspan(t0 - config.PRE_WINDOW, t0, color="#f0f0f0", lw=0, zorder=0)
        ax.axvspan(late0, late0 + config.LATE_WINDOW, color="#f0f0f0", lw=0, zorder=0)
        ax.axvline(t0, color=MUTED, lw=1, ls="--", zorder=1)
        ax.grid(axis="y", color=GRID, lw=0.8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelcolor=INK)

    # --- Top: surprise signal ------------------------------------------------
    # Baseline is drawn last (on top): all three runs share a seed, so their
    # traces are IDENTICAL before onset and only the top-most one is visible.
    order = [c for c in logs if c != "baseline"] + ["baseline"]
    end_y = {}
    for cond in order:
        log = logs[cond]
        ax_err.plot(log[:, col("t")], log[:, col("err_norm")],
                    color=COLORS[cond], lw=1.6, label=LABELS[cond], zorder=3)
        end_y[cond] = np.median(log[-30:, col("err_norm")])

    # Direct labels at the right end of each line (identity not by colour
    # alone). Labels are spaced at least ~0.15 decades apart so they don't
    # overlap when two signals end at the same level.
    placed = []
    for cond in sorted(end_y, key=end_y.get):
        y = np.log10(end_y[cond])
        if placed and y - placed[-1] < 0.15:
            y = placed[-1] + 0.15
        placed.append(y)
        ax_err.annotate(cond.replace("_", " "), xy=(1.0, 10 ** y),
                        xycoords=("axes fraction", "data"), xytext=(4, 0),
                        textcoords="offset points", va="center", fontsize=9,
                        color=INK)
    ax_err.set_yscale("log")
    ax_err.set_ylabel("one-step prediction error\n‖actual − predicted‖", color=INK)
    ax_err.set_title("Surprise signal: body change vs world event", loc="left",
                     fontsize=13, color=INK)
    ax_err.legend(loc="upper left", frameon=False, fontsize=9,
                  title="(same seed: all runs identical before onset)",
                  title_fontsize=8, alignment="left")
    ax_err.get_legend().get_title().set_color(MUTED)

    ymax = ax_err.get_ylim()[1]
    for x, text in ((t0 - config.PRE_WINDOW / 2, "pre window"),
                    (late0 + config.LATE_WINDOW / 2, f"late window\n(onset + {config.LATE_OFFSET})")):
        ax_err.text(x, ymax, text, ha="center", va="top", fontsize=8, color=MUTED)
    ax_err.text(t0, ymax, " onset", ha="left", va="bottom", fontsize=8, color=MUTED)

    # --- Bottom: what the body was doing --------------------------------------
    for cond in order:
        log = logs[cond]
        ax_th.plot(log[:, col("t")], log[:, col("theta")], color=COLORS[cond], lw=1.4)
    ax_th.set_ylabel("angle θ (rad)\n0 = upright", color=INK)
    ax_th.set_xlabel("timestep (dt = 0.05 s)", color=INK)
    ax_th.set_ylim(-np.pi - 0.2, np.pi + 0.2)
    ax_th.set_yticks([-np.pi, 0, np.pi], ["−π", "0", "π"])

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved figure -> {path}")
