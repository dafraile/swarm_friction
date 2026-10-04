"""One streaming pass over computer_use_turns: the forensic inventory a content-blind gate would see.
Collects (aggregate only): external hosts in network commands per agent family; credential-pattern
commands; agent/process-spawning commands; and a stratified sample of commands per predicted class
for classifier validation (analysis/validate_classifier.py). Writes data/ai_village_derived/*.json
(gitignored) and docs/AI_VILLAGE_FORENSICS.md.
"""
from __future__ import annotations
import collections, gzip, json, random, re, sys, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_village_chains import classify_bash, rows, NET_RE

DATA = Path("data/ai_village"); OUT = Path("data/ai_village_derived"); OUT.mkdir(exist_ok=True)
HOST_RE = re.compile(r"(?:https?://|ssh\s+(?:\w+@)?|scp\s+(?:\w+@)?|git\s+clone\s+(?:https?://|git@))([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
agents = {r["id"]: r for r in rows(DATA / "agents.jsonl.gz")}
sess_agent = {s["id"]: s["agent_id"] for s in rows(DATA / "computer_use_sessions.jsonl.gz")}
def fam(aid):
    m = agents.get(aid, {}).get("model_string", "?")
    return "claude" if "claude" in m else "gpt/o" if m.startswith(("gpt", "o1", "o3", "o4")) else "gemini" if "gemini" in m else "other"
rng = random.Random(7)
sample = {c: [] for c in ("P1", "P2", "P3", "P4", "none")}; seen = {c: 0 for c in sample}
hosts = collections.Counter(); hosts_fam = collections.defaultdict(collections.Counter); host_agents = collections.defaultdict(set)
cred_cmds = collections.Counter(); spawn_cmds = []; n_bash = 0; n_turns = 0; cls_counts = collections.Counter()
for t in rows(DATA / "computer_use_turns.jsonl.gz"):
    n_turns += 1
    aa = t.get("agent_action")
    if not isinstance(aa, dict) or "command" not in aa:
        continue
    n_bash += 1
    cmd = str(aa["command"]); cls = classify_bash(cmd); aid = sess_agent.get(t["session_id"])
    key = sorted(cls)[0] if cls else "none"
    for c in (cls or {"none"}):
        cls_counts[c] += 1
    seen[key] += 1  # reservoir, 80 per stratum
    record = {"command": cmd, "command_sha256": hashlib.sha256(cmd.encode()).hexdigest(),
              "source_turn_id": t.get("id"), "source_turn_ordinal": n_turns, "session_id": t["session_id"], "stratum": key}
    if len(sample[key]) < 80: sample[key].append(record)
    else:
        j = rng.randrange(seen[key]);
        if j < 80: sample[key][j] = record
    if "P2" in cls:
        for h in set(m.lower() for m in HOST_RE.findall(cmd)):
            hosts[h] += 1; hosts_fam[fam(aid)][h] += 1; host_agents[h].add(aid)
    if "P3" in cls:
        m = re.search(r"(\.ssh/|id_rsa|\.aws/|\.env\b|credentials|secrets?\b|api[_-]?key|token|password|passwd|\.netrc|keychain|gcloud auth|aws configure|printenv)", cmd, re.I)
        cred_cmds[m.group(1).lower() if m else "other"] += 1
    if "P4" in cls and len(spawn_cmds) < 2000:
        spawn_cmds.append({"family": fam(aid), "cmd": cmd[:800]})
json.dump({"schema_version": 2, "sample_records": sample, "stratum_populations": seen, "classifier_sha256": hashlib.sha256(Path(__file__).with_name("ai_village_chains.py").read_bytes()).hexdigest(), "hosts": hosts.most_common(500), "hosts_by_family": {f: c.most_common(60) for f, c in hosts_fam.items()},
           "host_agent_counts": {h: len(a) for h, a in host_agents.items()}, "cred_patterns": cred_cmds.most_common(), "spawn_cmds": spawn_cmds,
           "n_turns": n_turns, "n_bash": n_bash, "class_counts": dict(cls_counts)}, open(OUT / "forensics.json", "w"))
md = ["# What a content-blind gate would have seen in the AI Village", "",
      f"*Aggregate inventory from `analysis/village_forensics_pass.py` over {n_turns:,} computer-use turns ({n_bash:,} bash actions). "
      "No session text is reproduced beyond hostnames and credential-pattern keywords. Dataset: AI Digest, AI Village, research terms.*", "",
      "## Network reach (P2): distinct external hosts named in bash commands", "",
      f"- distinct hosts: **{len(hosts):,}**; hosts named by 5 or more distinct agents: {sum(1 for h,a in host_agents.items() if len(a)>=5):,}",
      "", "| host | commands | distinct agents |", "|---|---|---|"]
md += [f"| {h} | {n:,} | {len(host_agents[h])} |" for h, n in hosts.most_common(40)]
md += ["", "Per model family, top hosts:", ""]
for f, c in hosts_fam.items():
    md.append(f"- **{f}**: " + ", ".join(f"{h} ({n})" for h, n in c.most_common(8)))
md += ["", "## Credential touches (P3): pattern that triggered the class", "", "| pattern | commands |", "|---|---|"]
md += [f"| `{p}` | {n:,} |" for p, n in cred_cmds.most_common(25)]
md += ["", "## Agent/process spawning (P4)", "", f"- commands matching a spawn pattern: {cls_counts['P4']:,} (first 2,000 retained as a descriptive convenience sample; no laundering inference)",
       "- by family: " + ", ".join(f"{f} {n}" for f, n in collections.Counter(s['family'] for s in spawn_cmds).most_common()), "",
       "## Class counts over all bash actions", "", "| class | commands | share of bash |", "|---|---|---|"]
md += [f"| {c} | {cls_counts[c]:,} | {cls_counts[c]/max(n_bash,1):.1%} |" for c in ("P1", "P2", "P3", "P4", "none")]
Path("docs/AI_VILLAGE_FORENSICS.md").write_text("\n".join(md) + "\n"); print("\n".join(md[:12])); print("FORENSICS_DONE")
