"""
config.py — every knob for the surprise-attribution experiment lives here.

Edit this file (not the other modules) to change disturbance timing, magnitude
and type. All other modules import from here, so one change propagates
everywhere and every run is fully described by this file + the random seed.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"            # CSVs + figure go here
MODEL_PATH = HERE / "models" / "forward_model.pt"   # trained forward model

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
# The SAME seed is used for every condition, so baseline / body-change /
# world-event share an identical trajectory up to the disturbance step. Any
# difference after that point is caused by the disturbance alone.
SEED = 0

# ---------------------------------------------------------------------------
# Episode
# ---------------------------------------------------------------------------
EPISODE_STEPS = 400        # Pendulum dt = 0.05 s  ->  400 steps = 20 s
DISTURBANCE_STEP = 200     # step at which body change / world event begins.
                           # Chosen well after swing-up (~50-80 steps) so the
                           # "before" window is a clean, stabilised baseline.

# ---------------------------------------------------------------------------
# Condition 2: BODY CHANGE (permanent, starts at DISTURBANCE_STEP)
# ---------------------------------------------------------------------------
# Which Pendulum-v1 physical parameter to change: "l" (length), "m" (mass)
# or "g" (gravity — not a body change, but handy as a control).
#
# NOTE — why the default is LENGTH, not mass:
#   Pendulum-v1 dynamics are
#       θ̈ = 3g/(2l) · sin θ  +  3/(m l²) · u
#   Mass does NOT appear in the gravity term (gravity torque and inertia both
#   scale with m and cancel). So a mass change only alters how strongly the
#   motor torque u acts, and is only visible in proportion to |u|. While the
#   pendulum is balanced upright u is small, so the mass signal is weaker
#   (measured with this setup: late/pre error ratio ≈ 10 for m×1.5 vs ≈ 17 for
#   l×1.5). Length changes BOTH terms, so it is the cleaner default. This is
#   itself a defensible point: a body change is only detectable to the extent
#   the body is exercised in a way that depends on the changed parameter.
BODY_PARAM = "l"
BODY_SCALE = 1.5           # multiply the parameter by this (1.5 = +50%)

# ---------------------------------------------------------------------------
# Condition 3: WORLD EVENT (transient, starts at DISTURBANCE_STEP)
# ---------------------------------------------------------------------------
# An external torque (N·m) applied ON TOP of the agent's torque for a few
# steps, then removed. The forward model is never told about it — it only
# sees the agent's own commanded action — exactly like an unexpected shove.
# For reference the agent's own torque is limited to ±2 N·m.
WORLD_TORQUE = 6.0         # magnitude of the shove (sign = direction)
WORLD_DURATION = 5         # number of steps the shove lasts (5 × 0.05 s = 0.25 s)

# ---------------------------------------------------------------------------
# Controller (MPC using the learned forward model)
# ---------------------------------------------------------------------------
MPC_HORIZON = 20           # planning horizon in steps (1 s)
MPC_SAMPLES = 500          # candidate action sequences per step
MPC_WARMSTART_FRAC = 0.5   # fraction of samples drawn around last step's plan
MPC_WARMSTART_STD = 0.3    # std of noise around the warm-start plan
# Small Gaussian noise added to the EXECUTED torque ("persistent excitation").
# It keeps the body exercised so that changes to the torque-gain term (mass,
# length) keep producing error while balanced. The effect is detectable without
# it too (sampling MPC is never perfectly still), just weaker: late/pre ratio
# for l×1.5 drops from ≈17 to ≈12 with 0.0. Set to 0.0 to see the noise-free case.
ACTION_NOISE_STD = 0.3

# ---------------------------------------------------------------------------
# Forward model + training
# ---------------------------------------------------------------------------
HIDDEN_SIZES = (128, 128)
TRAIN_SAMPLES = 60_000     # uniform (state, action) samples from the HEALTHY body
VAL_FRACTION = 0.1
TRAIN_EPOCHS = 40
BATCH_SIZE = 256
LEARNING_RATE = 1e-3
RETRAIN = False            # True = ignore saved checkpoint and retrain

# ---------------------------------------------------------------------------
# Summary features
# ---------------------------------------------------------------------------
PRE_WINDOW = 50            # steps before DISTURBANCE_STEP used as "before" baseline
IMMEDIATE_WINDOW = 20      # steps right after onset ("immediate response")
LATE_OFFSET = 100          # N: how many steps after onset we check "still elevated?"
LATE_WINDOW = 50           # length of that late window
# A late window counts as "still elevated" if its mean error exceeds
#   ELEVATED_RATIO × (pre-disturbance mean error).
ELEVATED_RATIO = 2.0
