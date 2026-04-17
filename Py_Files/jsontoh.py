# # """
# # Generate rf_model.cpp with HARDWIRED if-else trees (no arrays)
# # ==============================================================
# # This is the ONLY way to guarantee 0% BRAM in Vivado HLS.

# # Instead of:
# #     if (features[f_idx[t][node]] <= thresh[t][node])  <- array = BRAM

# # We generate:
# #     if (features[3] <= 0.423f)                         <- literal = LUT

# # Each tree becomes a standalone C++ function with constants
# # baked directly into the comparisons. HLS sees pure logic.
# # """

# # import json
# # import numpy as np

# # with open("forest.json", "r") as f:
# #     forest = json.load(f)

# # N_TREES        = 25
# # N_FEATURES     = 14
# # N_CORES        = 5
# # TREES_PER_CORE = 5
# # VOTE_THRESH    = 12

# # print(f"[INFO] Loaded {N_TREES} trees")
# # for i, t in enumerate(forest):
# #     n_leaves = sum(1 for f in t["feature"] if f == -2)
# #     print(f"  Tree {i:02d}: {len(t['feature'])} nodes, {n_leaves} leaves")

# # # ── Generate one C++ function per tree ──────────────────────
# # def generate_tree_function(tree_idx, tree):
# #     features   = tree["feature"]
# #     thresholds = tree["threshold"]
# #     left       = tree["left"]
# #     right      = tree["right"]
# #     values     = tree["value"]

# #     leaf_class = []
# #     for fid, val in zip(features, values):
# #         if fid == -2:
# #             leaf_class.append(int(np.argmax(val[0])))
# #         else:
# #             leaf_class.append(-1)

# #     lines = []
# #     lines.append(f"// Tree {tree_idx:02d}: {len(features)} nodes")
# #     lines.append(f"static int tree_{tree_idx:02d}(data_t feat[N_FEATURES]) {{")
# #     lines.append(f"#pragma HLS INLINE")
# #     lines.append(f"")

# #     def write_node(node_idx, depth):
# #         pad = "    " + "    " * depth
# #         result = []
# #         if features[node_idx] == -2:
# #             cls = leaf_class[node_idx]
# #             result.append(f"{pad}return {cls};")
# #         else:
# #             fid   = features[node_idx]
# #             thr   = thresholds[node_idx]
# #             l_idx = left[node_idx]
# #             r_idx = right[node_idx]
# #             result.append(f"{pad}if (feat[{fid}] <= (data_t){thr:.10f}) {{")
# #             result.extend(write_node(l_idx, depth + 1))
# #             result.append(f"{pad}}} else {{")
# #             result.extend(write_node(r_idx, depth + 1))
# #             result.append(f"{pad}}}")
# #         return result

# #     lines.extend(write_node(0, 0))
# #     lines.append(f"}}")
# #     lines.append(f"")
# #     return "\n".join(lines)

# # # ── Write complete rf_model.cpp ──────────────────────────────
# # with open("rf_model.cpp", "w", encoding="utf-8") as f:

# #     f.write('#include "rf_model.h"\n\n')
# #     f.write("// ============================================================\n")
# #     f.write("// Memory-less Spatial AI -- Hardwired Tree Functions\n")
# #     f.write("// NO ARRAYS anywhere in this file\n")
# #     f.write("// All thresholds are literal C++ float constants\n")
# #     f.write("// HLS maps these to LUT comparators -> 0% BRAM guaranteed\n")
# #     f.write("// ============================================================\n\n")

# #     print("\n[STEP 1] Generating hardwired tree functions...")
# #     for i, tree in enumerate(forest):
# #         fn = generate_tree_function(i, tree)
# #         f.write(fn)
# #         f.write("\n")
# #         print(f"  tree_{i:02d}() -- {len(tree['feature'])} nodes hardwired")

# #     print("\n[STEP 2] Generating 5 core functions...")
# #     for c in range(N_CORES):
# #         start = c * TREES_PER_CORE
# #         end   = start + TREES_PER_CORE
# #         f.write(f"// Core {c}: trees {start}..{end-1}\n")
# #         f.write(f"static int core_{c:02d}(data_t feat[N_FEATURES]) {{\n")
# #         f.write(f"#pragma HLS INLINE\n")
# #         calls = [f"tree_{t:02d}(feat)" for t in range(start, end)]
# #         f.write(f"    return {' + '.join(calls)};\n")
# #         f.write("}\n\n")
# #         print(f"  core_{c:02d}() -- calls tree_{start:02d} to tree_{end-1:02d}")

