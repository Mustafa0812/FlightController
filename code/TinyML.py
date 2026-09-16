"""TinyML Flight Controller Altitude Estimation
Learns to predict ground-truth altitude from IMU and Barometer data.
Includes Physical Clamping, Exponential Moving Average (EMA) Low-Pass Filtering,
Temporal 1D-CNN windowing, and zero-dependency C Header export for Cortex-M microcontrollers.
"""

import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader


# =====================================================================
# 1. Dataset & Data Preprocessing
# =====================================================================

class FlightDataProcessor:
    """Parses PX4/ULog CSV exports, extracts features (X) and ground-truth (Y),
    and handles normalization and sequence formatting.
    """
    def __init__(self, use_relative_baro: bool = True):
        self.use_relative_baro = use_relative_baro
        self.mean_x = None
        self.std_x = None
        self.input_cols = [
            'sensor_combined.accelerometer_m_s2[2]',  # a_z
            'sensor_combined.gyro_rad[0]',            # omega_x
            'sensor_combined.gyro_rad[1]',            # omega_y
            'sensor_combined.gyro_rad[2]',            # omega_z
        ]
        self.baro_col = None
        self.target_col = None

    def _identify_columns(self, df: pd.DataFrame):
        # Barometer feature
        if 'vehicle_air_data.baro_alt_meter' in df.columns:
            self.baro_col = 'vehicle_air_data.baro_alt_meter'
        elif 'sensor_baro.pressure' in df.columns:
            self.baro_col = 'sensor_baro.pressure'
        elif 'vehicle_air_data.baro_pressure_pa' in df.columns:
            self.baro_col = 'vehicle_air_data.baro_pressure_pa'
        else:
            raise KeyError("Could not find a barometer column in CSV!")

        # Target (Ground-Truth)
        if 'distance_sensor.current_distance' in df.columns and df['distance_sensor.current_distance'].notna().any():
            self.target_col = 'distance_sensor.current_distance'
        elif 'vehicle_visual_odometry.z' in df.columns and df['vehicle_visual_odometry.z'].notna().any():
            self.target_col = 'vehicle_visual_odometry.z'
        elif 'vehicle_local_position.dist_bottom' in df.columns:
            self.target_col = 'vehicle_local_position.dist_bottom'
        else:
            raise KeyError("Could not find a ground truth target column (distance_sensor or visual_odometry)!")

    def load_single_csv(self, csv_path: str):
        """Loads a single CSV flight log, parses X and y, and returns clean arrays."""
        df = pd.read_csv(csv_path)
        self._identify_columns(df)

        cols_to_extract = self.input_cols + [self.baro_col, self.target_col]
        clean_df = df[cols_to_extract].dropna().copy()

        # Compute relative barometer altitude to remove atmospheric offset
        if self.use_relative_baro:
            clean_df['baro_feature'] = clean_df[self.baro_col] - clean_df[self.baro_col].iloc[0]
        else:
            clean_df['baro_feature'] = clean_df[self.baro_col]

        feature_cols = self.input_cols + ['baro_feature']
        X = clean_df[feature_cols].to_numpy(dtype=np.float32)
        y = clean_df[self.target_col].to_numpy(dtype=np.float32)

        return X, y, feature_cols, self.target_col

    def fit_normalizer(self, X: np.ndarray):
        """Computes mean and std for standard scaling."""
        self.mean_x = np.mean(X, axis=0)
        self.std_x = np.std(X, axis=0)
        # Prevent division by zero
        self.std_x[self.std_x == 0] = 1.0

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Scales X using stored mean and standard deviation."""
        if self.mean_x is None or self.std_x is None:
            raise ValueError("Normalizer has not been fitted yet!")
        return (X - self.mean_x) / self.std_x


class FlightDataset(Dataset):
    """PyTorch Dataset supporting instantaneous point prediction or sliding windows."""
    def __init__(self, X: np.ndarray, y: np.ndarray, window_size: int = 1):
        self.window_size = window_size
        if window_size == 1:
            self.X = torch.from_numpy(X).float()
            self.y = torch.from_numpy(y).float().unsqueeze(1)
        else:
            # Create sliding windows across time-series: shape (N - window + 1, window_size, features)
            xs, ys = [], []
            for i in range(len(X) - window_size + 1):
                xs.append(X[i : i + window_size])
                ys.append(y[i + window_size - 1])
            self.X = torch.tensor(np.array(xs), dtype=torch.float32)
            self.y = torch.tensor(np.array(ys), dtype=torch.float32).unsqueeze(1)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


# =====================================================================
# 2. Filtering & Post-Processing Adjustments
# =====================================================================

def apply_physical_bounds(y_pred: np.ndarray, min_val: float = 0.0, max_val: float = None) -> np.ndarray:
    """Clamps altitude predictions to logical physical boundaries (e.g. >= 0.0m on ground)."""
    return np.clip(y_pred, a_min=min_val, a_max=max_val)


def apply_ema_filter(y_pred: np.ndarray, alpha: float = 0.25, initial_val: float = None) -> np.ndarray:
    """Lightweight Low-Pass / Exponential Moving Average (EMA) filter:
        y_filtered[t] = alpha * y_raw[t] + (1 - alpha) * y_filtered[t-1]
    Eliminates high-frequency IMU vibration and sensor jitter.
    """
    filtered = np.zeros_like(y_pred)
    if len(y_pred) == 0:
        return filtered
    filtered[0] = initial_val if initial_val is not None else y_pred[0]
    for t in range(1, len(y_pred)):
        filtered[t] = alpha * y_pred[t] + (1.0 - alpha) * filtered[t - 1]
    return filtered


# =====================================================================
# 3. TinyML Model Architectures
# =====================================================================

class TinyAltitudeMLP(nn.Module):
    """Ultra-compact Multilayer Perceptron for microcontroller deployment.
    Input shape: (Batch, Num_Features) -> 241 parameters (~964 bytes).
    Execution time: < 30 microseconds on Cortex-M4/M7.
    """
    def __init__(self, in_features: int = 5, hidden1: int = 16, hidden2: int = 8):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, hidden1),
            nn.ReLU(),
            nn.Linear(hidden1, hidden2),
            nn.ReLU(),
            nn.Linear(hidden2, 1)
        )

    def forward(self, x):
        return self.net(x)


class TinyAltitudeCNN(nn.Module):
    """Lightweight 1D Temporal Convolutional Network for windowed inputs.
    Forces the model to learn smooth temporal features over time.
    Input shape: (Batch, Window_Size, Num_Features).
    """
    def __init__(self, in_features: int = 5, window_size: int = 16, hidden_channels: int = 16):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(in_channels=in_features, out_channels=hidden_channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(in_channels=hidden_channels, out_channels=8, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1)
        )
        self.fc = nn.Linear(8, 1)

    def forward(self, x):
        # x: (Batch, Window, Features) -> transpose to (Batch, Features, Window) for Conv1d
        x = x.transpose(1, 2)
        feat = self.conv(x).squeeze(-1)
        return self.fc(feat)


class CascadedConvHeadNet(nn.Module):
    """Cascaded Neural Network with a 1D Convolutional Output Head:
    1. Base MLP extracts point-wise altitude estimates across a short window of K steps.
    2. A 1D Convolutional filter at the output head directly learns an FIR kernel
       that smooths output jitter while compensating for phase lag during backpropagation.
    Input shape: (Batch, K, In_Features) -> Output: (Batch, 1)
    """
    def __init__(self, in_features: int = 5, hidden1: int = 16, hidden2: int = 8, K: int = 3):
        super().__init__()
        self.K = K
        self.base_mlp = nn.Sequential(
            nn.Linear(in_features, hidden1),
            nn.ReLU(),
            nn.Linear(hidden1, hidden2),
            nn.ReLU(),
            nn.Linear(hidden2, 1)
        )
        # 1D Conv output filter across K temporal steps
        self.conv_head = nn.Conv1d(in_channels=1, out_channels=1, kernel_size=K, bias=True)

    def forward(self, x):
        # x: (Batch, K, Features)
        b, k, f = x.shape
        # Evaluate base MLP across all timesteps in the window
        raw_seq = self.base_mlp(x.view(b * k, f)).view(b, 1, k)
        # Apply 1D Conv filter across time dimension
        out = self.conv_head(raw_seq).squeeze(-1)
        return torch.relu(out)  # Physical clamp >= 0.0m


# =====================================================================
# 4. Model Training & Evaluation
# =====================================================================

def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int = 120,
    lr: float = 0.01,
    weight_decay: float = 1e-4
):
    criterion = nn.HuberLoss()  # Robust to sensor spikes and landing bumps
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=10)

    train_losses = []
    val_losses = []

    for epoch in range(1, epochs + 1):
        model.train()
        running_train_loss = 0.0
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            pred = model(batch_x)
            loss = criterion(pred, batch_y)
            loss.backward()
            optimizer.step()
            running_train_loss += loss.item() * len(batch_y)

        train_loss = running_train_loss / len(train_loader.dataset)

        # Validation phase
        model.eval()
        running_val_loss = 0.0
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                pred = model(batch_x)
                loss = criterion(pred, batch_y)
                running_val_loss += loss.item() * len(batch_y)

        val_loss = running_val_loss / len(val_loader.dataset)
        scheduler.step(val_loss)

        train_losses.append(train_loss)
        val_losses.append(val_loss)

        if epoch % 20 == 0 or epoch == 1:
            print(f"Epoch [{epoch:03d}/{epochs:03d}] | Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f}")

    return train_losses, val_losses


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    mae = np.mean(np.abs(y_pred - y_true))
    rmse = np.sqrt(np.mean((y_pred - y_true) ** 2))
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return {"mae": mae, "rmse": rmse, "r2": r2}


def evaluate_and_refine(
    model: nn.Module,
    X_test: np.ndarray,
    y_test: np.ndarray,
    alpha_ema: float = 0.25,
    clamp_min: float = 0.0
):
    """Evaluates raw model predictions, applies physical clamping and EMA filtering,
    and produces side-by-side performance comparisons and trajectory plots.
    """
    model.eval()
    with torch.no_grad():
        x_tensor = torch.from_numpy(X_test).float()
        raw_preds = model(x_tensor).squeeze(-1).numpy()

    # Refinement Step 1: Physical boundary constraint
    clamped_preds = apply_physical_bounds(raw_preds, min_val=clamp_min)

    # Refinement Step 2: Low-pass Exponential Moving Average filter
    filtered_preds = apply_ema_filter(clamped_preds, alpha=alpha_ema)

    metrics_raw = compute_metrics(y_test, raw_preds)
    metrics_clamped = compute_metrics(y_test, clamped_preds)
    metrics_filtered = compute_metrics(y_test, filtered_preds)

    print("\n" + "=" * 65)
    print("           REFINED MODEL EVALUATION SUMMARY")
    print("=" * 65)
    print(f"{'Stage':<24} | {'MAE (cm)':<10} | {'RMSE (cm)':<10} | {'R^2 Score':<10}")
    print("-" * 65)
    print(f"{'1. Raw MLP Output':<24} | {metrics_raw['mae']*100:<10.2f} | {metrics_raw['rmse']*100:<10.2f} | {metrics_raw['r2']:<10.4f}")
    print(f"{'2. Clamped (>= 0.0m)':<24} | {metrics_clamped['mae']*100:<10.2f} | {metrics_clamped['rmse']*100:<10.2f} | {metrics_clamped['r2']:<10.4f}")
    print(f"{'3. Filtered (EMA a=' + str(alpha_ema) + ')':<24} | {metrics_filtered['mae']*100:<10.2f} | {metrics_filtered['rmse']*100:<10.2f} | {metrics_filtered['r2']:<10.4f}")
    print("=" * 65 + "\n")

    # Generate visual comparison plot
    try:
        plt.figure(figsize=(12, 6))
        plt.plot(y_test, label="Ground Truth (Distance Sensor)", color="black", linewidth=2.5, zorder=4)
        plt.plot(raw_preds, label=f"Raw Prediction (R² = {metrics_raw['r2']:.3f})", color="coral", linestyle=":", alpha=0.7, linewidth=1.5)
        plt.plot(filtered_preds, label=f"Refined (Clamped + EMA α={alpha_ema}, R² = {metrics_filtered['r2']:.3f})", color="royalblue", linewidth=2.0, zorder=3)
        plt.title("Altitude Estimation: Raw vs Clamped + EMA Low-Pass Filtered")
        plt.xlabel("Sample Index (Time Step @ ~5 Hz)")
        plt.ylabel("Altitude Above Ground (m)")
        plt.axhline(0.0, color="gray", linestyle="--", alpha=0.5, label="Ground Level (0.0 m)")
        plt.legend(loc="upper right")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plot_path = os.path.join(os.path.dirname(__file__), "flight_altitude_eval.png")
        plt.savefig(plot_path, dpi=200)
        plt.close()
        print(f"[+] Refined evaluation plot saved to: {plot_path}")
    except Exception as e:
        print(f"Plot saving skipped: {e}")

    return {
        "raw": (raw_preds, metrics_raw),
        "clamped": (clamped_preds, metrics_clamped),
        "filtered": (filtered_preds, metrics_filtered)
    }


# =====================================================================
# 5. Firmware C Header Exporter (with Clamping & EMA for Microcontroller)
# =====================================================================

def export_mlp_to_c_header(
    model: TinyAltitudeMLP,
    processor: FlightDataProcessor,
    output_header_path: str = "altitude_model.h",
    default_alpha: float = 0.25
):
    """Exports trained MLP weights, biases, standard scalers, physical clamping,
    and a stateful Low-Pass Filter directly into a standalone C header.
    """
    state = model.state_dict()
    w0 = state['net.0.weight'].cpu().numpy()  # (hidden1, in_features)
    b0 = state['net.0.bias'].cpu().numpy()    # (hidden1,)
    w2 = state['net.2.weight'].cpu().numpy()  # (hidden2, hidden1)
    b2 = state['net.2.bias'].cpu().numpy()    # (hidden2,)
    w4 = state['net.4.weight'].cpu().numpy()  # (1, hidden2)
    b4 = state['net.4.bias'].cpu().numpy()    # (1,)

    mean_x = processor.mean_x
    std_x = processor.std_x

    def arr_to_c(arr):
        return ", ".join(f"{v:.7e}f" for v in arr.flatten())

    lines = []
    lines.append("/* Auto-generated TinyML Altitude Estimator */")
    lines.append("/* Target: STM32, ESP32, Teensy, Cortex-M microcontrollers */")
    lines.append("#ifndef ALTITUDE_MODEL_H")
    lines.append("#define ALTITUDE_MODEL_H\n")
    lines.append("#include <math.h>\n")
    lines.append(f"#define MODEL_NUM_INPUTS {w0.shape[1]}")
    lines.append(f"#define MODEL_HIDDEN1    {w0.shape[0]}")
    lines.append(f"#define MODEL_HIDDEN2    {w2.shape[0]}")
    lines.append(f"#define DEFAULT_LPF_ALPHA {default_alpha:.2f}f\n")

    lines.append("/* Normalization Parameters */")
    lines.append(f"static const float MEAN_X[{w0.shape[1]}] = {{{arr_to_c(mean_x)}}};")
    lines.append(f"static const float STD_X[{w0.shape[1]}]  = {{{arr_to_c(std_x)}}};\n")

    lines.append("/* Layer 1 (Linear + ReLU) */")
    w0_rows = ",\n".join(f"    {{{arr_to_c(row)}}}" for row in w0)
    lines.append(f"static const float W0[{w0.shape[0]}][{w0.shape[1]}] = {{\n{w0_rows}\n}};")
    lines.append(f"static const float B0[{w0.shape[0]}] = {{{arr_to_c(b0)}}};\n")

    lines.append("/* Layer 2 (Linear + ReLU) */")
    w2_rows = ",\n".join(f"    {{{arr_to_c(row)}}}" for row in w2)
    lines.append(f"static const float W2[{w2.shape[0]}][{w2.shape[1]}] = {{\n{w2_rows}\n}};")
    lines.append(f"static const float B2[{w2.shape[0]}] = {{{arr_to_c(b2)}}};\n")

    lines.append("/* Layer 3 (Output Linear) */")
    lines.append(f"static const float W4[{w4.shape[1]}] = {{{arr_to_c(w4)}}};")
    lines.append(f"static const float B4 = {b4[0]:.7e}f;\n")

    lines.append("""/* Stateful Low-Pass / Exponential Moving Average (EMA) Filter */
