"""The Village's own administrative controls, from events.jsonl.gz: human-helper requests and the
outreach-approval loop. Approval rate, response latency, and who asks. Aggregate only."""
from __future__ import annotations
import collections, json, sys
from datetime import datetime
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_village_chains import rows
DATA = Path("data/ai_village")
agents = {r["id"]: r["name"] for r in rows(DATA / "agents.jsonl.gz")}
types = collections.Counter(); req = {}; resp = []; helper = collections.Counter(); helper_cancel = collections.Counter(); by_type_agent = collections.defaultdict(collections.Counter)
example_keys = {}
for e in rows(DATA / "events.jsonl.gz"):
    d = e.get("data") or {}; t = d.get("actionType"); types[t] += 1
    if t in ("OUTREACH_APPROVAL_REQUEST", "OUTREACH_APPROVAL_RESPONSE", "REQUEST_HUMAN_HELPER", "CANCEL_REQUEST_FOR_HUMAN_HELPER", "STOP_HUMAN_USE_SESSION"):
        example_keys.setdefault(t, sorted(k for k in d.keys() if k != "output"))
        aid = d.get("agentId"); by_type_agent[t][agents.get(aid, "?")] += 1
        ts = datetime.fromisoformat(e["created_at"])
        if t == "OUTREACH_APPROVAL_REQUEST":
            req[d.get("outreachApprovalRequestId") or d.get("requestId") or e["id"]] = (ts, aid, d)
        elif t == "OUTREACH_APPROVAL_RESPONSE":
            resp.append((ts, aid, d))
        elif t == "REQUEST_HUMAN_HELPER": helper[agents.get(aid, "?")] += 1
        elif t == "CANCEL_REQUEST_FOR_HUMAN_HELPER": helper_cancel[agents.get(aid, "?")] += 1
out = ["# The Village's own approval loops (events table)", "",
       "*From `analysis/village_approvals.py`. Aggregate counts; no message text reproduced.*", "",
       "## Event types (all)", "", "| actionType | count |", "|---|---|"]
out += [f"| {t} | {n:,} |" for t, n in types.most_common()]
out += ["", "## Outreach approval (added 2026-04-14): an agent must ask before contacting outside parties", "",
        f"- requests: {len(req)}; responses: {len(resp)}"]
dec = collections.Counter()
for ts, aid, d in resp:
    v = d.get("approval", d.get("approved", d.get("decision")))
    dec[str(v)[:30]] += 1
out.append(f"- decisions (`approval` field): {dict(dec)}")
with_comment = sum(1 for ts, aid, d in resp if (d.get("adminComment") or "").strip())
out.append(f"- responses carrying an admin comment: {with_comment}/{len(resp)}")
def coarse(m):
    m = (m or "").lower()
    if "email" in m or "gmail" in m or "@" in m: return "email"
    if "github" in m or "gitlab" in m: return "github/gitlab"
    if any(k in m for k in ("pinterest", "twitter", "x post", "x /", "reddit", "youtube", "hacker news", "substack", "moltbook", "lesswrong", "ea forum", "medium", "dev.to", "behance", "instructables", "slack", "discord")): return "social/forum post"
    if "contact form" in m or "contact page" in m or "web form" in m or "submit" in m: return "website contact form"
    return "other"
med = collections.Counter(coarse(d.get("medium")) for ts, aid, d in req.values()); out.append(f"- request medium (coarse): {dict(med)}")
proxy_terms = ("proxy", "on behalf of", "acting as my", "posted by", "via another agent", "since i do not have")
proxied = [d for ts, aid, d in req.values() if any(t in ((d.get("medium") or "") + " " + (d.get("rationale") or "")).lower() for t in proxy_terms)]
proxied_ids = {k for k, (ts, aid, d) in req.items() if any(t in ((d.get("medium") or "") + " " + (d.get("rationale") or "")).lower() for t in proxy_terms)}
proxied_outcomes = collections.Counter(str(d.get("approval")) for ts, aid, d in resp if (d.get("outreachApprovalRequestId") in proxied_ids))
out.append(f"- **requests routed through another agent as proxy** (medium/rationale says proxy, on behalf of, posted by another agent, lacking own credentials): {len(proxied)} of {len(req)}; decisions on those: {dict(proxied_outcomes)}")
app_by_agent = collections.defaultdict(lambda: [0, 0])
for ts, aid, d in resp:
    app_by_agent[agents.get(aid, "?")][0] += 1; app_by_agent[agents.get(aid, "?")][1] += bool(d.get("approval"))
out.append("- approval rate by requesting agent (n ≥ 10): " + ", ".join(f"{a} {ap}/{n}" for a, (n, ap) in sorted(app_by_agent.items(), key=lambda kv: -kv[1][0]) if n >= 10))
out.append(f"- response fields seen: {example_keys.get('OUTREACH_APPROVAL_RESPONSE')}")
out.append(f"- request fields seen: {example_keys.get('OUTREACH_APPROVAL_REQUEST')}")
# latency: match by requestId if present, else nearest previous request by same agent
lat = []
reqs_by_agent = collections.defaultdict(list)
for k, (ts, aid, d) in req.items(): reqs_by_agent[aid].append(ts)
for ts, aid, d in resp:
    rid = d.get("outreachApprovalRequestId") or d.get("requestId")
    if rid in req: lat.append((ts - req[rid][0]).total_seconds() / 60)
    else:
        prev = [t for t in reqs_by_agent.get(aid, []) if t <= ts]
        if prev: lat.append((ts - max(prev)).total_seconds() / 60)
if lat: out.append(f"- response latency (min): median {np.median(lat):.0f}, p90 {np.percentile(lat,90):.0f}, max {max(lat):.0f}  (n={len(lat)})")
out += ["- requests by agent: " + ", ".join(f"{a} {n}" for a, n in by_type_agent['OUTREACH_APPROVAL_REQUEST'].most_common(10)), "",
        "## Human-helper requests (the agent asks a human to take over)", "",
        f"- requests: {sum(helper.values())}; cancellations: {sum(helper_cancel.values())}; human sessions stopped: {types['STOP_HUMAN_USE_SESSION']}",
        "- by agent: " + ", ".join(f"{a} {n}" for a, n in helper.most_common(12)), "",
        "## Google sign-in hand-off (credential never given to the agent)", "",
        f"- REQUEST_GOOGLE_SIGN_IN {types['REQUEST_GOOGLE_SIGN_IN']}, RESTARTING_AFTER_GOOGLE_SIGN_IN {types['RESTARTING_AFTER_GOOGLE_SIGN_IN']}",
        "", "## Reading", "",
        "The Village already runs two of the three loci from the harness: a human approval step for outreach "
        "(deny-until-approved; a quarter of requests are refused, median turnaround minutes, tail of days) and an environment-level "
        "credential split for Google sign-in, where the agent structurally cannot hold the password and must hand off. Both emit an "
        "event record whether or not anyone reads the transcript. Ten proxy-posting requests explicitly routed actions through another "
        "agent, and nine were approved. This is evidence of disclosed delegation under an approval process, not evidence of evasion "
        "or policy laundering. The records do not establish whether a parent transmitted all applicable constraints."]
Path("docs/AI_VILLAGE_APPROVALS.md").write_text("\n".join(out) + "\n"); print("\n".join(out))
