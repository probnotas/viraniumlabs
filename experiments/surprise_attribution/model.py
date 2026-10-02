"""
model.py — the learned forward model ("self-model") of the HEALTHY pendulum.

    input : [cos θ, sin θ, θ̇, torque]      (4 numbers)
    output: [cos θ', sin θ', θ̇']            (predicted next observation)
    loss  : MSE against the true next observation

------------------------------------------------------------------------
SWAPPING IN YOUR OWN MODEL
------------------------------------------------------------------------
The rest of the code only ever calls

    model.predict(obs, act) -> next_obs        (torch tensors, batched)
        obs : float32 tensor [B, 3]
        act : float32 tensor [B, 1]
        out : float32 tensor [B, 3]

and `load_or_train_model()`. To use your model, either
  (a) give your nn.Module a `predict` method with that signature and return
      it from `load_or_train_model()`, or
  (b) wrap it:  class Wrapper: def predict(self, o, a): return my_net(torch.cat([o, a], -1))
Nothing else needs to change.
------------------------------------------------------------------------
"""

import numpy as np
import torch
import torch.nn as nn

import config
from env_setup import make_env


class ForwardModel(nn.Module):
    """MLP that predicts the next observation.

    Two standard tricks, both of which keep the I/O contract above intact:

    1. Residual prediction. Internally the net outputs Δ = next_obs − obs and
       we return obs + Δ. One step is only 0.05 s, so next_obs ≈ obs; learning
       the small change is much easier than re-learning the identity map.
    2. Fixed input/output scaling. θ̇ ranges over ±8 while cos/sin are in ±1;
       we standardise with statistics computed from the training data so all
       inputs/targets are on a similar scale. The stats are stored as buffers
       so they are saved/loaded with the weights.
    """

    def __init__(self, hidden_sizes=config.HIDDEN_SIZES):
        super().__init__()
        layers, d_in = [], 4
        for h in hidden_sizes:
            layers += [nn.Linear(d_in, h), nn.ReLU()]
            d_in = h
        layers.append(nn.Linear(d_in, 3))
        self.net = nn.Sequential(*layers)

        # Normalisation statistics (set by fit_normalizer before training).
        self.register_buffer("in_mean", torch.zeros(4))
        self.register_buffer("in_std", torch.ones(4))
        self.register_buffer("out_mean", torch.zeros(3))
        self.register_buffer("out_std", torch.ones(3))

    def fit_normalizer(self, x: torch.Tensor, delta: torch.Tensor):
        self.in_mean.copy_(x.mean(0))
        self.in_std.copy_(x.std(0) + 1e-6)
        self.out_mean.copy_(delta.mean(0))
        self.out_std.copy_(delta.std(0) + 1e-6)

    def forward_delta_normalized(self, obs, act):
        """Raw network output (normalised Δ). Used for the training loss."""
        x = torch.cat([obs, act], dim=-1)
        return self.net((x - self.in_mean) / self.in_std)

    def predict(self, obs: torch.Tensor, act: torch.Tensor) -> torch.Tensor:
        """Predicted next observation (un-normalised). THE interface."""
        delta = self.forward_delta_normalized(obs, act) * self.out_std + self.out_mean
        return obs + delta


# ---------------------------------------------------------------------------
# Training data
# ---------------------------------------------------------------------------
def collect_transitions(n: int, seed: int):
    """Sample (obs, action, next_obs) from the HEALTHY pendulum.

    We do NOT roll out episodes. Instead each sample teleports the pendulum to
    a uniformly random state (θ ∈ [−π, π], θ̇ ∈ [−8, 8]), applies a uniformly
    random torque (u ∈ [−2, 2]) and records the result.

    Why: we want prediction error during the experiment to measure MODEL
    MISMATCH (body ≠ self-model), not "the pendulum wandered into a state the
    model never saw". Uniform coverage of the whole state-action space means a
    world-event shove that throws the pendulum somewhere unusual still lands
    in well-trained territory — so its error can genuinely decay back to
    baseline once the shove ends.
    """
    rng = np.random.default_rng(seed)
    env = make_env(max_episode_steps=10)
    env.reset(seed=seed)
    max_speed = float(env.raw.max_speed)

    obs_buf = np.zeros((n, 3), np.float32)
    act_buf = np.zeros((n, 1), np.float32)
    nxt_buf = np.zeros((n, 3), np.float32)
    for i in range(n):
        th = rng.uniform(-np.pi, np.pi)
        thd = rng.uniform(-max_speed, max_speed)
        u = rng.uniform(-env.max_torque, env.max_torque, size=1).astype(np.float32)
        obs_buf[i] = env.set_state(th, thd)
        nxt_buf[i], *_ = env.step(u)
        act_buf[i] = u
    env.close()
    return obs_buf, act_buf, nxt_buf


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------
def train_model(seed: int = config.SEED, verbose: bool = True) -> ForwardModel:
    torch.manual_seed(seed)
    obs, act, nxt = (torch.from_numpy(a) for a in
                     collect_transitions(config.TRAIN_SAMPLES, seed + 12345))

    # Train/validation split so we can report held-out one-step error.
    n_val = int(len(obs) * config.VAL_FRACTION)
    perm = torch.randperm(len(obs))
    val_idx, tr_idx = perm[:n_val], perm[n_val:]

    model = ForwardModel()
    model.fit_normalizer(torch.cat([obs, act], -1)[tr_idx], (nxt - obs)[tr_idx])
    opt = torch.optim.Adam(model.parameters(), lr=config.LEARNING_RATE)

    def target(idx):  # normalised Δ — what the network directly outputs
        return ((nxt - obs)[idx] - model.out_mean) / model.out_std

    for epoch in range(config.TRAIN_EPOCHS):
        model.train()
        for b in torch.split(tr_idx[torch.randperm(len(tr_idx))], config.BATCH_SIZE):
            loss = nn.functional.mse_loss(
                model.forward_delta_normalized(obs[b], act[b]), target(b))
            opt.zero_grad()
            loss.backward()
            opt.step()

        if verbose and (epoch % 10 == 0 or epoch == config.TRAIN_EPOCHS - 1):
            model.eval()
            with torch.no_grad():
                # Report validation error in the same units as the experiment:
                # mean ‖actual_next − predicted_next‖ in observation space.
                pred = model.predict(obs[val_idx], act[val_idx])
                err = (nxt[val_idx] - pred).norm(dim=-1).mean().item()
            print(f"  epoch {epoch:3d}  train MSE(norm Δ) {loss.item():.2e}  "
                  f"val one-step error {err:.2e}")
    model.eval()
    return model


def load_or_train_model() -> ForwardModel:
    """Load the saved forward model, or train + save one if absent.

    >>> Replace the body of this function to plug in your own model. <<<
    """
    if config.MODEL_PATH.exists() and not config.RETRAIN:
        model = ForwardModel()
        model.load_state_dict(torch.load(config.MODEL_PATH, weights_only=True))
        model.eval()
        print(f"Loaded forward model from {config.MODEL_PATH}")
        return model

    print("Training forward model on the healthy pendulum ...")
    model = train_model()
    config.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), config.MODEL_PATH)
    print(f"Saved forward model to {config.MODEL_PATH}")
    return model
