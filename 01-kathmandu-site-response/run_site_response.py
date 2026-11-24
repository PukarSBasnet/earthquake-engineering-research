"""Batch 1-D linear site response for every Vs profile in data/vs_profiles.csv.

For each (site, Vs correlation) pair this script builds a PySeismoSoil Vs_Profile,
saves the profile plot and the amplification-function plot, and writes a summary
table with Vs30 and the fundamental frequency f0.

Usage:
    python run_site_response.py                      # all profiles
    python run_site_response.py --site Airport-BH1   # one borehole
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PySeismoSoil.class_Vs_profile import Vs_Profile

HERE = Path(__file__).resolve().parent
COLS = ["thickness_m", "vs_mps", "damping_pct", "density_gcc", "layer"]


def build_profile(group: pd.DataFrame) -> Vs_Profile:
    data = group.sort_values("layer")[COLS].to_numpy(dtype=float)
    return Vs_Profile(data, damping_unit="%", density_unit="g/cm^3")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=HERE / "data" / "vs_profiles.csv")
    ap.add_argument("--out", default=HERE / "output")
    ap.add_argument("--site", help="only run this site (e.g. BH5)")
    args = ap.parse_args()

    df = pd.read_csv(args.data)
    if args.site:
        df = df[df["site"] == args.site]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    summary = []
    for (site, method), g in df.groupby(["site", "vs_correlation"], sort=False):
        prof = build_profile(g)
        tag = f"{site}_{method.replace('-', '')}"

        prof.plot()
        plt.savefig(out / f"{tag}_vs_profile.png", dpi=200, bbox_inches="tight")
        plt.close("all")

        prof.get_ampl_function(show_fig=True)
        plt.savefig(out / f"{tag}_amplification.png", dpi=200, bbox_inches="tight")
        plt.close("all")

        summary.append({
            "site": site,
            "vs_correlation": method,
            "depth_m": g["thickness_m"].sum(),
            "vs30_mps": prof.vs30,
            "f0_ro_hz": prof.get_f0_RO(),
            "f0_bh_hz": prof.get_f0_BH(),
        })
        print(f"done: {tag}")

    pd.DataFrame(summary).to_csv(out / "summary.csv", index=False)
    print(f"\nResults written to {out}")


if __name__ == "__main__":
    main()