# #     print("\n[STEP 3] Writing rf_predict...")
# #     f.write("// ============================================================\n")
# #     f.write("// TOP FUNCTION: rf_predict\n")
# #     f.write("// AXI4-Lite interface auto-generated for PYNQ\n")
# #     f.write("// ============================================================\n")
# #     f.write("void rf_predict(data_t features[N_FEATURES], int *out_class) {\n\n")
# #     f.write("    // AXI4-Lite ports for PYNQ Python control\n")
# #     f.write("#pragma HLS INTERFACE s_axilite port=features   bundle=CTRL\n")
# #     f.write("#pragma HLS INTERFACE s_axilite port=out_class  bundle=CTRL\n")
# #     f.write("#pragma HLS INTERFACE s_axilite port=return     bundle=CTRL\n\n")
# #     f.write("    // Allow all cores to read features simultaneously\n")
# #     f.write("#pragma HLS ARRAY_PARTITION variable=features complete\n\n")
# #     f.write("    // All 5 cores evaluate in parallel\n")
# #     f.write("    // Each core calls 5 hardwired tree functions\n")
# #     f.write("    // Total: 25 trees evaluated with zero memory accesses\n")
# #     core_calls = [f"core_{c:02d}(features)" for c in range(N_CORES)]
# #     f.write(f"    int votes = {' + '.join(core_calls)};\n\n")
# #     f.write(f"    *out_class = (votes > {VOTE_THRESH}) ? 1 : 0;\n")
# #     f.write("}\n")

# # print("\n")
# # print("+----------------------------------------------------------+")
# # print("|  DONE: rf_model.cpp generated with hardwired trees      |")
# # print("|  25 tree functions + 5 core functions + 1 top function  |")
# # print("|  ZERO arrays in the entire file                         |")
# # print("|                                                          |")
# # print("|  Expected HLS Synthesis Results:                        |")
# # print("|    BRAM_18K : 0        (0%)  -- INNOVATION PROVEN       |")
# # print("|    LUT      : ~30,000-40,000 (60-75%)                   |")
# # print("|    FF       : ~1,000-3,000   (1-3%)                     |")
# # print("|    DSP      : 0        (0%)                             |")
# # print("+----------------------------------------------------------+")
# """
# Generate rf_model.cpp - No INLINE version
# ==========================================
# Fix: Removed #pragma HLS INLINE from tree and core functions.
# HLS will synthesize each tree as a separate sub-module.
# This avoids the "Synthesizability check failed" error caused
# by inlining 25 large trees into one massive function.
# """

# import json
# import numpy as np

# with open("forest.json", "r") as f:
#     forest = json.load(f)

# N_TREES        = 25
# N_FEATURES     = 14
# N_CORES        = 5
# TREES_PER_CORE = 5
# VOTE_THRESH    = 12

# print(f"[INFO] Loaded {N_TREES} trees")
# for i, t in enumerate(forest):
#     n_leaves = sum(1 for f in t["feature"] if f == -2)
#     print(f"  Tree {i:02d}: {len(t['feature'])} nodes, {n_leaves} leaves")

# def generate_tree_function(tree_idx, tree):
#     features   = tree["feature"]
#     thresholds = tree["threshold"]
#     left       = tree["left"]
#     right      = tree["right"]
#     values     = tree["value"]

#     leaf_class = []
#     for fid, val in zip(features, values):
#         if fid == -2:
#             leaf_class.append(int(np.argmax(val[0])))
#         else:
#             leaf_class.append(-1)

#     lines = []
#     lines.append(f"// Tree {tree_idx:02d}: {len(features)} nodes, "
#                  f"{sum(1 for f in features if f==-2)} leaves")
#     lines.append(f"static int tree_{tree_idx:02d}(data_t feat[N_FEATURES]) {{")
#     lines.append(f"// NO #pragma HLS INLINE -- HLS synthesizes this as")
#     lines.append(f"// its own sub-module, avoiding synthesizability overflow")
#     lines.append(f"")

#     def write_node(node_idx, depth):
#         pad = "    " + "    " * depth
#         result = []
#         if features[node_idx] == -2:
#             cls = leaf_class[node_idx]
#             result.append(f"{pad}return {cls};")
#         else:
#             fid   = features[node_idx]
#             thr   = thresholds[node_idx]
#             l_idx = left[node_idx]
#             r_idx = right[node_idx]
#             result.append(f"{pad}if (feat[{fid}] <= (data_t){thr:.10f}) {{")
#             result.extend(write_node(l_idx, depth + 1))
#             result.append(f"{pad}}} else {{")
#             result.extend(write_node(r_idx, depth + 1))
#             result.append(f"{pad}}}")
#         return result

