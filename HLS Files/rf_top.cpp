// rf_top.cpp — Fixed RF Top-Level with Temporal Window Reset
// ============================================================
// BUG 1 FIX: Added reset_t reset parameter.
//   When reset=1, the internal sliding window is cleared and the function
//   returns 0 (invalid / don't-use-this-output).
//   The testbench MUST call rf_top(features, 1) before each new test sample.
//
// Synthesis note: no new hardware cost — reset is a single-bit register clear.

#include "rf_eeg.h"
#include "trees.h"

label_t rf_top(
    const feature_t features[NUM_FEATURES],
    reset_t         reset
) {
#pragma HLS INTERFACE ap_ctrl_none port=return
#pragma HLS INTERFACE ap_none      port=reset
#pragma HLS INTERFACE ap_none      port=features
#pragma HLS ARRAY_PARTITION variable=features complete dim=1

    // ── Temporal fusion sliding window ────────────────────────────────────
    // Static state persists across HLS co-sim calls — this is exactly what
    // caused Bug 1.  The reset port flushes it cleanly.
    static label_t window[WINDOW_SIZE];
    static ap_uint<3> win_idx  = 0;   // 0..WINDOW_SIZE-1
    static ap_uint<3> win_fill = 0;   // how many slots are valid

#pragma HLS RESET variable=window
#pragma HLS RESET variable=win_idx
#pragma HLS RESET variable=win_fill

    // ── Reset path ────────────────────────────────────────────────────────
    if (reset == 1) {
        RESET_LOOP: for (int i = 0; i < WINDOW_SIZE; i++) {
#pragma HLS UNROLL
            window[i] = 0;
        }
        win_idx  = 0;
        win_fill = 0;
        return (label_t)0;   // caller must discard this output
    }

    // ── Inference path ────────────────────────────────────────────────────
    // 1. Single-shot RF prediction (no temporal fusion)
    label_t raw_pred = (label_t)rf_predict(features);

    // 2. Insert into circular window
    window[win_idx] = raw_pred;
    win_idx  = (win_idx  + 1) % WINDOW_SIZE;
    // NEW - explicit cast on both sides
    win_fill = (ap_uint<3>)((win_fill < (ap_uint<3>)WINDOW_SIZE) ?
               (ap_uint<3>)(win_fill + 1) : (ap_uint<3>)WINDOW_SIZE);

    // 3. Majority vote over filled window
    vote_t votes = 0;
    VOTE_LOOP: for (int i = 0; i < WINDOW_SIZE; i++) {
#pragma HLS UNROLL
        if (i < (int)win_fill) {
            votes += (window[i] == 1) ? (vote_t)1 : (vote_t)-1;
        }
    }

    return (label_t)(votes > 0 ? 1 : 0);
}
