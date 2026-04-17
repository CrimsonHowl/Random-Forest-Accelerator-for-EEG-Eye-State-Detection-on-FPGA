#!/usr/bin/env python3
"""
retrain_on_split.py
===================
Reads "EEG Eye State.arff", performs a stratified 80/20 train-test split,
trains a new Random Forest on the TRAIN set, exports forest.json for HLS,
and writes the TEST set to test_300.csv for the testbench.

WHY THIS FIXES THE ACCURACY BUG:
  The original model was evaluated on the first 300 samples of the ARFF
  which have a different class distribution than the full dataset.
  This script ensures the model's thresholds are learned from data that
  is representative of the test distribution (stratified split).

Usage:
  pip install scikit-learn scipy numpy pandas
  python retrain_on_split.py \
    --arff "EEG Eye State.arff" \
    --test_csv test_300.csv \
    --forest_json forest_split.json \
    --n_test 300 \
    --n_trees 10
"""

import argparse
import json
import sys
import numpy as np
import pandas as pd
from scipy.io import arff as scipy_arff
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import accuracy_score, classification_report

FEATURE_OFFSET = 4100.0
FEATURE_NAMES  = ["AF3","F7","F3","FC5","T7","P7","O1",
                   "O2","P8","T8","FC6","F4","F8","AF4"]


# ─────────────────────────────────────────────────────────────────────────────
#  ARFF loader (handles both scipy and manual parsing)
# ─────────────────────────────────────────────────────────────────────────────
def load_arff(path: str) -> pd.DataFrame:
    try:
        data, meta = scipy_arff.loadarff(path)
        df = pd.DataFrame(data)
        # Decode byte strings
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].apply(
                    lambda x: x.decode() if isinstance(x, bytes) else x
                )
        return df
    except Exception as e:
        print(f"[WARN] scipy arff failed ({e}), trying manual parse...")
        return _manual_arff_parse(path)