typedef struct {
    float alpha;
    float current_val;
    int initialized;
} AltitudeLPF;

static inline void altitude_lpf_init(AltitudeLPF *lpf, float alpha) {
    lpf->alpha = alpha;
    lpf->current_val = 0.0f;
    lpf->initialized = 0;
}

static inline float altitude_lpf_update(AltitudeLPF *lpf, float raw_val) {
    if (!lpf->initialized) {
        lpf->current_val = raw_val;
        lpf->initialized = 1;
    } else {
        lpf->current_val = lpf->alpha * raw_val + (1.0f - lpf->alpha) * lpf->current_val;
    }
    return lpf->current_val;
}

/**
 * Predict vertical altitude with physical boundary clamping (>= 0.0 m).
 * Inputs (raw):
 *   in_features[0] = a_z (sensor_combined.accelerometer_m_s2[2])
 *   in_features[1] = omega_x (sensor_combined.gyro_rad[0])
 *   in_features[2] = omega_y (sensor_combined.gyro_rad[1])
 *   in_features[3] = omega_z (sensor_combined.gyro_rad[2])
 *   in_features[4] = baro_relative (current_baro_alt - takeoff_baro_alt)
 * 
 * Returns: Clamped altitude / distance to ground in meters (>= 0.0m).
 */