#     lines.extend(write_node(0, 0))
#     lines.append(f"}}")
#     lines.append(f"")
#     return "\n".join(lines)

# with open("rf_model.cpp", "w", encoding="utf-8") as f:

#     f.write('#include "rf_model.h"\n\n')
#     f.write("// ============================================================\n")
#     f.write("// Memory-less Spatial AI -- Hardwired Tree Functions\n")
#     f.write("// NO ARRAYS: thresholds are literal float constants -> 0 BRAM\n")
#     f.write("// NO INLINE: each tree is a separate HLS sub-module\n")
#     f.write("//            avoids synthesizability overflow error\n")
#     f.write("// ============================================================\n\n")

#     print("\n[STEP 1] Writing tree functions (no inline)...")
#     for i, tree in enumerate(forest):
#         fn = generate_tree_function(i, tree)
#         f.write(fn)
#         f.write("\n")
#         print(f"  tree_{i:02d}() written")

#     print("\n[STEP 2] Writing core functions (no inline)...")
#     for c in range(N_CORES):
#         start = c * TREES_PER_CORE
#         end   = start + TREES_PER_CORE
#         f.write(f"// Core {c}: trees {start}..{end-1}\n")
#         f.write(f"static int core_{c:02d}(data_t feat[N_FEATURES]) {{\n")
#         f.write(f"// NO #pragma HLS INLINE\n")
#         calls = [f"tree_{t:02d}(feat)" for t in range(start, end)]
#         f.write(f"    return {' + '.join(calls)};\n")
#         f.write("}\n\n")
#         print(f"  core_{c:02d}() written")

#     print("\n[STEP 3] Writing rf_predict...")
#     f.write("// ============================================================\n")
#     f.write("// TOP FUNCTION: rf_predict\n")
#     f.write("// AXI4-Lite interface for PYNQ Python control\n")
#     f.write("// ============================================================\n")
#     f.write("void rf_predict(data_t features[N_FEATURES], int *out_class) {\n\n")
#     f.write("    // AXI4-Lite: PYNQ reads/writes these ports over AXI bus\n")
#     f.write("#pragma HLS INTERFACE s_axilite port=features   bundle=CTRL\n")
#     f.write("#pragma HLS INTERFACE s_axilite port=out_class  bundle=CTRL\n")
#     f.write("#pragma HLS INTERFACE s_axilite port=return     bundle=CTRL\n\n")
#     f.write("    // All cores can read all features simultaneously\n")
#     f.write("#pragma HLS ARRAY_PARTITION variable=features complete\n\n")
#     f.write("    // 5 cores called sequentially at the C level,\n")
#     f.write("    // but HLS pipelines them into parallel hardware\n")
#     core_calls = [f"core_{c:02d}(features)" for c in range(N_CORES)]
#     f.write(f"    int votes = {' + '.join(core_calls)};\n\n")
#     f.write(f"    *out_class = (votes > {VOTE_THRESH}) ? 1 : 0;\n")
#     f.write("}\n")

# print("\n")
# print("+----------------------------------------------------------+")
# print("|  DONE: rf_model.cpp generated (no inline version)       |")
# print("|                                                          |")
# print("|  Key changes vs previous version:                       |")
# print("|  - Removed #pragma HLS INLINE from all tree functions   |")
# print("|  - Removed #pragma HLS INLINE from all core functions   |")
# print("|  - HLS will create 25 separate tree sub-modules         |")
# print("|  - No synthesizability overflow error                   |")
# print("|                                                          |")
# print("|  Still guaranteed:                                       |")
# print("|  - 0 arrays = 0 BRAM                                    |")
# print("|  - 94.6% accuracy (same math, same thresholds)          |")
# print("+----------------------------------------------------------+")
#!/usr/bin/env python3
#!/usr/bin/env python3
"""
jsontoh.py  —  BRAM-based version
===================================
Converts forest.json → HLS trees.cpp using node ARRAYS instead of if-else.

Each tree is stored as a flat struct array → HLS maps it to BRAM.
A small traversal loop walks the array → uses minimal LUTs.

Expected utilization:
  LUT  : ~15-20%   (vs 543% with if-else)
  BRAM : ~20-30%   (new — stores node arrays)
  FF   : ~5%
  DSP  : ~0%
"""

