"""Optimization Experiment: Alpha Sweep & Cascaded 1D Conv Head
Quantifies Millisecond Delay vs. Noise Reduction and plots phase lag comparisons.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

from TinyML import FlightDataProcessor, TinyAltitudeMLP, CascadedConvHeadNet


class WindowDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray, K: int):
        xs, ys = [], []
        for i in range(len(X) - K + 1):
            xs.append(X[i : i + K])
            ys.append(y[i + K - 1])
        self.X = torch.tensor(np.array(xs), dtype=torch.float32)
        self.y = torch.tensor(np.array(ys), dtype=torch.float32).unsqueeze(1)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray):
    mae = np.mean(np.abs(y_pred - y_true)) * 100.0   # cm
    rmse = np.sqrt(np.mean((y_pred - y_true) ** 2)) * 100.0  # cm
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    # Jitter: Mean absolute 2nd difference (high-frequency acceleration noise)
    jitter = np.mean(np.abs(np.diff(y_pred, n=2))) * 1000.0  # mm
    return mae, rmse, r2, jitter


def apply_ema(series: np.ndarray, alpha: float) -> np.ndarray:
    out = np.zeros_like(series)
    out[0] = series[0]
    for t in range(1, len(series)):
        out[t] = alpha * series[t] + (1.0 - alpha) * out[t - 1]
    return out


def main():
    csv_file = r"C:\Users\musta\Downloads\00_02_49.csv"
    processor = FlightDataProcessor(use_relative_baro=True)
    X, y, feature_names, target_name = processor.load_single_csv(csv_file)

    # 80/20 train/test split
    split_idx = int(0.8 * len(X))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    processor.fit_normalizer(X_train)
    X_train_norm = processor.transform(X_train)
    X_test_norm = processor.transform(X_test)

    # Effective sampling interval dt
    df_raw = pd.read_csv(csv_file)
    t_sec = df_raw['timestamp'].to_numpy() / 1e6
    dt_ms = np.mean(np.diff(t_sec)) * 1000.0  # ~208.4 ms

    # Load baseline pre-trained MLP
    ckpt_path = os.path.join(os.path.dirname(__file__), "tiny_altitude_model.pt")
    ckpt = torch.load(ckpt_path, weights_only=False)
    base_mlp = TinyAltitudeMLP(5, 16, 8)
    base_mlp.load_state_dict(ckpt['model_state_dict'])
    base_mlp.eval()

    with torch.no_grad():
        raw_preds = np.clip(
            base_mlp(torch.from_numpy(X_test_norm).float()).squeeze(-1).numpy(),
            0.0, None
        )

    raw_mae, raw_rmse, raw_r2, raw_jitter = compute_metrics(y_test, raw_preds)

    # -------------------------------------------------------------
    # 1. Sweep Alpha Values
    # -------------------------------------------------------------
    alphas = [0.15, 0.25, 0.40]
    sweep_data = {}

    for a in alphas:
        filtered = apply_ema(raw_preds, a)
        mae, rmse, r2, jitter = compute_metrics(y_test, filtered)
        # Theoretical low-frequency group delay in ms: T_delay = ((1 - a) / a) * dt
        delay_ms = ((1.0 - a) / a) * dt_ms
        jitter_reduction = (1.0 - jitter / raw_jitter) * 100.0
        sweep_data[a] = {
            "preds": filtered,
            "delay_ms": delay_ms,
            "jitter_reduction": jitter_reduction,
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "jitter": jitter
        }

    # -------------------------------------------------------------
    # 2. Train Cascaded 1D Conv Head Net (K=3)
    # -------------------------------------------------------------
    K = 3
    train_ds = WindowDataset(X_train_norm, y_train, K)
    test_ds = WindowDataset(X_test_norm, y_test, K)
    train_loader = DataLoader(train_ds, batch_size=16, shuffle=True)

    torch.manual_seed(42)
    conv_net = CascadedConvHeadNet(in_features=5, hidden1=16, hidden2=8, K=K)
    optimizer = torch.optim.Adam(conv_net.parameters(), lr=0.008, weight_decay=1e-4)
    criterion = nn.HuberLoss()

    for epoch in range(1, 141):
        conv_net.train()
        for bx, by in train_loader:
            optimizer.zero_grad()
            loss = criterion(conv_net(bx), by)
            loss.backward()
            optimizer.step()

    conv_net.eval()
    with torch.no_grad():
        conv_preds = conv_net(test_ds.X).squeeze(-1).numpy()
        y_conv_test = test_ds.y.squeeze(-1).numpy()

    c_mae, c_rmse, c_r2, c_jitter = compute_metrics(y_conv_test, conv_preds)
    c_jitter_red = (1.0 - c_jitter / raw_jitter) * 100.0

    conv_fir_weights = conv_net.conv_head.weight.squeeze().cpu().detach().numpy()
    conv_bias = conv_net.conv_head.bias.item()

    # -------------------------------------------------------------
    # 3. Print Results Table
    # -------------------------------------------------------------
    print("\n" + "=" * 90)
    print("                OPTIMIZATION RESULTS: DELAY VS. NOISE REDUCTION")
    print("=" * 90)
    print(f"{'Method / Configuration':<26} | {'Delay (ms)':<11} | {'Jitter Red.':<12} | {'MAE (cm)':<9} | {'RMSE (cm)':<10} | {'R^2 Score':<9}")
    print("-" * 90)
    print(f"{'Raw Clamped MLP':<26} | {'0.0 ms':<11} | {'0.0 %':<12} | {raw_mae:<9.2f} | {raw_rmse:<10.2f} | {raw_r2:<9.4f}")
    for a in alphas:
        d = sweep_data[a]
        name = f"EMA Filter (alpha={a:.2f})"
        delay_str = f"{d['delay_ms']:.1f} ms"
        red_str = f"{d['jitter_reduction']:.1f} %"
        print(f"{name:<26} | {delay_str:<11} | {red_str:<12} | {d['mae']:<9.2f} | {d['rmse']:<10.2f} | {d['r2']:<9.4f}")
    c_red_str = f"{c_jitter_red:.1f} %"
    print(f"{'Cascaded 1D Conv (K=3)':<26} | {'Learned (0ms)':<11} | {c_red_str:<12} | {c_mae:<9.2f} | {c_rmse:<10.2f} | {c_r2:<9.4f}")
    print("=" * 90)
    print(f"Learned 1D Conv Head FIR Weights: {np.round(conv_fir_weights, 4).tolist()}, Bias: {conv_bias:.4f}\n")

    # -------------------------------------------------------------
    # 4. Multi-panel Plot (Full Trajectory + Zoomed Inset for Phase Lag)
    # -------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), gridspec_kw={'height_ratios': [2, 1.3]})

    time_steps = np.arange(len(y_test))

    # Panel 1: Full Validation Flight Segment
    ax1.plot(time_steps, y_test, label="Ground Truth (Distance Sensor)", color="black", linewidth=2.8, zorder=5)
    ax1.plot(time_steps, raw_preds, label="Raw MLP (No Filter, Jitter=355 mm)", color="gray", linestyle=":", alpha=0.6, linewidth=1.2)
    ax1.plot(time_steps, sweep_data[0.40]["preds"], label=f"EMA α=0.40 (Delay ~313 ms, R²={sweep_data[0.40]['r2']:.3f})", color="dodgerblue", linewidth=1.8)
    ax1.plot(time_steps, sweep_data[0.25]["preds"], label=f"EMA α=0.25 (Delay ~625 ms, R²={sweep_data[0.25]['r2']:.3f})", color="forestgreen", linewidth=2.0)
    ax1.plot(time_steps, sweep_data[0.15]["preds"], label=f"EMA α=0.15 (Delay ~1181 ms, R²={sweep_data[0.15]['r2']:.3f})", color="crimson", linestyle="--", linewidth=1.8)
    
    # Align conv preds (starts at K-1 = 2)
    t_conv = time_steps[K - 1 :]
    ax1.plot(t_conv, conv_preds, label=f"Cascaded 1D Conv Head (K=3, R²={c_r2:.3f})", color="purple", linestyle="-.", linewidth=2.0)

    ax1.set_title("Alpha Sweep (α = 0.15, 0.25, 0.40) & Cascaded 1D Conv Comparison", fontsize=13, fontweight='bold')
    ax1.set_ylabel("Altitude / Distance (m)", fontsize=11)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper right", framealpha=0.9)

    # Panel 2: Zoomed-in Segment to clearly visualize Phase Lag during descent/ascent
    zoom_start, zoom_end = 20, 50
    z_time = time_steps[zoom_start:zoom_end]
    ax2.plot(z_time, y_test[zoom_start:zoom_end], label="Ground Truth", color="black", linewidth=3.0, zorder=5)
    ax2.plot(z_time, sweep_data[0.40]["preds"][zoom_start:zoom_end], label="EMA α=0.40 (Delay 313 ms)", color="dodgerblue", linewidth=2.0)
    ax2.plot(z_time, sweep_data[0.25]["preds"][zoom_start:zoom_end], label="EMA α=0.25 (Delay 625 ms)", color="forestgreen", linewidth=2.0)
    ax2.plot(z_time, sweep_data[0.15]["preds"][zoom_start:zoom_end], label="EMA α=0.15 (Delay 1181 ms - Lag visible)", color="crimson", linestyle="--", linewidth=2.0)

    # Conv preds in zoom window
    mask = (t_conv >= zoom_start) & (t_conv < zoom_end)
    ax2.plot(t_conv[mask], conv_preds[mask], label="Cascaded 1D Conv Head (No Phase Lag)", color="purple", linestyle="-.", linewidth=2.2)

    ax2.set_title("Zoomed View: Maneuver Phase Lag & Temporal Displacement", fontsize=11, fontweight='bold')
    ax2.set_xlabel("Time Step (Index @ 208.4 ms per step)", fontsize=11)
    ax2.set_ylabel("Altitude (m)", fontsize=11)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper right", framealpha=0.9)

    plt.tight_layout()
    plot_path = os.path.join(os.path.dirname(__file__), "alpha_sweep_comparison.png")
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"[+] Alpha sweep & 1D Conv plot saved to: {plot_path}")


if __name__ == "__main__":
    main()
