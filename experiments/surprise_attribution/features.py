"""
features.py — simple, hand-defined summary features of each error signal.

Hypothesis being tested:
    body change  -> error rises and STAYS high   (persistent model mismatch)
    world event  -> error spikes then DECAYS      (transient, model still valid)

All windows are anchored at the same onset step t0 = DISTURBANCE_STEP, even
for the baseline, so the baseline acts as a "nothing happened" reference:

    |---- pre ----|t0|-- immediate --| ... |---- late ----|
     PRE_WINDOW       IMMEDIATE_WINDOW      starts at t0 + LATE_OFFSET (= N)

Features per episode:
  pre_mean        mean error in the PRE window (healthy, undisturbed)
  imm_mean        mean error right after onset
  peak            max error from onset to end of episode
  late_mean       mean error N steps later
  imm_ratio       imm_mean  / pre_mean    (did anything happen at onset?)
  late_ratio      late_mean / pre_mean    (is it STILL happening N steps later?)
  still_elevated  late_ratio > ELEVATED_RATIO

Ratios rather than raw differences make the features scale-free: they do not
depend on how accurate this particular model happens to be in absolute terms.

Reading the result: we expect imm_ratio ≫ 1 for both disturbances (so "onset"
alone cannot attribute the cause), and late_ratio ≫ 1 only for body change
(so "persistence" is the distinguishing feature).
"""

import numpy as np

import config
from run_experiment import err_column

FEATURE_NAMES = ["pre_mean", "imm_mean", "peak", "late_mean",
                 "imm_ratio", "late_ratio", "still_elevated"]


def summarize(err: np.ndarray) -> dict:
    t0 = config.DISTURBANCE_STEP
    pre = err[max(0, t0 - config.PRE_WINDOW):t0]
    imm = err[t0:t0 + config.IMMEDIATE_WINDOW]
    late_start = t0 + config.LATE_OFFSET
    late = err[late_start:late_start + config.LATE_WINDOW]
    if len(late) == 0:
        raise ValueError("Late window is past the end of the episode: "
                         "increase EPISODE_STEPS or reduce LATE_OFFSET.")

    pre_mean = pre.mean()
    eps = 1e-12  # guards division if the model is (implausibly) perfect
    late_ratio = late.mean() / (pre_mean + eps)
    return {
        "pre_mean": pre_mean,
        "imm_mean": imm.mean(),
        "peak": err[t0:].max(),
        "late_mean": late.mean(),
        "imm_ratio": imm.mean() / (pre_mean + eps),
        "late_ratio": late_ratio,
        "still_elevated": bool(late_ratio > config.ELEVATED_RATIO),
    }


def summarize_all(logs: dict) -> dict:
    return {cond: summarize(err_column(log)) for cond, log in logs.items()}


def print_summary(summary: dict):
    t0 = config.DISTURBANCE_STEP
    print()
    print("Summary features (onset t0 = %d; late window = steps %d–%d; "
          "'still elevated' if late/pre > %.1f)" % (
              t0, t0 + config.LATE_OFFSET,
              t0 + config.LATE_OFFSET + config.LATE_WINDOW - 1,
              config.ELEVATED_RATIO))
    header = f"{'condition':<13}" + "".join(f"{n:>15}" for n in FEATURE_NAMES)
    print(header)
    print("-" * len(header))
    for cond, f in summary.items():
        cells = []
        for n in FEATURE_NAMES:
            v = f[n]
            cells.append(f"{str(v):>15}" if isinstance(v, bool) else f"{v:>15.3e}"
                         if n in ("pre_mean", "imm_mean", "peak", "late_mean")
                         else f"{v:>15.2f}")
        print(f"{cond:<13}" + "".join(cells))
    print()


def save_summary_csv(summary: dict, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        fh.write("condition," + ",".join(FEATURE_NAMES) + "\n")
        for cond, f in summary.items():
            fh.write(cond + "," + ",".join(
                str(int(f[n])) if isinstance(f[n], bool) else f"{f[n]:.8g}"
                for n in FEATURE_NAMES) + "\n")
