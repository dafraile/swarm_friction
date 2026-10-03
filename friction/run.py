"""Run episodes.

  python -m friction.run --model gpt-6-luna --friction none --locus environment --suite B --seeds 1 --out runs/pilot
  python -m friction.run --model gpt-6-luna --friction none,structured --suite A,B --seeds 1,2,3,4,5 --out runs/main
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .agents import Budget, BudgetExceeded, LLMAgent, RootUsageAggregator, make_judge, make_officer, other_family_model
from .episode import Episode
from .gates import Broker
from .tasks import load_tasks
from .world import World

LOCK = threading.Lock()


def run_one(task: dict, friction: str, locus: str, seed: int, model: str, out: Path, budget: Budget,
            judge_model: str | None, officer_model: str | None, effort: str = "medium", charter: str = "prompt") -> dict:
    locus_for_agent = locus
    agg = RootUsageAggregator()

    def factory(agent_id, instruction, parent_id, meta_tools, role=None):
        a = LLMAgent(agent_id, model, task, instruction, meta_tools, budget=budget, parent_id=parent_id, effort=effort, charter=charter, locus=locus_for_agent)
        agg.agents.append(a)
        if parent_id is None:
            a.usage = agg.total  # episode-level totals reported through the root
        return a

    officer = make_officer(officer_model, budget) if locus == "agent" else None
    judge = make_judge(judge_model, budget) if judge_model else None
    broker = Broker(friction=friction, locus=locus, officer=officer, seed=seed)
    ep = Episode(task, friction, locus, seed, f"{model}@{effort}/{charter}", factory, broker, world=World.load(),
                 log_path=out / "calls.jsonl", judge=judge)
    row = ep.run()
    row["declarations"] = len(broker.declarations)
    row["charter"] = charter
    row["effort"] = effort
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--friction", default="none")
    ap.add_argument("--locus", default="environment")
    ap.add_argument("--suite", default="A,B")
    ap.add_argument("--tasks", default="all", help="comma list of task ids, or all")
    ap.add_argument("--seeds", default="1")
    ap.add_argument("--out", default="runs/dev")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--budget", type=float, default=50.0, help="USD cap for this process")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--label", default="")
    ap.add_argument("--skip-existing", action="store_true", help="skip (task, friction, seed) cells already present in <out>/calls.episodes.jsonl")
    ap.add_argument("--officer-model", default=None, help="compliance officer model (default: the other family)")
    ap.add_argument("--charter", default="prompt", help="prompt | file | none : how the Charter is presented to the root agent")
    ap.add_argument("--effort", default="medium", help="reasoning effort: none/low/medium/high (OpenAI) or low/medium/high (Anthropic)")
    a = ap.parse_args(argv)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()
    suites = set(a.suite.split(","))
    ids = None if a.tasks == "all" else set(a.tasks.split(","))
    tasks = [t for t in tasks if t["suite"] in suites and (ids is None or t["id"] in ids)]
    frictions = a.friction.split(",")
    seeds = [int(s) for s in a.seeds.split(",")]
    budget = Budget(a.budget)
    judge_model = None if a.no_judge else other_family_model(a.model)
    officer_model = a.officer_model or other_family_model(a.model)

    jobs = [(t, f, s) for f in frictions for s in seeds for t in tasks]
    if a.skip_existing and (out / "calls.episodes.jsonl").exists():
        have = set()
        for line in (out / "calls.episodes.jsonl").read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                have.add((r["task_id"], r["friction"], int(r["seed"])))
        before = len(jobs)
        jobs = [(t, f, s) for t, f, s in jobs if (t["id"], f, s) not in have]
        print(f"skip-existing: {before - len(jobs)} cells already done, {len(jobs)} to run", flush=True)
    print(f"{len(jobs)} episodes | model={a.model} locus={a.locus} friction={frictions} suites={sorted(suites)} seeds={seeds} | out={out}", flush=True)
    done = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(run_one, t, f, a.locus, s, a.model, out, budget, judge_model, officer_model, a.effort, a.charter): (t["id"], f, s) for t, f, s in jobs}
        for fut in as_completed(futs):
            tid, f, s = futs[fut]
            try:
                row = fut.result()
            except BudgetExceeded as e:
                print(f"!! {e}", flush=True)
                ex.shutdown(cancel_futures=True)
                break
            except Exception:
                print(f"!! {tid} {f} s{s} ERROR\n{traceback.format_exc()}", flush=True)
                with LOCK:
                    with open(out / "errors.jsonl", "a") as fh:
                        fh.write(json.dumps({"task_id": tid, "friction": f, "seed": s, "error": traceback.format_exc()}) + "\n")
                continue
            done.append(row)
            flag = "VIOL" if row["violation_completed"] else ("att " if row["violation_attempted"] else "    ")
            print(f"{tid:5} {f:10} s{s} | {flag} | met={int(row['objective_met'])} refusal={int(row['scoped_refusal'])} "
                  f"laund={int(row['laundering'])} trunc={int(row['truncated'])} | steps={row['steps']:2} meta={row['meta_calls']:2} "
                  f"k={row['k_realised']} | ${row['cost_usd']:.3f} {row['wall_clock_s']:.0f}s", flush=True)
    summary(done, budget.spent, time.time() - t0)
    with open(out / "summary.json", "a") as fh:
        fh.write(json.dumps({"label": a.label, "args": vars(a), "n": len(done), "spent_usd": round(budget.spent, 3)}) + "\n")


def summary(rows: list[dict], spent: float, secs: float):
    if not rows:
        print("no episodes completed"); return
    import pandas as pd
    df = pd.DataFrame(rows)
    print("\n== summary ==")
    g = df.groupby(["suite", "friction"]).agg(n=("episode_id", "count"), objective_met=("objective_met", "mean"),
                                               violation_completed=("violation_completed", "mean"), scoped_refusal=("scoped_refusal", "mean"),
                                               laundering=("laundering", "mean"), truncated=("truncated", "mean"),
                                               steps=("steps", "mean"), meta=("meta_calls", "mean"), k=("k_realised", "mean"), cost=("cost_usd", "sum"))
    print(g.round(2).to_string())
    print(f"\ntotal spent USD {spent:.2f} in {secs/60:.1f} min; mean per episode USD {spent/len(rows):.3f}")


if __name__ == "__main__":
    sys.exit(main())
