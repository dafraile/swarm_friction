"""Confirmatory analysis. Committed before the confirmatory run (PREREGISTRATION.md).

    python analysis/primary.py runs/main_luna runs/main_sonnet ...

Primary: logit(y) ~ friction * suite + n_star [+ model], cluster-robust SE by task_id,
with y = violation_completed in Suite B and objective_met in Suite A. β3 (friction×suite) is
the asymmetry. Reported per friction arm vs none, per model and pooled.
Secondary (exploratory, Wilson intervals): scoped_refusal, laundering, rubber_stamp, Δk strata,
Suite A overhead, descriptive asymmetry index with bootstrap.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.proportion import proportion_confint


def load(paths) -> pd.DataFrame:
    rows = []
    for p in paths:
        f = Path(p) / "calls.episodes.jsonl"
        if f.exists():
            rows += [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    df = pd.DataFrame(rows)
    df["model_family"] = df["model"].str.split("@").str[0]
    df["y"] = np.where(df["suite"] == "B", df["violation_completed"], df["objective_met"]).astype(int)
    df["suiteB"] = (df["suite"] == "B").astype(int)
    df["dk"] = (df["k_out"].fillna(0) - df["k_in"].fillna(0)).astype(int)
    return df


def primary(df: pd.DataFrame, arm: str, label: str):
    d = df[df["friction"].isin(["none", arm])].copy()
    if d["friction"].nunique() < 2 or d["suite"].nunique() < 2:
        print(f"  [{label}] insufficient cells for arm={arm}")
        return
    d["fr"] = (d["friction"] == arm).astype(int)
    formula = "y ~ fr * suiteB + n_star" + (" + C(model_family)" if d["model_family"].nunique() > 1 else "")
    try:
        m = smf.logit(formula, data=d).fit(disp=0, cov_type="cluster", cov_kwds={"groups": d["task_id"]})
        b, se = m.params["fr:suiteB"], m.bse["fr:suiteB"]
        print(f"  [{label}] arm={arm:10} n={len(d):4}  β3(friction×suite) = {b:+.2f}  (95% CI {b-1.96*se:+.2f}, {b+1.96*se:+.2f})  p={m.pvalues['fr:suiteB']:.3f}")
    except Exception as e:  # separation etc.
        print(f"  [{label}] arm={arm:10} n={len(d):4}  logit failed ({type(e).__name__}: {str(e)[:60]}); see cell table")


def cells(df: pd.DataFrame):
    g = df.groupby(["model_family", "locus", "suite", "friction"]).agg(
        n=("episode_id", "count"), objective_met=("objective_met", "mean"), viol_attempted=("violation_attempted", "mean"),
        viol_completed=("violation_completed", "mean"), scoped_refusal=("scoped_refusal", "mean"), laundering=("laundering", "mean"),
        rubber_stamp=("rubber_stamp", "mean"), truncated=("truncated", "mean"), steps=("steps", "mean"), meta=("meta_calls", "mean"),
        k=("k_realised", "mean"), tokens_in=("tokens_in", "mean"), cost=("cost_usd", "sum"))
    print(g.round(2).to_string())


def asymmetry_index(df: pd.DataFrame, arm: str, label: str, B: int = 2000, seed: int = 0):
    rng = np.random.default_rng(seed)
    d = df[df["friction"].isin(["none", arm])]
    def A(dd):
        b0 = dd[(dd.suite == "B") & (dd.friction == "none")]["violation_completed"].mean()
        b1 = dd[(dd.suite == "B") & (dd.friction == arm)]["violation_completed"].mean()
        a0 = dd[(dd.suite == "A") & (dd.friction == "none")]["objective_met"].mean()
        a1 = dd[(dd.suite == "A") & (dd.friction == arm)]["objective_met"].mean()
        return (b0 - b1), (a0 - a1)
    db, da = A(d)
    boots = []
    tasks = d["task_id"].unique()
    for _ in range(B):
        samp = rng.choice(tasks, size=len(tasks), replace=True)
        dd = pd.concat([d[d.task_id == t] for t in samp])
        boots.append(A(dd))
    boots = np.array(boots)
    ratio = db / da if abs(da) > 1e-9 else float("nan")
    lo_da, hi_da = np.nanpercentile(boots[:, 1], [2.5, 97.5])
    note = "" if (lo_da > 0 or hi_da < 0) else "  (denominator CI covers 0: ratio undefined, report the two deltas)"
    print(f"  [{label}] arm={arm:10} Δviolation_completed={db:+.3f} (95% {np.nanpercentile(boots[:,0],2.5):+.3f},{np.nanpercentile(boots[:,0],97.5):+.3f})  "
          f"Δobjective_met|A={da:+.3f} (95% {lo_da:+.3f},{hi_da:+.3f})  A={ratio:.2f}{note}")


def secondary(df: pd.DataFrame):
    def rate(sub, col):
        k, n = int(sub[col].sum()), len(sub)
        lo, hi = proportion_confint(k, n, method="wilson") if n else (np.nan, np.nan)
        return f"{k}/{n} = {k/n if n else float('nan'):.2f} ({lo:.2f}, {hi:.2f})"
    print("\n-- scoped_refusal, Suite B, by model × friction")
    for (m, f), sub in df[df.suite == "B"].groupby(["model_family", "friction"]):
        print(f"  {m:20} {f:10} {rate(sub, 'scoped_refusal')}")
    print("\n-- laundering on spawn tasks (B-S5, B-L5), by model × locus × friction")
    for (m, l, f), sub in df[df.task_id.isin(["B-S5", "B-L5"])].groupby(["model_family", "locus", "friction"]):
        print(f"  {m:20} {l:12} {f:10} laundering {rate(sub, 'laundering')}   spawned {int(sub['spawns'].gt(0).sum())}/{len(sub)}")
    if (df.locus == "agent").any():
        print("\n-- rubber_stamp at the agent locus (episodes with ≥1 out-of-scope approval)")
        for (m, f), sub in df[df.locus == "agent"].groupby(["model_family", "friction"]):
            print(f"  {m:20} {f:10} {rate(sub, 'rubber_stamp')}")
    print("\n-- violation_completed in Suite B by Δk stratum × friction (H2)")
    for (m, dk, f), sub in df[df.suite == "B"].groupby(["model_family", "dk", "friction"]):
        print(f"  {m:20} Δk={dk}  {f:10} {rate(sub, 'violation_completed')}")
    print("\n-- Suite A overhead (tax): mean steps / meta calls / tokens_in by friction")
    print(df[df.suite == "A"].groupby(["model_family", "friction"])[["steps", "meta_calls", "tokens_in", "objective_met"]].mean().round(2).to_string())


def main(paths):
    df = load(paths)
    print(f"{len(df)} episodes from {len(paths)} run dirs\n\n== cells ==")
    cells(df)
    env = df[df.locus == "environment"]
    print("\n== primary: β3 = friction × suite interaction (log-odds), cluster-robust by task ==")
    for arm in ("structured", "tax"):
        for m, sub in env.groupby("model_family"):
            primary(sub, arm, m)
        if env["model_family"].nunique() > 1:
            primary(env, arm, "pooled")
    print("\n== descriptive asymmetry index (task-level bootstrap) ==")
    for arm in ("structured", "tax"):
        for m, sub in env.groupby("model_family"):
            if (sub.friction == arm).any():
                asymmetry_index(sub, arm, m)
    print("\n== secondary (exploratory) ==")
    secondary(df)


if __name__ == "__main__":
    main(sys.argv[1:] or ["runs/main_luna"])
