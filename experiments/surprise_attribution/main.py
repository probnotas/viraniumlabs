"""
main.py — run the whole Rung 3 surprise-attribution experiment.

    cd experiments/surprise_attribution
    python main.py

Pipeline:
  1. load (or train) the forward model of the healthy pendulum   [model.py]
  2. run baseline / body_change / world_event episodes, log CSVs [run_experiment.py]
  3. plot the three error signals on one figure                  [plot.py]
  4. compute + print per-episode summary features                [features.py]
"""

import config
from features import print_summary, save_summary_csv, summarize_all
from model import load_or_train_model
from plot import plot_error_signals
from run_experiment import run_all_conditions


def main():
    model = load_or_train_model()
    logs = run_all_conditions(model)
    plot_error_signals(logs, config.RESULTS_DIR / "error_signals.png")
    summary = summarize_all(logs)
    print_summary(summary)
    save_summary_csv(summary, config.RESULTS_DIR / "summary_features.csv")


if __name__ == "__main__":
    main()
