# Rung 3: Surprise attribution on Pendulum-v1

Can one-step prediction error from a learned self-model tell **"my body changed"**
apart from **"the world pushed me"**?

## Run

```bash
pip install -r requirements.txt
cd experiments/surprise_attribution
python main.py
```

The first run trains the forward model (~10 s on CPU) and saves it to `models/`.
Later runs reuse it. Set `RETRAIN = True` in `config.py` to train it again.

Outputs go to `results/`:

| file | contents |
|---|---|
| `baseline.csv`, `body_change.csv`, `world_event.csv` | per-step log: θ, θ̇, agent torque, external torque, body-changed flag, `err_norm` (the surprise signal), per-dimension errors |
| `error_signals.png` | all three error signals on one figure, with the angle below for context |
| `summary_features.csv` | the printed summary table |

## Files

| file | role |
|---|---|
| `config.py` | **every knob**: disturbance step, type, magnitude, duration, windows, MPC and training settings |
| `env_setup.py` | Pendulum-v1 wrapper with `change_body()` (permanent) and `step(action, external_torque)` (transient) |
| `model.py` | MLP forward model `[cos θ, sin θ, θ̇, u] → next obs`, MSE training, save/load. **Swap point for your model.** |
| `controller.py` | sampling MPC that plans with the forward model (stand-in for your MPC) |
| `run_experiment.py` | runs the three conditions, computes surprise each step, writes CSVs |
| `features.py` | pre / immediate / late window means and ratios |
| `plot.py` | the comparison figure |
| `main.py` | runs the whole pipeline |

### Swapping in your model and MPC

- **Model:** the experiment only calls `model.predict(obs[B,3], act[B,1]) -> next_obs[B,3]`
  (torch tensors). Give your net that method, or wrap it, and return it from
  `load_or_train_model()` in `model.py`.
- **MPC:** the experiment only calls `controller.act(obs) -> np.ndarray shape [1]`.
  Replace `MPCController` in `run_experiment.run_episode`.

## Result with the default config (seed 0)

```
condition           pre_mean   imm_mean    peak       late_mean   imm_ratio  late_ratio  still_elevated
baseline            2.63e-03   2.82e-03    5.63e-03   2.79e-03     1.07       1.06       False
body_change         2.63e-03   4.53e-02    1.50e-01   4.57e-02    17.24      17.39       True
world_event         2.63e-03   2.34e-01    9.05e-01   2.44e-03    88.96       0.93       False
```

Both disturbances raise error sharply at onset (`imm_ratio` ≫ 1), so onset alone
cannot attribute the cause. Persistence can: `late_ratio` (error 100–150 steps
after onset relative to before) stays ≈17× for the body change and returns to
≈1× for the world event.

## Design choices you may need to defend

1. **The model only sees the agent's own action.** The shove is never passed to it.
   Surprise is therefore "the outcome differed from what *I* expected from *my* action".
2. **Uniform training coverage.** The model is trained on states and actions sampled
   uniformly (θ ∈ [−π, π], θ̇ ∈ [−8, 8], u ∈ [−2, 2]), not on rollouts. This way,
   when the shove knocks the pendulum somewhere unusual, the model is still accurate
   there. Error after the shove then measures model mismatch, not unfamiliar states.
   If your model was trained only on near-upright MPC data, expect the world-event
   error to stay high while the pendulum is far from upright. That would be a
   confound, not a body change.
3. **Same seed across conditions.** All three runs are identical up to the onset
   step, so any difference afterwards comes from the disturbance.
4. **The external torque bypasses the ±2 N·m clip.** Otherwise the env would silently
   cap the shove (see `env_setup.step`). It enters the dynamics the same way motor torque does.
5. **Length, not mass, is the default body change.** In Pendulum-v1 mass cancels out
   of the gravity term, so a mass change only shows up through applied torque. It is
   still detectable, but weaker (late ratio ≈10 vs ≈17). See the note in `config.py`.
6. **Exploration noise on executed torque** (`ACTION_NOISE_STD`) keeps the body
   exercised. The *noisy* action is what the model is given, so the noise itself
   causes no error. With noise 0.0 the body-change late ratio is still ≈12.
7. **The controller keeps using the stale model** after the body change, as an
   agent with no self-model update would. It still balances the l×1.5 pendulum
   in this setup. With larger changes it may fail, and then the error mixes
   mismatch with unusual states.

## Known limitations

- One seed per condition. Before drawing conclusions, repeat over seeds and over
  several disturbance magnitudes and durations.
- A long or repeated world event (e.g. a constant wind) would look persistent too.
  Persistence separates *transient vs persistent* causes, not *body vs world* in general.
  That ambiguity is the obvious next rung.
- `err_norm` mixes units: cos/sin are unitless and θ̇ is rad/s, and θ̇ errors dominate.
  The per-dimension columns in the CSV let you check this.
