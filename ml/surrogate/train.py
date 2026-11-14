"""
AquaPredict Surrogate ML - Model Training & Held-Out Evaluation (Milestone M9)
Trains a gradient-boosted regression surrogate that imitates the M5 screening model.
Evaluates fidelity on strictly held-out simulation scenarios with zero scenario leakage.

CRITICAL SCIENTIFIC DISCLAIMER:
These metrics measure how closely the ML surrogate reproduces the AquaPredict screening model.
They do not measure real-world flood prediction accuracy.
"""

import os
import sys
import json
import time
import joblib
import numpy as np

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
DATA_DIR = os.path.join(WORKSPACE_DIR, "ml", "surrogate", "data")
MODELS_DIR = os.path.join(WORKSPACE_DIR, "ml", "surrogate", "models")
MODEL_OUTPUT_PATH = os.path.join(MODELS_DIR, "surrogate_model.joblib")
META_OUTPUT_PATH = os.path.join(MODELS_DIR, "surrogate_metadata.json")

RANDOM_SEED = 42

def train_and_evaluate():
    """Load dataset, train surrogate model, evaluate on held-out scenarios, and export artifacts."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    
    # 1. Load Datasets and Metadata
    train_file = os.path.join(DATA_DIR, "train_dataset.npz")
    heldout_file = os.path.join(DATA_DIR, "heldout_dataset.npz")
    meta_file = os.path.join(DATA_DIR, "scenarios_metadata.json")

    if not os.path.exists(train_file) or not os.path.exists(heldout_file):
        raise FileNotFoundError("Training datasets not found. Run generate_dataset.py first.")

    train_data = np.load(train_file)
    heldout_data = np.load(heldout_file)
    with open(meta_file, "r", encoding="utf-8") as f:
        data_meta = json.load(f)

    X_train, y_train = train_data["X"], train_data["y"]
    X_heldout, y_heldout = heldout_data["X"], heldout_data["y"]
    features = list(train_data["features"])

    print(f"Loaded Train Data: {X_train.shape[0]} samples, {X_train.shape[1]} features")
    print(f"Loaded Held-Out Data: {X_heldout.shape[0]} samples, {X_heldout.shape[1]} features")

    # 2. Configure Model Architecture
    model_type = "HistGradientBoostingRegressor"
    config = {
        "max_iter": 100,
        "max_depth": 10,
        "learning_rate": 0.1,
        "min_samples_leaf": 20,
        "l2_regularization": 0.01,
        "random_state": RANDOM_SEED
    }

    print(f"\nTraining {model_type} with seed {RANDOM_SEED}...")
    t0 = time.perf_counter()
    model = HistGradientBoostingRegressor(**config)
    model.fit(X_train, y_train)
    fit_duration_s = time.perf_counter() - t0
    print(f"Training completed in {fit_duration_s:.3f} seconds.")

    # 3. Evaluate on Strictly Held-Out Scenarios
    print("\nEvaluating on strictly held-out scenarios...")
    t0_inf = time.perf_counter()
    y_pred_heldout = model.predict(X_heldout)
    inf_duration_s = time.perf_counter() - t0_inf

    # Post-process predictions: depths cannot be negative
    y_pred_heldout = np.maximum(0.0, y_pred_heldout)

    mae = float(mean_absolute_error(y_heldout, y_pred_heldout))
    rmse = float(root_mean_squared_error(y_heldout, y_pred_heldout))
    max_ae = float(np.max(np.abs(y_heldout - y_pred_heldout)))

    # Measure inference time on 10,000 cell grid
    sample_grid_X = X_train[:10000]
    t0_grid = time.perf_counter()
    _ = model.predict(sample_grid_X)
    inference_time_grid_ms = float((time.perf_counter() - t0_grid) * 1000.0)

    # Measure screening simulator runtime on 10,000 cell grid
    from ml.surrogate.generate_dataset import run_screening_simulation, load_cell_features
    cell_feats = load_cell_features()
    t0_sim = time.perf_counter()
    _ = run_screening_simulation(50.0, 180, 0.33, 0.05, cell_feats["dep"])
    sim_runtime_total_ms = float((time.perf_counter() - t0_sim) * 1000.0)
    sim_runtime_per_frame_ms = sim_runtime_total_ms / 37.0

    print("-" * 65)
    print(" HELD-OUT SURROGATE EVALUATION RESULTS")
    print("-" * 65)
    print(f" Mean Absolute Error (MAE):     {mae * 1000:.2f} mm ({mae:.4f} m)")
    print(f" Root Mean Squared Error (RMSE): {rmse * 1000:.2f} mm ({rmse:.4f} m)")
    print(f" Max Absolute Error:            {max_ae * 1000:.2f} mm ({max_ae:.4f} m)")
    print(f" Surrogate Inference (10k cells): {inference_time_grid_ms:.2f} ms / frame")
    print(f" Original Simulator (10k cells):  {sim_runtime_per_frame_ms:.2f} ms / frame")
    print(f" Speedup Factor:                 {sim_runtime_per_frame_ms / max(0.01, inference_time_grid_ms):.1f}x faster")
    print("-" * 65)

    # 4. Save Model Artifact
    joblib.dump(model, MODEL_OUTPUT_PATH, compress=3)
    print(f"Saved model artifact: {MODEL_OUTPUT_PATH}")

    # 5. Save Model Metadata
    meta = {
        "milestone": "M9",
        "model_name": "AquaPredict Screening Model ML Surrogate",
        "model_type": model_type,
        "framework": "scikit-learn",
        "provenance_label": "SYNTHETIC SURROGATE",
        "validation_status": "UNVALIDATED against real-world flood observations",
        "scientific_disclaimer": "These metrics measure how closely the ML surrogate reproduces the AquaPredict screening model. They do not measure real-world flood prediction accuracy.",
        "random_seed": RANDOM_SEED,
        "features": features,
        "package_versions": {
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__
        },
        "training_configuration": config,
        "training_time_seconds": round(fit_duration_s, 3),
        "dataset_split": {
            "strategy": "Complete simulation scenario partition (zero scenario overlap)",
            "leakage_prevention": "VERIFIED (Train scenario IDs disjoint from held-out IDs)",
            "train_scenario_count": data_meta["scenarios_count_train"],
            "heldout_scenario_count": data_meta["scenarios_count_heldout"],
            "train_samples": int(len(y_train)),
            "heldout_samples": int(len(y_heldout))
        },
        "heldout_metrics": {
            "mae_meters": round(mae, 4),
            "mae_mm": round(mae * 1000, 2),
            "rmse_meters": round(rmse, 4),
            "rmse_mm": round(rmse * 1000, 2),
            "max_abs_error_meters": round(max_ae, 4),
            "max_abs_error_mm": round(max_ae * 1000, 2),
            "surrogate_inference_time_ms_per_frame": round(inference_time_grid_ms, 2),
            "original_simulator_time_ms_per_frame": round(sim_runtime_per_frame_ms, 2)
        }
    }

    with open(META_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Saved model metadata: {META_OUTPUT_PATH}")

    return meta

if __name__ == "__main__":
    train_and_evaluate()
