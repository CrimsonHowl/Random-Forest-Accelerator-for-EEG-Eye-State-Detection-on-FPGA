// rf_eeg.h — Self-Reconfiguring Random Forest Accelerator
#ifndef RF_EEG_H
#define RF_EEG_H

#include "ap_fixed.h"
#include "ap_int.h"
#include "hls_stream.h"

// ── Feature type ──────────────────────────────────────────────────────────────
typedef ap_fixed<32, 18>    feature_t;

// ── Label / vote types ────────────────────────────────────────────────────────
typedef ap_uint<1>          label_t;        // 0=Open, 1=Closed
typedef ap_int<8>           vote_t;         // signed accumulator
typedef ap_uint<1>          reset_t;        // BUG 1 FIX: window reset port
typedef ap_uint<5>          vote_cnt_t;     // per-class vote counter (up to 25 trees)
typedef ap_fixed<16, 2>     conf_t;         // confidence score [0.0 .. 1.0]
typedef ap_uint<25>         mask_t;         // one bit per tree

// ── Dataset / architecture constants ─────────────────────────────────────────
#define NUM_FEATURES        14
#define FEATURE_OFFSET      4100.0f
#define NUM_TREES           25
#define WINDOW_SIZE         5
#define TEMPORAL_WINDOW     5               // alias used by modules.cpp

// ── Temporal fusion entry ─────────────────────────────────────────────────────
struct tf_entry_t {
    ap_uint<1>  prediction;
    conf_t      confidence;
};

// ── Tree-to-feature dependency mask ──────────────────────────────────────────
// Bit i = 1 means tree j depends on feature i.
// 0x3FFF = all 14 features active → no tree is ever masked out (safe default).
static const ap_uint<14> TREE_FEAT_MASK[NUM_TREES] = {
    0x3FFF, 0x3FFF, 0x3FFF, 0x3FFF, 0x3FFF,
    0x3FFF, 0x3FFF, 0x3FFF, 0x3FFF, 0x3FFF,
    0x3FFF, 0x3FFF, 0x3FFF, 0x3FFF, 0x3FFF,
    0x3FFF, 0x3FFF, 0x3FFF, 0x3FFF, 0x3FFF,
    0x3FFF, 0x3FFF, 0x3FFF, 0x3FFF, 0x3FFF
};

// ── Top-level function ────────────────────────────────────────────────────────
// reset=1 → flush sliding window (discard output)
// reset=0 → normal inference
label_t rf_top(
    const feature_t features[NUM_FEATURES],
    reset_t         reset
);

#endif // RF_EEG_H
