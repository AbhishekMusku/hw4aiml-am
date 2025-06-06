#!/usr/bin/env python3
"""
pan.py – SpGEMM regression checker (multi-row, multi-column).

Default run (no args):
    python pan.py          # uses ./in.csv  and  ./out.csv → writes ./result.csv

Optional override:
    python pan.py my_in.csv my_out.csv my_result.csv

CSV outputs
-----------
result.csv has five columns
    row_idx_i , col_idx_j , gold , hw , match
where *match* is 1 if |gold–hw| ≤ 1 e‑6, else 0.
"""

import sys, textwrap as _tw, pathlib as _pl, re
import pandas as pd, numpy as np

TOL     = 1e-6            # numeric comparison tolerance
SEP_RE  = r"[\s,]+"       # allow one‑or‑more comma/whitespace as separator

# ---------------------------------------------------------------- helpers
def _read_csv_flex(fname: str, has_header: bool):
    """Read *fname* accepting either comma *or* whitespace delimiters."""
    return pd.read_csv(
        fname,
        sep=SEP_RE,
        engine="python",
        comment="#",
        header=0 if has_header else None,
        skip_blank_lines=True,
    )


def load_sw(fname: str) -> pd.DataFrame:
    df = _read_csv_flex(fname, has_header=True)
    if not {"row_idx_i", "col_idx_j", "prod"}.issubset(df.columns):
        raise ValueError("SW CSV must have columns row_idx_i,col_idx_j,prod")
    df = df[df["row_idx_i"] != 0.5]                     # drop dummy rows
    return (
        df.groupby(["row_idx_i", "col_idx_j"], sort=False)["prod"].sum()
          .rename("gold")
          .reset_index()
    )


def load_hw(fname: str) -> pd.DataFrame:
    raw = _read_csv_flex(fname, has_header=False)
    # remove accidental textual header
    if raw.iloc[0].apply(lambda x: isinstance(x, str) and re.search(r"[A-Za-z]", str(x))).any():
        raw = raw.iloc[1:].reset_index(drop=True)

    if raw.shape[1] == 2:                  # col , val → assume row 0
        raw.columns = ["col_idx_j", "val"]
        raw.insert(0, "row_idx_i", 0)
    elif raw.shape[1] == 3:                # row , col , val
        raw.columns = ["row_idx_i", "col_idx_j", "val"]
    else:
        raise ValueError("HW file must have 2 or 3 columns")

    raw[["row_idx_i", "col_idx_j"]] = raw[["row_idx_i", "col_idx_j"]].astype(int)
    return (
        raw.groupby(["row_idx_i", "col_idx_j"], sort=False)["val"].sum()
           .reset_index()
    )


def build_report(sw: pd.DataFrame, hw: pd.DataFrame) -> pd.DataFrame:
    merged = (
        pd.merge(sw, hw, how="outer", on=["row_idx_i", "col_idx_j"])
          .fillna({"gold": 0, "val": 0})
          .rename(columns={"val": "hw"})
    )
    merged["match"] = np.isclose(merged.gold, merged.hw, atol=TOL).astype(int)
    return merged.sort_values(["row_idx_i", "col_idx_j"]).reset_index(drop=True)

# ---------------------------------------------------------------- main
def main() -> None:
    # Decide file names (in, out, result)
    if len(sys.argv) == 1:
        sw_file, hw_file, res_file = "in.csv", "out.csv", "result.csv"
    elif len(sys.argv) == 3:
        sw_file, hw_file, res_file = sys.argv[1], sys.argv[2], "result.csv"
    elif len(sys.argv) == 4:
        sw_file, hw_file, res_file = sys.argv[1], sys.argv[2], sys.argv[3]
    else:
        print(_tw.dedent(__doc__).strip(), file=sys.stderr)
        sys.exit(2)

    for f in (sw_file, hw_file):
        if not _pl.Path(f).is_file():
            print(f"❌ File not found: {f}", file=sys.stderr)
            sys.exit(2)

    report = build_report(load_sw(sw_file), load_hw(hw_file))
    report.to_csv(res_file, index=False)

    if report["match"].all():
        print(f"✅ All outputs match — report written to {res_file}")
        sys.exit(0)
    else:
        bad = len(report) - report["match"].sum()
        print(f"❌ {bad} mismatches — see {res_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()
