"""Random-forest ground-motion model for NGA-West2 Fourier amplitude spectra.

Script version of ml_ground_motion_model.ipynb. Trains one RandomForestRegressor
per frequency, reports R^2 / RMSE on a 20 % hold-out set, and saves the five
figures plus a performance table.

Usage:
    python gmm_random_forest.py --data path/to/NGA2West_FAS_CA.csv
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

FREQ_COLS = ["freq0.501187", "freq1.000000", "freq2.041738", "freq3.019952", "freq4.570881"]
BASE_FEATURES = ["mag", "Rrup", "Vs30", "eqUTMx", "eqUTMy", "staUTMx", "staUTMy"]


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    X = df[BASE_FEATURES].copy()
    X["log_Rrup"] = np.log10(X["Rrup"] + 1)
    X["log_Vs30"] = np.log10(X["Vs30"])
    X["mag_squared"] = X["mag"] ** 2
    return X


def scenario(X, mag, rrup, vs30):
    row = {c: X[c].median() for c in ["eqUTMx", "eqUTMy", "staUTMx", "staUTMy"]}
    row.update(mag=mag, Rrup=rrup, Vs30=vs30)
    return make_features(pd.DataFrame([row]))[X.columns]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="NGA2West_FAS_CA.csv")
    ap.add_argument("--out", default=Path(__file__).resolve().parent / "output")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.data)
    freqs = [float(c.replace("freq", "")) for c in FREQ_COLS]
    X = make_features(df)
    Y = df[FREQ_COLS].copy()
    X = X.fillna(X.median())
    Y = Y.fillna(Y.median())

    X_tr, X_te, Y_tr, Y_te = train_test_split(X, Y, test_size=0.2, random_state=args.seed)
    scaler = StandardScaler().fit(X_tr)
    Xs_tr, Xs_te = scaler.transform(X_tr), scaler.transform(X_te)

    models, preds, results = {}, {}, []
    for col, f in zip(FREQ_COLS, freqs):
        m = RandomForestRegressor(n_estimators=100, max_depth=15, random_state=args.seed, n_jobs=-1)
        m.fit(Xs_tr, Y_tr[col])
        models[col], preds[col] = m, m.predict(Xs_te)
        r2 = r2_score(Y_te[col], preds[col])
        rmse = np.sqrt(mean_squared_error(Y_te[col], preds[col]))
        results.append({"frequency_hz": f, "r2": r2, "rmse": rmse})
        print(f"{f:6.3f} Hz: R2 = {r2:.3f}, RMSE = {rmse:.4f}")
    res = pd.DataFrame(results)
    res.to_csv(out / "performance.csv", index=False)
    print(f"\nAverage R2: {res['r2'].mean():.3f}")

    # Fig 1: predicted vs actual
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    for ax, col, f in zip(axes.flat, FREQ_COLS, freqs):
        ax.scatter(Y_te[col], preds[col], alpha=0.5, s=20)
        lims = [min(Y_te[col].min(), preds[col].min()), max(Y_te[col].max(), preds[col].max())]
        ax.plot(lims, lims, "r--", lw=2)
        ax.set(xlabel="Actual", ylabel="Predicted", title=f"{f:.3f} Hz (R² = {r2_score(Y_te[col], preds[col]):.3f})")
        ax.grid(True, alpha=0.3)
    axes.flat[-1].remove()
    fig.tight_layout()
    fig.savefig(out / "predicted_vs_actual.png", dpi=300)

    # Figs 2-4: scaling with magnitude, distance, Vs30
    sweeps = [
        ("magnitude_scaling", "Magnitude", np.linspace(4, 8, 50), lambda v: (v, 20.0, 500.0), False,
         "Ground Motion vs Magnitude (R=20 km, Vs30=500 m/s)"),
        ("distance_scaling", "Distance (km)", np.linspace(1, 200, 50), lambda v: (6.5, v, 500.0), True,
         "Ground Motion vs Distance (M=6.5, Vs30=500 m/s)"),
        ("vs30_scaling", "Vs30 (m/s)", np.linspace(150, 1000, 50), lambda v: (6.5, 20.0, v), False,
         "Ground Motion vs Vs30 (M=6.5, R=20 km)"),
    ]
    for name, xlabel, values, params, logx, title in sweeps:
        fig, ax = plt.subplots(figsize=(10, 6))
        grid = pd.concat([scenario(X, *params(v)) for v in values])
        gs = scaler.transform(grid)
        for col, f in zip(FREQ_COLS, freqs):
            ax.plot(values, models[col].predict(gs), lw=2, label=f"{f:.3f} Hz")
        ax.set(xlabel=xlabel, ylabel="Predicted Ground Motion", title=title)
        if logx:
            ax.set_xscale("log")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(out / f"{name}.png", dpi=300)

    # Fig 5: correlation between frequencies
    labels = [f"{f:.3f} Hz" for f in freqs]
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(pd.DataFrame(preds).corr(), annot=True, fmt=".3f", cmap="coolwarm", center=0,
                square=True, ax=ax, xticklabels=labels, yticklabels=labels)
    ax.set_title("Frequency Correlation")
    fig.tight_layout()
    fig.savefig(out / "frequency_correlation.png", dpi=300)
    print(f"Outputs saved to {out}")


if __name__ == "__main__":
    main()