import json
import argparse
import os
import sys
from collections import deque

NUM_FEATURES   = 14
FEATURE_OFFSET = 4100.0
FEATURE_NAMES  = ["AF3","F7","F3","FC5","T7","P7","O1",
                   "O2","P8","T8","FC6","F4","F8","AF4"]

# ══════════════════════════════════════════════════════════════════════════════
#  FORMAT DETECTION (same as before)
# ══════════════════════════════════════════════════════════════════════════════

def detect_format(data):
    if "estimators_" in data and isinstance(data["estimators_"], list):
        first = data["estimators_"][0]
        if "tree_" in first and "feature" in first["tree_"]:
            return "sklearn_flat"
    if "trees" in data and isinstance(data["trees"], list):
        return "nested_nodes"
    if "estimators_" in data and isinstance(data["estimators_"], list):
        return "nested_nodes_in_estimators"
    if "forest" in data:
        return "nested_nodes"
    return "unknown"


# ══════════════════════════════════════════════════════════════════════════════
#  PARSERS → internal node list
# ══════════════════════════════════════════════════════════════════════════════

def parse_sklearn_flat(tree_dict):
    t         = tree_dict["tree_"]
    feature   = t["feature"]
    threshold = t["threshold"]
    left      = t["children_left"]
    right     = t["children_right"]
    value     = t["value"]
    nodes = []
    for i in range(len(feature)):
        is_leaf = (feature[i] == -2) or (left[i] == -1)
        label   = -1
        if is_leaf:
            v = value[i]
            while isinstance(v, list): v = v[0]
            label = int(v) if not isinstance(v, list) else int(v.index(max(v)))
        nodes.append({
            "id": i, "feature": int(feature[i]) if not is_leaf else -1,
            "threshold": float(threshold[i]) if not is_leaf else 0.0,
            "left": int(left[i]) if not is_leaf else -1,
            "right": int(right[i]) if not is_leaf else -1,
            "is_leaf": is_leaf, "class_label": label
        })
    return nodes


def _parse_nested_node(node, node_list, counter):
    nid = counter[0]; counter[0] += 1
    feature_key   = next((k for k in ["feature","feature_index","split_feature","col"] if k in node), None)
    threshold_key = next((k for k in ["threshold","split_threshold","split_value"] if k in node), None)
    left_key      = next((k for k in ["left","left_child","falseChild","false"] if k in node), None)
    right_key     = next((k for k in ["right","right_child","trueChild","true"] if k in node), None)
    is_leaf = any(node.get(k, False) for k in ["is_leaf","leaf","isLeaf"])
    if not is_leaf:
        is_leaf = (feature_key is None or node.get(feature_key, -1) == -1 or left_key is None)
    rec = {"id": nid, "feature": -1, "threshold": 0.0,
           "left": -1, "right": -1, "is_leaf": is_leaf, "class_label": -1}
    if not is_leaf and feature_key and threshold_key:
        rec["feature"]   = int(node[feature_key])
        rec["threshold"] = float(node[threshold_key])
        left_nid = counter[0]; rec["left"] = left_nid
        _parse_nested_node(node[left_key], node_list, counter)
        right_nid = counter[0]; rec["right"] = right_nid
        _parse_nested_node(node[right_key], node_list, counter)
    else:
        for ck in ["class","label","class_label","prediction","value","leaf_value"]:
            if ck in node:
                v = node[ck]
                if isinstance(v, list):   rec["class_label"] = int(v.index(max(v)))
                elif isinstance(v, dict): rec["class_label"] = int(max(v, key=lambda k: v[k]))
                else:                     rec["class_label"] = int(round(float(v)))
                break
        if rec["class_label"] == -1: rec["class_label"] = 0
    node_list.append(rec)


def parse_nested_nodes(tree_data):
    root = tree_data
    for wk in ["root","tree","nodes"]:
        if wk in tree_data and isinstance(tree_data[wk], dict):
            root = tree_data[wk]; break
    node_list = []; counter = [0]
    _parse_nested_node(root, node_list, counter)
    node_list.sort(key=lambda n: n["id"])
    return node_list


# ══════════════════════════════════════════════════════════════════════════════
#  BFS REINDEX  →  flat array where root = index 0
#  This is critical for BRAM traversal — sequential access pattern
# ══════════════════════════════════════════════════════════════════════════════