def _manual_arff_parse(path: str) -> pd.DataFrame:
    """Simple manual ARFF parser for numeric + class attributes."""
    cols, rows = [], []
    in_data = False
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            if line.lower().startswith("@attribute"):
                parts = line.split()
                cols.append(parts[1].strip("'\""))
            elif line.lower().startswith("@data"):
                in_data = True
            elif in_data:
                rows.append(line.split(","))
    df = pd.DataFrame(rows, columns=cols)
    for c in df.columns[:-1]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df.dropna(inplace=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  Tree serializer → forest.json (nested node format for json_to_trees.py)
# ─────────────────────────────────────────────────────────────────────────────
def _serialize_node(tree_, node_id: int, feature_names: list) -> dict:
    left_child  = tree_.children_left[node_id]
    right_child = tree_.children_right[node_id]

    if left_child == -1:  # leaf
        values = tree_.value[node_id][0].tolist()
        label  = int(np.argmax(values))
        return {"leaf": True, "class_label": label, "value": values}

    feat   = int(tree_.feature[node_id])
    thresh = float(tree_.threshold[node_id])
    fname  = feature_names[feat] if feat < len(feature_names) else f"f{feat}"

    return {
        "leaf":            False,
        "feature":         feat,
        "feature_name":    fname,
        "threshold":       thresh,
        "left":  _serialize_node(tree_, left_child,  feature_names),
        "right": _serialize_node(tree_, right_child, feature_names),
    }


def export_forest_json(rf: RandomForestClassifier,
                       feature_names: list,
                       path: str):
    forest_data = {
        "n_estimators":  rf.n_estimators,
        "n_features":    rf.n_features_in_,
        "feature_names": feature_names,
        "classes":       rf.classes_.tolist(),
        "trees": []
    }
    for estimator in rf.estimators_:
        tree_data = _serialize_node(estimator.tree_, 0, feature_names)
        forest_data["trees"].append(tree_data)

    with open(path, "w") as f:
        json.dump(forest_data, f, indent=2)
    print(f"[retrain] ✓ Exported {len(rf.estimators_)} trees → {path}")


# ─────────────────────────────────────────────────────────────────────────────
#  CSV writer for the testbench
# ─────────────────────────────────────────────────────────────────────────────
def write_test_csv(X_test, y_test, path):
    X_offset = X_test - 4100.0  # apply offset only for testbench
    df = pd.DataFrame(X_offset, columns=FEATURE_NAMES)
    df["eyeDetection"] = y_test.astype(int)
    df.to_csv(path, index=False, float_format="%.6f")
    print(f"[retrain] ✓ Test set ({len(df)} samples) → {path}")


def write_tb_data_snippet(X_test: np.ndarray, y_test: np.ndarray, path: str):
    """Write C++ array initializer rows for direct paste into tb_accuracy.cpp."""
    X_offset = X_test - FEATURE_OFFSET
    lines = []
    lines.append("// Paste this block into tb_accuracy.cpp TEST_DATA[][] array")
    lines.append("// Generated by retrain_on_split.py")
    for i in range(len(X_offset)):
        vals = ", ".join(f"{v:.4f}f" for v in X_offset[i])
        label = int(y_test[i])
        lines.append(f"    {{{vals}, {label}.0f}},  // sample {i}")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"[retrain] ✓ C++ snippet → {path}")


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arff",        default="EEG Eye State.arff")
    ap.add_argument("--test_csv",    default="test_300.csv")
    ap.add_argument("--forest_json", default="forest_split.json")
    ap.add_argument("--tb_snippet",  default="tb_data_snippet.cpp")
    ap.add_argument("--n_test",  type=int, default=300,
                    help="Number of test samples (stratified)")
    ap.add_argument("--n_trees", type=int, default=10,
                    help="Number of trees in the RF")
    ap.add_argument("--max_depth", type=int, default=8,
                    help="Max tree depth (shallower = faster HLS)")
    ap.add_argument("--min_samples_leaf", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    # 1. Load ARFF
    print(f"[retrain] Loading {args.arff} ...")
    df = load_arff(args.arff)
    print(f"[retrain] Loaded {len(df)} samples")

    # Detect label column
    label_col = next((c for c in df.columns
                      if "eye" in c.lower() or "label" in c.lower()
                      or "class" in c.lower()), df.columns[-1])
    feat_cols  = [c for c in df.columns if c != label_col][:NUM_FEATURES]
    print(f"[retrain] Label: {label_col} | Features: {feat_cols}")

    X = df[feat_cols].values.astype(float) - 4100.0  # apply offset to features
    y = df[label_col].values.astype(int)
    print(f"[retrain] Class distribution: "
          f"Open={np.sum(y==0)} ({100*np.mean(y==0):.1f}%)  "
          f"Closed={np.sum(y==1)} ({100*np.mean(y==1):.1f}%)")

    # 2. Stratified split
    test_size = args.n_test / len(X)
    if test_size >= 1.0:
        print(f"[ERROR] n_test={args.n_test} >= dataset size={len(X)}")
        sys.exit(1)

    sss = StratifiedShuffleSplit(n_splits=1, test_size=test_size,
                                 random_state=args.seed)
    train_idx, test_idx = next(sss.split(X, y))
    X_train, y_train = X[train_idx], y[train_idx]
    X_test,  y_test  = X[test_idx],  y[test_idx]
    print(f"[retrain] Train: {len(X_train)} | Test: {len(X_test)}")
    print(f"[retrain] Test class dist: "
          f"Open={np.sum(y_test==0)} Closed={np.sum(y_test==1)}")

    # 3. Train RF
    print(f"[retrain] Training RF: {args.n_trees} trees, max_depth={args.max_depth} ...")
    rf = RandomForestClassifier(
        n_estimators  = args.n_trees,
        max_depth     = args.max_depth,
        min_samples_leaf = args.min_samples_leaf,          # prevents overfitting tiny nodes
        class_weight  = "balanced",    # handles class imbalance
        random_state  = args.seed,
        n_jobs        = -1
    )
    rf.fit(X_train, y_train)

    # 4. Evaluate on test set (sanity check before HLS)
    y_pred_test  = rf.predict(X_test)
    y_pred_train = rf.predict(X_train)
    acc_train = 100.0 * accuracy_score(y_train, y_pred_train)
    acc_test  = 100.0 * accuracy_score(y_test,  y_pred_test)
    print(f"[retrain] Train accuracy: {acc_train:.2f}%")
    print(f"[retrain] Test  accuracy: {acc_test:.2f}%")
    if acc_test < 90.0:
        print(f"[WARN] Test accuracy {acc_test:.1f}% < 90%.")
        print("       Try: --n_trees 20 --max_depth 12")
        print(classification_report(y_test, y_pred_test,
                                    target_names=["Open","Closed"]))

    # 5. Export forest.json
    export_forest_json(rf, feat_cols, args.forest_json)

    # 6. Write test CSV + C++ snippet
    write_test_csv(X_test, y_test, args.test_csv)
    write_tb_data_snippet(X_test, y_test, args.tb_snippet)

    NUM_FEATURES_actual = len(feat_cols)
    print(f"\n[retrain] ══════════════════════════════════════════")
    print(f"[retrain]  NEXT STEPS:")
    print(f"[retrain]  1. python json_to_trees.py --json {args.forest_json} --out_dir D:/IP/files/")
    print(f"[retrain]  2. Paste tb_data_snippet.cpp into tb_accuracy.cpp TEST_DATA[][]")
    print(f"[retrain]  3. Re-run C Simulation in Vivado HLS")
    print(f"[retrain] ══════════════════════════════════════════")


NUM_FEATURES = 14

if __name__ == "__main__":
    main()