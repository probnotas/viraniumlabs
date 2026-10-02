"""
controller.py — sampling-based MPC that plans with the learned forward model.

This stands in for your existing MPC. The experiment only needs
`controller.act(obs) -> action (np.ndarray shape [1])`, so swap in yours freely.

How it works (random shooting with warm start):
  1. Sample MPC_SAMPLES torque sequences of length MPC_HORIZON.
     Half are fresh uniform samples (exploration), half are the previous best
     plan shifted by one step plus Gaussian noise (exploitation / smoothness).
  2. Roll every sequence forward through the forward model, in one batch.
  3. Score each rollout with the Pendulum-v1 cost
        angle² + 0.1·θ̇² + 0.001·u²     (angle measured from upright).
  4. Execute only the first torque of the best sequence; re-plan next step.

Important for the experiment: the controller uses the SAME (healthy-body)
model whose prediction error we are measuring. After a body change it keeps
planning with a stale self-model — exactly the situation we want to study.
"""

import numpy as np
import torch

import config


class MPCController:
    def __init__(self, model, max_torque: float, seed: int):
        self.model = model
        self.max_torque = max_torque
        self.H = config.MPC_HORIZON
        self.N = config.MPC_SAMPLES
        self.n_warm = int(self.N * config.MPC_WARMSTART_FRAC)
        # Seeded generators -> identical action choices across conditions
        # until the trajectories actually diverge.
        self.gen = torch.Generator().manual_seed(seed)
        self.np_rng = np.random.default_rng(seed)
        self.plan = torch.zeros(self.H)

    def _sample_sequences(self) -> torch.Tensor:
        fresh = (torch.rand(self.N - self.n_warm, self.H, generator=self.gen) * 2 - 1) \
            * self.max_torque
        shifted = torch.cat([self.plan[1:], self.plan[-1:]])          # shift by one
        warm = shifted + config.MPC_WARMSTART_STD * torch.randn(
            self.n_warm, self.H, generator=self.gen)
        seqs = torch.cat([fresh, warm], dim=0)
        return seqs.clamp(-self.max_torque, self.max_torque)          # [N, H]

    @torch.no_grad()
    def act(self, obs: np.ndarray) -> np.ndarray:
        seqs = self._sample_sequences()
        state = torch.as_tensor(obs, dtype=torch.float32).expand(self.N, 3)
        cost = torch.zeros(self.N)
        for t in range(self.H):
            u = seqs[:, t:t + 1]
            state = self.model.predict(state, u)
            theta = torch.atan2(state[:, 1], state[:, 0])   # 0 = upright
            cost += theta ** 2 + 0.1 * state[:, 2] ** 2 + 0.001 * u[:, 0] ** 2

        best = torch.argmin(cost)
        self.plan = seqs[best].clone()
        u0 = float(self.plan[0])

        # Exploration noise on the EXECUTED action (see config.ACTION_NOISE_STD).
        # The noisy action is what gets logged and fed to the forward model,
        # so the noise itself never causes prediction error.
        u0 += config.ACTION_NOISE_STD * self.np_rng.standard_normal()
        return np.array([np.clip(u0, -self.max_torque, self.max_torque)], np.float32)