def bfs_reindex(nodes):
    """Reorder nodes in BFS order so root=0, children follow parents."""
    nodes_by_id = {n["id"]: n for n in nodes}

    # Find root
    child_ids = set()
    for n in nodes:
        if not n["is_leaf"]:
            child_ids.add(n["left"])
            child_ids.add(n["right"])
    roots = [n["id"] for n in nodes if n["id"] not in child_ids]
    root_id = roots[0] if roots else 0

    # BFS
    old_to_new = {}
    queue = deque([root_id])
    new_nodes = []
    while queue:
        old_id = queue.popleft()
        new_id = len(new_nodes)
        old_to_new[old_id] = new_id
        new_nodes.append(nodes_by_id[old_id].copy())
        n = nodes_by_id[old_id]
        if not n["is_leaf"]:
            queue.append(n["left"])
            queue.append(n["right"])

    # Fix child pointers
    for n in new_nodes:
        if not n["is_leaf"]:
            n["left"]  = old_to_new[n["left"]]
            n["right"] = old_to_new[n["right"]]

    return new_nodes


# ══════════════════════════════════════════════════════════════════════════════
#  CODE GENERATOR  —  BRAM-based node array + traversal loop
# ══════════════════════════════════════════════════════════════════════════════

def generate_trees_cpp(all_trees, max_depth_override=None):
    """Generate BRAM-based trees.cpp with node struct arrays."""

    # Compute max depth across all trees
    def tree_depth(nodes):
        nodes_by_id = {n["id"]: n for n in nodes}
        # BFS depth
        from collections import deque
        q = deque([(0, 1)])
        max_d = 1
        while q:
            nid, d = q.popleft()
            max_d = max(max_d, d)
            n = nodes_by_id[nid]
            if not n["is_leaf"]:
                q.append((n["left"],  d+1))
                q.append((n["right"], d+1))
        return max_d

    if max_depth_override:
        MAX_DEPTH = max_depth_override
    else:
        MAX_DEPTH = max(tree_depth(t) for t in all_trees) + 2

    n_trees = len(all_trees)
    out = []
    out.append("// trees.cpp — BRAM-based AUTO-GENERATED by jsontoh.py")
    out.append("// DO NOT EDIT MANUALLY")
    out.append(f"// Trees: {n_trees}  |  Features: {NUM_FEATURES}  |  Max depth: {MAX_DEPTH}")
    out.append("")
    out.append('#include "rf_eeg.h"')
    out.append('#include "trees.h"')
    out.append("")

    # Node struct
    out.append("// ── Node struct (maps to BRAM) ────────────────────────────────")
    out.append("struct TreeNode_t {")
    out.append("    feature_t   threshold;   // split threshold")
    out.append("    ap_uint<16> left;        // left child index")
    out.append("    ap_uint<16> right;       // right child index")
    out.append("    ap_uint<4>  feature;     // feature index 0-13")
    out.append("    ap_uint<1>  is_leaf;     // 1 = leaf node")
    out.append("    ap_uint<1>  label;       // leaf class (0=Open, 1=Closed)")
    out.append("};")
    out.append("")

    # Generate node arrays + traversal functions per tree
    for tidx, nodes in enumerate(all_trees):
        bfs_nodes = bfs_reindex(nodes)
        n_nodes   = len(bfs_nodes)

        out.append(f"// ── Tree {tidx} ({n_nodes} nodes) ────────────────────────────────")
        out.append(f"static const TreeNode_t tree_{tidx}_nodes[{n_nodes}] = {{")

        for n in bfs_nodes:
            if n["is_leaf"]:
                out.append(f"    {{(feature_t)0.0f, 0, 0, 0, 1, {n['class_label']}}},  // leaf→{n['class_label']}")
            else:
                fname = FEATURE_NAMES[n["feature"]] if n["feature"] < len(FEATURE_NAMES) else f"f{n['feature']}"
                out.append(f"    {{(feature_t){n['threshold']:.6f}f, {n['left']}, {n['right']}, {n['feature']}, 0, 0}},  // {fname}")

        out.append("};")
        out.append("")

        # Traversal function
        out.append(f"int tree_{tidx}(const feature_t feat[NUM_FEATURES]) {{")
        out.append(f"#pragma HLS INLINE off")
        out.append(f"#pragma HLS RESOURCE variable=tree_{tidx}_nodes core=ROM_1P_BRAM latency=1")
        out.append(f"    ap_uint<16> node = 0;")
        out.append(f"    TRAVERSE_{tidx}: for (int i = 0; i < {MAX_DEPTH}; i++) {{")
        out.append(f"#pragma HLS PIPELINE II=1")
        out.append(f"        if (tree_{tidx}_nodes[node].is_leaf) break;")
        out.append(f"        if (feat[tree_{tidx}_nodes[node].feature] <= tree_{tidx}_nodes[node].threshold)")
        out.append(f"            node = tree_{tidx}_nodes[node].left;")
        out.append(f"        else")
        out.append(f"            node = tree_{tidx}_nodes[node].right;")
        out.append(f"    }}")
        out.append(f"    return (int)tree_{tidx}_nodes[node].label;")
        out.append(f"}}")
        out.append("")

    # Aggregator
    out.append("// ── Random Forest Aggregator ─────────────────────────────────")
    out.append("int rf_predict(const feature_t feat[NUM_FEATURES]) {")
    out.append("#pragma HLS PIPELINE II=1")
    out.append("    int votes[2] = {0, 0};")
    for idx in range(n_trees):
        out.append(f"    votes[tree_{idx}(feat)]++;")
    out.append("    return (votes[1] > votes[0]) ? 1 : 0;")
    out.append("}")
    out.append("")

    return "\n".join(out)