static inline float predict_altitude_raw(const float in_features[MODEL_NUM_INPUTS]) {
    float norm_x[MODEL_NUM_INPUTS];
    for (int i = 0; i < MODEL_NUM_INPUTS; i++) {
        norm_x[i] = (in_features[i] - MEAN_X[i]) / STD_X[i];
    }

    /* Hidden Layer 1 */
    float h1[MODEL_HIDDEN1];
    for (int i = 0; i < MODEL_HIDDEN1; i++) {
        float sum = B0[i];
        for (int j = 0; j < MODEL_NUM_INPUTS; j++) {
            sum += W0[i][j] * norm_x[j];
        }
        h1[i] = (sum > 0.0f) ? sum : 0.0f; /* ReLU */
    }

    /* Hidden Layer 2 */
    float h2[MODEL_HIDDEN2];
    for (int i = 0; i < MODEL_HIDDEN2; i++) {
        float sum = B2[i];
        for (int j = 0; j < MODEL_HIDDEN1; j++) {
            sum += W2[i][j] * h1[j];
        }
        h2[i] = (sum > 0.0f) ? sum : 0.0f; /* ReLU */
    }

    /* Output Layer */
    float out = B4;
    for (int j = 0; j < MODEL_HIDDEN2; j++) {
        out += W4[j] * h2[j];
    }

    /* Physical Boundary Clamping: Height above ground cannot be negative */
    if (out < 0.0f) {
        out = 0.0f;
    }

    return out;
}

