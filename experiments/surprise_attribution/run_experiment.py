"""
run_experiment.py — run one episode per condition and log the surprise signal.

Surprise at step t is the one-step prediction error

    e_t = ‖ obs_{t+1}  −  model.predict(obs_t, a_t) ‖₂

where a_t is the torque the AGENT commanded. Crucially, the model is only
ever given the agent's own action: it is the agent's belief about "what my
body will do when I do this". Anything else that moves the pendulum (a
changed body, an external shove) shows up as error.

The three conditions share one loop; they differ only in a "schedule" that
says what to do to the environment at each step.
"""

import numpy as np
import torch

import config
from controller import MPCController
from env_setup import make_env

CONDITIONS = ("baseline", "body_change", "world_event")

CSV_COLUMNS = [
    "t",                # step index
    "theta",            # true angle (rad, 0 = upright, wrapped to [-π, π])
    "theta_dot",        # true angular velocity (rad/s)
    "agent_torque",     # torque commanded by the controller (seen by the model)
    "external_torque",  # world-event torque (NOT seen by the model)
    "body_changed",     # 1 once the body parameter has been altered
    "err_norm",         # ‖actual − predicted‖  <- the surprise signal
    "err_cos",          # per-dimension signed errors (actual − predicted),
    "err_sin",          #   handy for later analysis of *where* the error is
    "err_thetadot",
]


def disturbance_schedule(condition: str, t: int):
    """Return (change_body_now, external_torque) for this condition and step.

    baseline     : nothing ever happens.
    body_change  : at DISTURBANCE_STEP, rescale the body parameter once.
                   The change persists for the rest of the episode.
    world_event  : for WORLD_DURATION steps starting at DISTURBANCE_STEP,
                   push with WORLD_TORQUE. Then nothing.
    """
    t0 = config.DISTURBANCE_STEP
    if condition == "baseline":
        return False, 0.0
    if condition == "body_change":
        return t == t0, 0.0
    if condition == "world_event":
        active = t0 <= t < t0 + config.WORLD_DURATION
        return False, (config.WORLD_TORQUE if active else 0.0)
    raise ValueError(f"unknown condition {condition!r}")


@torch.no_grad()
def run_episode(model, condition: str, seed: int = config.SEED) -> np.ndarray:
    """Run one episode and return a [T, len(CSV_COLUMNS)] log array."""
    env = make_env(config.EPISODE_STEPS)
    obs = env.reset(seed=seed)
    controller = MPCController(model, env.max_torque, seed=seed)
    body_changed = 0
    rows = []

    for t in range(config.EPISODE_STEPS):
        # 1. Apply the scheduled disturbance (if any) BEFORE this step's physics.
        change_body, ext_torque = disturbance_schedule(condition, t)
        if change_body:
            env.change_body(config.BODY_PARAM, config.BODY_SCALE)
            body_changed = 1

        # 2. Agent chooses an action using its (healthy-body) self-model.
        action = controller.act(obs)

        # 3. Self-model predicts the consequence of the AGENT's action only.
        pred = model.predict(torch.as_tensor(obs)[None], torch.as_tensor(action)[None])[0]
        pred = pred.numpy()

        # 4. The real world advances (with any external torque added).
        next_obs, _, terminated, truncated, info = env.step(action, ext_torque)

        # 5. Surprise = how wrong the self-model was.
        err_vec = next_obs - pred
        theta = np.arctan2(obs[1], obs[0])
        rows.append([t, theta, obs[2], info["agent_torque"], ext_torque,
                     body_changed, np.linalg.norm(err_vec), *err_vec])

        obs = next_obs
        if terminated or truncated:
            break

    env.close()
    return np.asarray(rows, dtype=np.float64)


def save_csv(log: np.ndarray, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, log, delimiter=",", header=",".join(CSV_COLUMNS),
               comments="", fmt="%.8g")


def run_all_conditions(model) -> dict:
    """Run baseline / body_change / world_event; save each to CSV."""
    logs = {}
    for cond in CONDITIONS:
        print(f"Running condition: {cond}")
        logs[cond] = run_episode(model, cond)
        out = config.RESULTS_DIR / f"{cond}.csv"
        save_csv(logs[cond], out)
        print(f"  saved {len(logs[cond])} steps -> {out}")
    return logs


def err_column(log: np.ndarray) -> np.ndarray:
    """Convenience accessor for the surprise signal column."""
    return log[:, CSV_COLUMNS.index("err_norm")]
