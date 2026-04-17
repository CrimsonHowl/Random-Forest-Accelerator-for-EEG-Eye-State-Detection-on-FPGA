// =============================================================================
// modules.cpp  —  Early Exit, Confidence, Temporal Fusion, Feature Monitor
// =============================================================================
#include "rf_eeg.h"
#include "stdint.h"

// =============================================================================
// EARLY EXIT CONTROLLER
//
// Called after every EARLY_EXIT_STEP trees have voted.
// Logic: if the current leader cannot be overtaken by ALL remaining trees
//        voting for the opponent, exit early.
//
// Condition to EXIT:
//   leader_votes > (total_trees / 2) + remaining_trees / 2
//   Equivalently: leader_votes + remaining > total/2 + remaining
//   Simple form used here:
//   leader_votes > (trees_remaining + 1) / 2 + trees_done / 2
//
// More precisely (avoids division):
//   2 * leader_votes > trees_done + trees_remaining
//   which simplifies to: 2 * leader_votes > NUM_ACTIVE_TREES
//
// Here we compute against active_count (trees not masked out).
// =============================================================================
ap_uint<1> early_exit_check(
    vote_cnt_t closed_votes,
    vote_cnt_t open_votes,
    ap_uint<5>  trees_done      // trees evaluated so far (of active trees)
) {
    #pragma HLS INLINE

    ap_uint<6> remaining = (ap_uint<6>)(NUM_TREES - (int)(uint64_t)trees_done);

    // Can the losing side catch up even if all remaining vote for it?
    if (closed_votes > open_votes) {
        // Closed is winning. Can Open ever catch up?
        // open_votes + remaining >= closed_votes  →  don't exit yet
        // open_votes + remaining <  closed_votes  →  EXIT
        if ((open_votes + remaining) < closed_votes)
            return 1; // EXIT EARLY — Closed wins
    } else if (open_votes > closed_votes) {
        if ((closed_votes + remaining) < open_votes)
            return 1; // EXIT EARLY — Open wins
    }
    // Tied or too close — keep evaluating
    return 0;
}

// =============================================================================
// CONFIDENCE ESTIMATOR
// confidence = winner_votes / total_evaluated
// Uses fixed-point division approximated as multiply-by-reciprocal
//
// Reciprocals for denominators 1–25 (precomputed, stored in LUT)
// reciprocal[n] = round(1/n * 256) for n = 1..25
// Multiply vote count by this, then shift right 8 to get conf in [0,1]
// =============================================================================
conf_t compute_confidence(vote_cnt_t winner_votes, ap_uint<5> total_evaluated) {
    #pragma HLS INLINE

    // LUT: recip_lut[i] = floor(256 / (i+1)) for i = 0..24
    static const ap_uint<9> recip_lut[25] = {
        256, 128, 85, 64, 51, 42, 36, 32, 28, 25,
         23,  21, 19, 18, 17, 16, 15, 14, 13, 12,
         12,  11, 11, 10, 10
    };
    #pragma HLS ARRAY_PARTITION variable=recip_lut complete

    ap_uint<5> idx = ((uint64_t)total_evaluated > 0) ? (ap_uint<5>)((uint64_t)total_evaluated - 1) : (ap_uint<5>)0;
    ap_uint<9> recip = recip_lut[(uint64_t)idx];

    // winner_votes * recip / 256  →  fits in ap_fixed<16,2>
    ap_uint<14> raw = (ap_uint<14>)((uint64_t)winner_votes * (uint64_t)recip);
    conf_t conf = (conf_t)((double)(uint64_t)raw / 256.0);  // Q8.8 divide  // divide by 256

    return conf;
}

// =============================================================================
// TEMPORAL FUSION LAYER
//
// Maintains a 5-entry shift register of recent (prediction, confidence) pairs.
// Weighted vote: each sample's vote weighted by its confidence score.
// This naturally suppresses low-confidence noise spikes.
//
// weighted_closed = sum of confidence[i] where prediction[i] == 1
// weighted_open   = sum of confidence[i] where prediction[i] == 0
// output = argmax(weighted_closed, weighted_open)
//
// The shift register is declared static — persists across calls (HW register).
// =============================================================================
ap_uint<1> temporal_fusion(
    ap_uint<1>  new_pred,
    conf_t      new_conf,
    tf_entry_t  window[TEMPORAL_WINDOW]   // caller maintains this buffer
) {
    #pragma HLS INLINE
    #pragma HLS ARRAY_PARTITION variable=window complete

    // Shift window: [0] = oldest, [TEMPORAL_WINDOW-1] = newest
    SHIFT: for (int i = 0; i < TEMPORAL_WINDOW - 1; i++) {
        #pragma HLS UNROLL
        window[i] = window[i + 1];
    }
    window[TEMPORAL_WINDOW - 1].prediction = new_pred;
    window[TEMPORAL_WINDOW - 1].confidence = new_conf;

    // Accumulate weighted votes
    conf_t score_closed = 0;
    conf_t score_open   = 0;

    ACCUMULATE: for (int i = 0; i < TEMPORAL_WINDOW; i++) {
        #pragma HLS UNROLL
        if (window[i].prediction == 1)
            score_closed = score_closed + window[i].confidence;
        else
            score_open   = score_open   + window[i].confidence;
    }

    return (score_closed >= score_open) ? (ap_uint<1>)1 : (ap_uint<1>)0;
}

// =============================================================================
// TREE MASK GENERATOR
//
// Given a bitmask of noisy features (set bit i = feature Fi is noisy),
// returns a 25-bit mask where bit j = 1 means tree j is ACTIVE (safe to use).
//
// A tree is masked out (disabled) if ANY of its key features is noisy.
// TREE_FEAT_MASK[j] & noisy_feat_mask == 0  →  tree j is safe → activate it.
//
// This runs combinationally — one cycle latency.
// =============================================================================
mask_t compute_tree_mask(ap_uint<14> noisy_feat_mask) {
    #pragma HLS INLINE

    mask_t active = 0;
    BUILD_MASK: for (int j = 0; j < NUM_TREES; j++) {
        #pragma HLS UNROLL
        // If no overlap between tree's feature deps and noisy features → keep tree
        active[j] = ((TREE_FEAT_MASK[j] & noisy_feat_mask) == 0) ? 1 : 0;
    }

    // Safety: if ALL trees are masked, un-mask all (fallback — better a noisy answer than none)
    if (active == 0)
        active = (mask_t)-1;  // all 25 bits set

    return active;
}
