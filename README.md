# Random Forest Accelerator for EEG Eye State Detection on FPGA

> **Detecting driver drowsiness in 640 nanoseconds using a hardware-accelerated Random Forest on the PYNQ-Z2 (Zynq-7020) FPGA.**

---

## Table of Contents
- [Overview](#overview)
- [Key Results](#key-results)
- [System Architecture](#system-architecture)
- [Hardware Techniques](#hardware-techniques)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Setup & Usage](#setup--usage)
- [Dataset](#dataset)
- [HLS Implementation](#hls-implementation)
- [Vivado Block Design](#vivado-block-design)
- [PYNQ Deployment](#pynq-deployment)
- [Performance Benchmark](#performance-benchmark)
- [Bugs Fixed](#bugs-fixed)

---

## Overview

This project accelerates a **15-tree Random Forest classifier** for real-time EEG-based eye state detection on an FPGA. The classifier distinguishes between **Eyes Open** and **Eyes Closed** from 14-channel EEG signals, enabling drowsiness detection for driver safety systems.

The system is implemented as a custom IP on the **PL (Programmable Logic)** side of the Zynq-7020 SoC, communicating with the **PS (ARM Cortex-A9)** via AXI bus. The FPGA core achieves **640ns inference latency** — a **736× speedup** over equivalent ARM software.

**Why FPGA?**
At 100 km/h, 50ms of ARM inference time = 1.4 meters of undetected drift. The FPGA brings this down to **0.019mm** per inference.

---

## Key Results

| Metric | Value |
|--------|-------|
| **Hardware Accuracy** | **91.67%** (275/300) |
| Precision | 91.67% |
| Recall (Sensitivity) | 89.63% |
| Specificity | 93.33% |
| F1-Score | 90.64% |
| **FPGA Core Latency** | **640 ns** (64 cycles @ 100MHz) |
| **Speedup vs ARM CPU** | **736×** faster |
| LUT Utilization | 43% (Vivado) / 88% (HLS estimate) |
| BRAM Utilization | 46% |
| FF Utilization | 37% |
| Timing | 8.54ns (target: 10ns) ✓ |

---

## System Architecture

```
EEG Headset (14 channels, 128 Hz)
          │
          ▼  raw µV values
  ARM Cortex-A9 (PS)
    ├── Subtract 4100.0 µV offset
    ├── Pack into 14 × 32-bit features
    └── Write to AXI register map
          │
          ▼
  FPGA Fabric (PL) — rf_top
    ├── Reset temporal window (reset=1)
    └── Inference (reset=0)
          │
          ├── tree_0(feat) ─┐
          ├── tree_1(feat)  │ majority
          ├── ...           ├── vote
          └── tree_14(feat)─┘
                │
                ▼
        Temporal Fusion
        (5-sample weighted window)
                │
                ▼
        label_t → 0=Open / 1=Closed
                │
                ▼
  ARM Decision Logic
    ├── < 1s closed  → ignore (normal blink)
    ├── 1–2s closed  → vibration warning
    └── > 2s closed  → brake signal
```

---

## Hardware Techniques

### 1. BRAM-Based Tree Storage
Instead of compiling trees as LUT-based if-else chains (which caused **543% LUT overflow**), each tree is stored as a flat node struct array in BRAM. A small traversal loop walks each array from root to leaf.

```
Node struct (per BRAM entry):
  threshold  : ap_fixed<32,18>  — split value
  left       : ap_uint<16>      — left child index
  right      : ap_uint<16>      — right child index
  feature    : ap_uint<4>       — which of 14 channels
  is_leaf    : ap_uint<1>       — stop flag
  label      : ap_uint<1>       — 0=Open, 1=Closed
```

**Impact:** LUT 543% → 88% ✓ (design now fits on chip)

---

### 2. Temporal Fusion (Sliding Window)
A 5-sample history of predictions is maintained. Confidence-weighted majority voting suppresses single-sample noise artifacts and electrode artifacts.

```
Window state: [(pred, conf), (pred, conf), ...]
score_closed = Σ conf[i] where pred[i] == 1
score_open   = Σ conf[i] where pred[i] == 0
output = argmax(score_closed, score_open)
```

**Impact:** False alarm suppression from noise spikes.

---

### 3. Early Exit Controller
After each tree votes, checks if the current winner is mathematically unbeatable. Stops early if remaining trees cannot change the outcome.

```
After tree k: remaining = 15 - k
If (losing_votes + remaining) < winning_votes → EXIT EARLY
```

**Impact:** Reduces average latency for clear-cut predictions.

---

### 4. Confidence Estimation
`confidence = winner_votes / total_trees_evaluated`

High confidence (≥0.85) → output directly.
Moderate confidence (0.65–0.84) → pass through temporal fusion.
Low confidence (<0.65) → flag as ambiguous.

**Impact:** Reduces false alarms on borderline predictions.

---

### 5. Tree Masking (Feature Reliability)
Each tree has a 14-bit feature dependency mask. When an electrode becomes noisy, trees depending on that channel are excluded from voting.

```cpp
// Tree j active if no overlap with noisy channels
active[j] = ((TREE_FEAT_MASK[j] & noisy_feat_mask) == 0);
```

**Impact:** Graceful degradation when electrodes are loose.

---

## Repository Structure

```
rf-eeg-fpga/
├── README.md
│
├── HLS Files/
│   ├── rf_eeg.h
│   ├── rf_top.cpp
│   ├── modules.cpp
│   ├── trees.h
│   └── tb_accuracy.cpp
│  
├── Py_Files/
│   ├── retrain_on_split.py       
│   ├── jsontoh.py                
│   └── csv_to_tb.py              
│
└── Pynq/
    ├── Final_RF.ipynb
    └── test_300.csv
```

> **Note:** `trees.cpp` and `forest_split.json` are not included due to file size.
> Run `retrain_on_split.py` to regenerate them.

---

## Prerequisites

### Software
| Tool | Version |
|------|---------|
| Vivado HLS | 2017.4 |
| Vivado | 2017.4 |
| Python | 3.7+ |
| scikit-learn | ≥ 0.24 |
| scipy | any |
| pandas | any |
| numpy | any |

### Hardware
- PYNQ-Z2 board (xc7z020clg400-1)
- PYNQ SD card with PYNQ v2.5+ image
- Ethernet cable
- Micro USB cable

---

## Setup & Usage

### Step 1 — Train the Model
```bash
pip install scikit-learn scipy pandas numpy

python retrain_on_split.py \
  --arff "EEG Eye State.arff" \
  --n_trees 15 \
  --max_depth 14 \
  --n_test 300 \
  --seed 999
```
Outputs: `forest_split.json`, `test_300.csv`

---

### Step 2 — Generate HLS trees.cpp
The `forest_split.json` is converted to BRAM-based HLS C++ using a custom converter. Each tree becomes a flat node array with a traversal loop — this is what enables the design to fit within the FPGA's resource limits.

```bash
Run Json to HLS converter
python python/jsontoh.py \
  --json forest_split.json \
  --out_dir hls/
```

---

### Step 3 — Patch Testbench
```bash
python csv_to_tb.py \
  --csv test_300.csv \
  --out hls/tb/tb_accuracy.cpp
```

---

### Step 4 — Vivado HLS
1. Open Vivado HLS 2017.4
2. Create project → add all files from `hls/`
3. Set top function: `rf_top`
4. Target part: `xc7z020clg400-1`
5. Run **C Simulation** → verify 92.33% accuracy
6. Run **C Synthesis** → verify LUT/BRAM fit

Expected synthesis results:
```
LUT:    88%  (46,985 / 53,200)
BRAM:   46%  (130 / 280)
FF:     37%  (40,071 / 106,400)
Timing: 8.54ns (target 10ns) ✓
```

---

### Step 5 — Vivado Block Design

1. Create new RTL project → part `xc7z020clg400-1`
2. Add all `.v` files from `solution1/syn/verilog/`
3. Create block design → add Zynq PS + rf_top + 9 AXI GPIOs
4. Run Implementation → Generate Bitstream

---

### Step 6 — PYNQ Deployment
```bash
# Copy to PYNQ (via Jupyter file browser or SCP)
scp rf_system.bit xilinx@192.168.2.99:/home/xilinx/
scp rf_system.hwh xilinx@192.168.2.99:/home/xilinx/
scp pynq/test_300.csv xilinx@192.168.2.99:/home/xilinx/
```

Open `http://192.168.2.99` → upload `Final_RF.ipynb` → run all cells.

---

## Dataset

**EEG Eye State** — UCI Machine Learning Repository

| Property | Value |
|----------|-------|
| Samples | 14,980 |
| Channels | 14 EEG electrodes |
| Label | 0=Open (55.1%), 1=Closed (44.9%) |
| Sample rate | 128 Hz |
| Format | ARFF |

**Channels:** AF3, F7, F3, FC5, T7, P7, O1, O2, P8, T8, FC6, F4, F8, AF4

**Preprocessing:** Subtract offset 4100.0 µV from all channels before inference.
The model is trained on offset-subtracted values — passing raw µV values
will reduce accuracy to ~55% (random).

---

## HLS Implementation

### Top-Level Function
```cpp
label_t rf_top(
    const feature_t features[NUM_FEATURES],  // 14 EEG channels
    reset_t         reset                     // 1=flush window, 0=infer
);
```

### Key Type Definitions
```cpp
typedef ap_fixed<32, 18>    feature_t;    // EEG value (18 int + 14 frac bits)
typedef ap_uint<1>          label_t;      // 0=Open, 1=Closed
typedef ap_uint<1>          reset_t;      // window reset
typedef ap_fixed<16, 2>     conf_t;       // confidence score
typedef ap_uint<25>         mask_t;       // tree activity mask

#define NUM_FEATURES  14
#define NUM_TREES     15
#define WINDOW_SIZE    5
```

---

## Vivado Block Design

```
rf_system:
  ├── processing_system7_0    Zynq PS (ARM + DDR)
  ├── rf_top_0                RF accelerator
  ├── axi_gpio_0 to _6        14 feature inputs (dual-channel)
  ├── axi_gpio_ctrl           Reset control
  ├── axi_gpio_result         Prediction output
  ├── axi_interconnect_0      AXI bus
  └── rst_ps7_0_100M          Reset controller
```

---

## PYNQ Deployment

### Core Inference Function
```python
def predict_hardware(raw_features, offsets):
    features = [raw_features[i] + offsets[i] for i in range(14)]

    # Reset temporal window
    rf_ip.register_map.reset_V = 1
    rf_ip.write(0x00, 0x01)
    while not (rf_ip.read(0x00) & 0x2): pass

    # Load 14 features
    for i, val in enumerate(features):
        setattr(rf_ip.register_map, f"features_{i}_V",
                float_to_fixed(val))

    # Pump window 5× (temporal fusion)
    rf_ip.register_map.reset_V = 0
    res = 0
    for _ in range(5):
        rf_ip.write(0x00, 0x01)
        while not (rf_ip.read(0x00) & 0x2): pass
        res = int(rf_ip.register_map.ap_return.ap_return)
    return res


def float_to_fixed(val):
    """ap_fixed<32,18>: scale by 2^14 = 16384"""
    scaled = int(val * 16384)
    if scaled < 0:
        scaled = (1 << 32) + scaled
    return scaled & 0xFFFFFFFF
```

---

## Performance Benchmark

| Platform | Time (300 samples) | Per Sample |
|----------|-------------------|------------|
| Software (ARM CPU) | 0.1414s | 0.47ms |
| Hardware (FPGA System) | 1.62s | 5.40ms |
| **Hardware (FPGA Core)** | **0.000192s** | **640ns** |
| **Core Speedup** | **736× faster than CPU** | |

> The FPGA system time is higher than software due to Python AXI GPIO
> overhead (~5ms per sample). The FPGA core itself is 736× faster.
> In a production deployment using DMA instead of GPIO, system time
> would approach the 640ns core time.

---

## Bugs Fixed

### Bug 1 — Temporal Window State Bleed
**Problem:** The 5-sample sliding window had persistent static state.
The testbench called `rf_top()` 300 times without resetting — state from
sample N contaminated sample N+1. Accuracy: 62.7% / 60%.

**Fix:** Added `reset_t reset` port. Call `rf_top(feat, 1)` before each
new test sample to flush the window.

---

### Bug 2 — Feature Offset Mismatch
**Problem:** Model trained on offset-subtracted values but testbench
passed raw µV values. Every threshold comparison failed. Accuracy: 55%.

**Fix:** Apply `raw_uV - 4100.0` offset during training AND at inference.
Values in `test_300.csv` are already offset-subtracted.

---

## Real-World Impact

At 100 km/h with a 128Hz EEG headset:

| Event | Time | Distance |
|-------|------|----------|
| FPGA inference | 640ns | 0.019mm |
| System latency | 5.4ms | 15cm |
| Alert fires (1s threshold) | 1.0s | 27.8m |

Without this system, a drowsy driver may drift for 3–5 seconds
(83–138 meters) before self-correcting. The 1-second vibration alert
cuts this to 27.8 meters — potentially preventing a collision.

---


