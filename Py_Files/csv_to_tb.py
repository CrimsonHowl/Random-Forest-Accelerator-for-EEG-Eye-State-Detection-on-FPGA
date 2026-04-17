#!/usr/bin/env python3
"""
csv_to_tb.py
============
Converts test_300.csv (output of retrain_on_split.py) into a C++ array
initializer that can be pasted directly into tb_accuracy.cpp.

Usage:
  python csv_to_tb.py --csv test_300.csv --out tb_accuracy.cpp

If --out is given, it patches the TEST_DATA block in-place.
Otherwise it prints to stdout.
"""

import argparse
import pandas as pd
import re
import sys

MARKER_START = "// <<<< PASTE csv_to_tb.py OUTPUT HERE >>>>"
MARKER_END   = "    // ... add all 300 rows ..."


def csv_to_cpp_rows(csv_path: str) -> list[str]:
    df = pd.read_csv(csv_path)
    rows = []
    for i, row in df.iterrows():
        feat_vals = list(row.iloc[:-1])
        label     = int(row.iloc[-1])
        vals_str  = ", ".join(f"{v:.4f}f" for v in feat_vals)
        rows.append(f"    {{{vals_str}, {label}.0f}},")
    return rows


def patch_tb_file(tb_path: str, new_rows: list[str]):
    with open(tb_path, "r") as f:
        content = f.read()

    # Find and replace between markers
    pattern = re.compile(
        r'(// <<<<[^>]+>>>>\n)(.+?)(    // \.\.\. add all 300 rows \.\.\.)',
        re.DOTALL
    )
    replacement = r'\g<1>' + "\n".join(new_rows) + "\n    // auto-generated\n"
    new_content, n = re.subn(pattern, replacement, content)

    if n == 0:
        print("[csv_to_tb] Marker not found. Printing to stdout instead.")
        print("\n".join(new_rows))
        return

    with open(tb_path, "w") as f:
        f.write(new_content)
    print(f"[csv_to_tb] ✓ Patched {tb_path} with {len(new_rows)} samples")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="test_300.csv path")
    ap.add_argument("--out", default=None,  help="tb_accuracy.cpp to patch (optional)")
    args = ap.parse_args()

    rows = csv_to_cpp_rows(args.csv)
    print(f"[csv_to_tb] Read {len(rows)} samples from {args.csv}")

    if args.out:
        patch_tb_file(args.out, rows)
    else:
        print("\n".join(rows))


if __name__ == "__main__":
    main()