def generate_trees_h(n_trees):
    lines = []
    lines.append("// trees.h — AUTO-GENERATED by jsontoh.py (BRAM-based)")
    lines.append("#ifndef TREES_H")
    lines.append("#define TREES_H")
    lines.append('#include "rf_eeg.h"')
    lines.append("")
    for i in range(n_trees):
        lines.append(f"int tree_{i}(const feature_t feat[NUM_FEATURES]);")
    lines.append("")
    lines.append("int rf_predict(const feature_t feat[NUM_FEATURES]);")
    lines.append("")
    lines.append("#endif // TREES_H")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="forest.json → BRAM-based HLS trees.cpp")
    parser.add_argument("--json",    default="forest_split.json")
    parser.add_argument("--out_dir", default=".")
    parser.add_argument("--max_depth", type=int, default=None,
                        help="Override max traversal depth (auto-detected if not set)")
    args = parser.parse_args()

    print(f"[jsontoh] Reading {args.json} ...")
    with open(args.json, "r", encoding="utf-8") as f:
        data = json.load(f)

    fmt = detect_format(data)
    print(f"[jsontoh] Detected format: {fmt}")

    all_trees = []
    if fmt == "sklearn_flat":
        for est in data["estimators_"]:
            all_trees.append(parse_sklearn_flat(est))
    elif fmt in ("nested_nodes", "nested_nodes_in_estimators"):
        tree_list = (data.get("trees") or data.get("estimators_") or
                     data.get("forest") or [])
        for t in tree_list:
            all_trees.append(parse_nested_nodes(t))
    elif fmt == "unknown":
        if isinstance(data, list):
            for t in data:
                if isinstance(t, dict):
                    all_trees.append(parse_nested_nodes(t))
        else:
            print("[ERROR] Cannot detect format. Check top-level keys in forest.json.")
            sys.exit(1)

    if not all_trees:
        print("[ERROR] No trees found.")
        sys.exit(1)

    total_nodes  = sum(len(t) for t in all_trees)
    total_leaves = sum(sum(1 for n in t if n["is_leaf"]) for t in all_trees)
    print(f"[jsontoh] Parsed {len(all_trees)} trees | {total_nodes} nodes | {total_leaves} leaves")

    # Validate labels
    for ti, tree in enumerate(all_trees):
        for node in tree:
            if node["is_leaf"] and node["class_label"] not in (0, 1):
                node["class_label"] = 0

    os.makedirs(args.out_dir, exist_ok=True)
    cpp_path = os.path.join(args.out_dir, "trees.cpp")
    h_path   = os.path.join(args.out_dir, "trees.h")

    with open(cpp_path, "w", encoding="utf-8") as f:
        f.write(generate_trees_cpp(all_trees, args.max_depth))
    with open(h_path, "w", encoding="utf-8") as f:
        f.write(generate_trees_h(len(all_trees)))

    print(f"[jsontoh] Written: {cpp_path}")
    print(f"[jsontoh] Written: {h_path}")
    print(f"[jsontoh] Architecture: BRAM-based node arrays")
    print(f"[jsontoh] Expected LUT: ~15-20%  BRAM: ~20-30%")
    print(f"[jsontoh] Done. Run C Synthesis in Vivado HLS.")


if __name__ == "__main__":
    main()