/**
 * Predict altitude and filter through the EMA Low-Pass Filter in one step.
 */
static inline float predict_altitude_filtered(const float in_features[MODEL_NUM_INPUTS], AltitudeLPF *lpf) {
    float raw_pred = predict_altitude_raw(in_features);
    return altitude_lpf_update(lpf, raw_pred);
}

#endif /* ALTITUDE_MODEL_H */""")

    header_code = "\n".join(lines)
    with open(output_header_path, "w") as f:
        f.write(header_code)
    print(f"[+] Refined Model exported to C header: {output_header_path}")


# =====================================================================
# 6. Main Execution Pipeline
# =====================================================================

def main():
    csv_file = r"C:\Users\musta\Downloads\00_02_49.csv"
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"File not found: {csv_file}")

    print("=" * 65)
    print(f"Loading flight log: {csv_file}")
    processor = FlightDataProcessor(use_relative_baro=True)
    X, y, feature_names, target_name = processor.load_single_csv(csv_file)

    print(f"Input features ({len(feature_names)}): {feature_names}")
    print(f"Target: {target_name}")
    print(f"Total samples: {len(X)}")

    # Time-series Split: 80% train, 20% test (chronological to avoid data leakage)
    split_idx = int(0.8 * len(X))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    # Fit normalizer on training set only
    processor.fit_normalizer(X_train)
    X_train_norm = processor.transform(X_train)
    X_test_norm = processor.transform(X_test)

    # Create PyTorch Datasets (instantaneous MLP)
    train_dataset = FlightDataset(X_train_norm, y_train, window_size=1)
    val_dataset = FlightDataset(X_test_norm, y_test, window_size=1)

    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)

    # Initialize TinyML Model (TinyAltitudeMLP)
    model = TinyAltitudeMLP(in_features=len(feature_names), hidden1=16, hidden2=8)
    num_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"TinyML Model initialized: {num_params} parameters (~{num_params * 4} bytes)")

    # Train
    print("\nTraining TinyML altitude estimator...")
    train_losses, val_losses = train_model(
        model, train_loader, val_loader, epochs=120, lr=0.01
    )

    # Evaluate with Physical Clamping & EMA Low-Pass Filtering
    alpha_filter = 0.25
    results = evaluate_and_refine(
        model, X_test_norm, y_test, alpha_ema=alpha_filter, clamp_min=0.0
    )

    # Export to C Header with Built-in Clamping and LowPassFilter Struct
    header_path = os.path.join(os.path.dirname(__file__), "altitude_model.h")
    export_mlp_to_c_header(model, processor, header_path, default_alpha=alpha_filter)

    # Save trained PyTorch weights
    pt_path = os.path.join(os.path.dirname(__file__), "tiny_altitude_model.pt")
    torch.save({
        'model_state_dict': model.state_dict(),
        'mean_x': processor.mean_x,
        'std_x': processor.std_x,
        'features': feature_names,
        'target': target_name,
        'alpha_filter': alpha_filter
    }, pt_path)
    print(f"[+] PyTorch model saved to: {pt_path}")


if __name__ == "__main__":
    main()
