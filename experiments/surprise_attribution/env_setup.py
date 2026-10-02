"""
env_setup.py — the Pendulum-v1 environment plus the two kinds of disturbance.

We keep the standard Gymnasium Pendulum-v1 physics untouched and add two
hooks on a thin wrapper:

  * change_body(param, scale)   -> permanently rescale m, l or g
  * step(action, external_torque) -> apply an extra torque the agent did not
                                     command (a "world event")

Keeping both disturbances in one wrapper means the experiment loop is the
same for all three conditions; only the schedule of hook calls differs.
"""

import gymnasium as gym
import numpy as np


class DisturbablePendulum:
    """Pendulum-v1 with hooks for body changes and external torques."""

    def __init__(self, max_episode_steps: int):
        # disable_env_checker: the passive checker would complain when we
        # temporarily lift the torque limit for external torques (see step()).
        self.env = gym.make(
            "Pendulum-v1",
            max_episode_steps=max_episode_steps,
            disable_env_checker=True,
        )
        # .unwrapped is the raw PendulumEnv: it exposes the physics
        # parameters (m, l, g, dt, max_torque, max_speed) and self.state.
        self.raw = self.env.unwrapped
        self.max_torque = float(self.raw.max_torque)   # the agent's limit (2.0)
        self._nominal = {"m": self.raw.m, "l": self.raw.l, "g": self.raw.g}

    # ------------------------------------------------------------------
    def reset(self, seed: int):
        """Reset to a healthy body and a seeded initial state."""
        for k, v in self._nominal.items():      # undo any previous body change
            setattr(self.raw, k, v)
        obs, _ = self.env.reset(seed=seed)
        return obs

    # ------------------------------------------------------------------
    def change_body(self, param: str, scale: float):
        """BODY CHANGE: permanently multiply one physical parameter.

        This edits the simulator's own parameter, so every later step uses the
        new physics. The forward model was trained on the nominal body and is
        NOT updated, so its predictions become systematically wrong.
        """
        if param not in self._nominal:
            raise ValueError(f"param must be one of {list(self._nominal)}")
        setattr(self.raw, param, self._nominal[param] * scale)

    # ------------------------------------------------------------------
    def step(self, action: np.ndarray, external_torque: float = 0.0):
        """Advance one step.

        action           — the torque the AGENT commands (what the forward
                           model is told about). Clipped to ±max_torque as usual.
        external_torque  — WORLD EVENT torque added on top. The model never
                           sees this value.

        Implementation: Pendulum-v1 clips the total torque to ±max_torque
        internally, which would silently swallow a large shove. So we
          1. clip the agent's torque ourselves (same as the env would),
          2. lift the env's limit for this single step,
          3. pass agent_torque + external_torque,
          4. restore the limit.
        The dynamics equation itself is unchanged: an external torque enters
        exactly the way a motor torque would (θ̈ += 3/(m l²) · τ_ext).
        """
        agent_u = float(np.clip(action, -self.max_torque, self.max_torque)[0])
        total_u = np.array([agent_u + external_torque], dtype=np.float32)

        self.raw.max_torque = np.inf
        try:
            obs, reward, terminated, truncated, info = self.env.step(total_u)
        finally:
            self.raw.max_torque = self.max_torque

        info = dict(info, agent_torque=agent_u, external_torque=external_torque)
        return obs, reward, terminated, truncated, info

    # ------------------------------------------------------------------
    def set_state(self, theta: float, theta_dot: float):
        """Teleport the pendulum (used only to sample training data)."""
        self.raw.state = np.array([theta, theta_dot], dtype=np.float64)
        return self.raw._get_obs()

    def close(self):
        self.env.close()


def make_env(max_episode_steps: int) -> DisturbablePendulum:
    return DisturbablePendulum(max_episode_steps)
