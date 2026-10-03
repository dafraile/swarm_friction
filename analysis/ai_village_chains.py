"""Chain-length and privileged-action density in real swarm activity (AI Village dataset).

HANDOFF §9.1 asked for the chain-length distribution of real agent action chains, to calibrate
what friction would cost. RESULTS.md §3 then showed that in our harness the effect of friction
rides on the *declaration at privileged actions*, not on chain length. So this script measures
both quantities per real session, with a content-blind, purely syntactic privileged-action
classifier mirroring Charter §5 (P1 out-of-workspace file access, P2 network, P3 credentials,
P4 spawn), and reports:

  * n  = actions per session (chain length)
  * k  = privileged-class actions per session (the gate trigger count)
  * the cost of a declaration gate (k extra round-trips per session; share of sessions with k = 0)
  * the cost of a uniform per-step tax (n extra round-trips)
  * for reference, survival p^n and p^k at a few p values

Two sources:
  A. computer_use_turns   — all agents, actions are GUI/bash; bash commands are classified by regex.
  B. claude_code_messages — the Claude Code agent (Opus 4.5), tool_use blocks with tool names:
                            Bash (classified by command), Read/Write/Edit/Glob/Grep (by path),
                            WebFetch/WebSearch (P2), Task/Agent (P4 = spawn).

Usage: python analysis/ai_village_chains.py [--data data/ai_village] [--out docs/AI_VILLAGE_CHAINS.md]
Nothing here reads a screenshot or any text beyond the command / tool arguments. Agents, dates
and goals are reported in aggregate only.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import os
import re
from pathlib import Path

import numpy as np

# ------------------------------------------------------------------ syntactic privileged classes
NET_RE = re.compile(r"\b(curl|wget|ssh|scp|sftp|rsync|nc|ncat|netcat|telnet|ping|dig|nslookup|ftp|git\s+(clone|push|pull|fetch|remote)|"
                    r"pip3?\s+install|npm\s+(i|install|publish)|npx|yarn\s+add|apt(-get)?\s+install|brew\s+install|gh\s+(pr|issue|release|api|repo)|"
                    r"docker\s+(pull|push)|requests\.(get|post)|urllib|httpx|fetch\()", re.I)
# v2 after validation (docs/AI_VILLAGE_CLASSIFIER_VALIDATION.md): credential FILES and commands, credential-shaped
# assignments, auth headers, and the dataset's own [REDACTED] marker. Bare words like "token" no longer count.
CRED_RE = re.compile(r"(\.ssh/|id_rsa|id_ed25519|\.aws/credentials|\.aws/config|\.netrc|\.npmrc|\.pypirc|\.git-credentials|\.docker/config\.json|keychain|"
                     r"gcloud\s+auth|aws\s+configure|gh\s+auth|huggingface-cli\s+login|hf\s+auth|\bprintenv\b|\benv\s*\|\s*grep|"
                     r"(^|[\s;&|])(cat|less|more|head|tail|echo|grep|source)\s+[^|;&]*(\.env\b|secrets?\.(json|ya?ml|txt|env)|credentials\.(json|ya?ml)|token\.(json|txt))|"
                     r"(^|[\s;&|=:\"'(])(?:api[_-]?key|access[_-]?token|auth[_-]?token|bearer|secret[_-]?key|password|passwd|client[_-]?secret)\s*[=:]\s*\S|"
                     r"Authorization:\s*(Bearer|Basic|token)|\[REDACTED\])", re.I)
SPAWN_RE = re.compile(r"\b(claude\s+(-p|--print)|codex\s+exec|aider\b|nohup\s+python.*agent|subprocess\.Popen|tmux\s+new|screen\s+-dm)", re.I)
WRITE_RE = re.compile(r"(>\s*/|>>\s*/|\btee\s+/|\bmv\b.*\s/|\bcp\b.*\s/|\bchmod\b|\bchown\b|\brm\s+-rf?\s+/|\bsudo\b)", re.I)
HOME_ROOTS = ("/home/", "/root/", "/workspace", "/tmp/", "~", "./", "/Users/")


CRED_ENV_RE = re.compile(r"\b[A-Z][A-Z0-9_]*(TOKEN|KEY|SECRET|PASS|PASSWORD|CREDENTIAL)[A-Z0-9_]*\s*=|\$\{?[A-Z][A-Z0-9_]*(TOKEN|KEY|SECRET|PASS|PASSWORD|CREDENTIAL)[A-Z0-9_]*")


def classify_bash(cmd: str) -> set[str]:
    out = set()
    if not cmd:
        return out
    if NET_RE.search(cmd):
        out.add("P2")
    if CRED_RE.search(cmd) or CRED_ENV_RE.search(cmd):
        out.add("P3")
    if SPAWN_RE.search(cmd):
        out.add("P4")
    # P1 (out-of-workspace write) is NOT assigned from bash text: validation found 0 gold positives in 49 regex hits.
    # It is only assigned from explicit file-tool paths (classify_path), where the path is unambiguous.
    return out


def classify_path(path: str) -> set[str]:
    p = (path or "").strip()
    if not p or not p.startswith("/"):
        return set()
    if any(p.startswith(r) for r in HOME_ROOTS):
        return set()
    return {"P1"}


def classify_cc_tool(name: str, inp: dict) -> set[str]:
    n = (name or "").lower()
    if n in ("webfetch", "websearch", "web_fetch", "web_search"):
        return {"P2"}
    if n in ("task", "agent", "spawn", "subagent"):
        return {"P4"}
    if n in ("bash", "mcp__village__bash"):
        return classify_bash(str(inp.get("command", "")))
    if n in ("read", "write", "edit", "multiedit", "notebookedit", "glob", "grep", "ls"):
        return classify_path(str(inp.get("file_path", inp.get("path", inp.get("notebook_path", "")))))
    return set()


# ------------------------------------------------------------------ readers
def rows(path: Path):
    with gzip.open(path, "rt") as fh:
        for l in fh:
            if l.strip():
                try:
                    yield json.loads(l)
                except json.JSONDecodeError:
                    continue


def action_kind(agent_action) -> str | None:
    if not isinstance(agent_action, dict):
        return None
    if "command" in agent_action:
        return "bash"
    a = agent_action.get("action") or agent_action.get("type")
    return str(a) if a else "other"


def computer_use(data: Path, agents: dict, limit: int | None = None):
    """Per-session n and k over computer_use_turns."""
    per: dict[str, dict] = collections.defaultdict(lambda: {"n": 0, "k": 0, "bash": 0, "classes": collections.Counter()})
    sess_agent = {}
    for s in rows(data / "computer_use_sessions.jsonl.gz"):
        sess_agent[s["id"]] = s["agent_id"]
    i = 0
    for t in rows(data / "computer_use_turns.jsonl.gz"):
        i += 1
        if limit and i > limit:
            break
        aa = t.get("agent_action")
        kind = action_kind(aa)
        if kind is None:
            continue
        rec = per[t["session_id"]]
        rec["n"] += 1
        if kind == "bash":
            rec["bash"] += 1
            cls = classify_bash(str(aa.get("command", "")))
            if cls:
                rec["k"] += 1
                rec["classes"].update(cls)
    out = []
    for sid, r in per.items():
        aid = sess_agent.get(sid)
        out.append({"session": sid, "agent": agents.get(aid, {}).get("name", "?"), "model": agents.get(aid, {}).get("model_string", "?"),
                    "n": r["n"], "k": r["k"], "bash": r["bash"], "classes": dict(r["classes"])})
    return out


LOOP_TOOLS = {"mcp__village__get_events", "mcp__village__chat_message", "mcp__village__edit_memory", "mcp__village__search_history",
              "mcp__village__get_pixel_coordinates", "TodoWrite", "mcp__village__wait", "mcp__village__pause"}
START_T, STOP_T = "mcp__village__start_computer_session", "mcp__village__stop_computer_session"


def claude_code(data: Path, agents: dict):
    """The Claude Code agent ran as ONE SDK session for two months, so the chain unit is its own
    start_computer_session → stop_computer_session span. n counts world actions inside a span
    (Bash, village bash, computer_use, Read/Write/Edit/Grep/Glob, WebFetch/WebSearch, Task);
    the scaffold's polling, chat and memory calls are excluded. Tool calls outside any span are
    grouped into "between-session" chains and reported separately."""
    msgs = []
    for m in rows(data / "claude_code_messages.jsonl.gz"):
        if m.get("message_type") != "assistant":
            continue
        c = m.get("content") or {}
        msg = c.get("message", c) if isinstance(c, dict) else {}
        blocks = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(blocks, list):
            continue
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                msgs.append((m["created_at"], b.get("name", ""), b.get("input") or {}))
    msgs.sort(key=lambda x: x[0])
    chains = []
    cur = None
    between = {"n": 0, "k": 0, "classes": collections.Counter(), "tools": collections.Counter(), "spawns": [], "kind": "between"}
    for ts, name, inp in msgs:
        if name == START_T:
            cur = {"n": 0, "k": 0, "classes": collections.Counter(), "tools": collections.Counter(), "spawns": [], "kind": "session", "start": ts}
            continue
        if name == STOP_T:
            if cur is not None:
                cur["end"] = ts
                chains.append(cur)
            cur = None
            continue
        if name in LOOP_TOOLS:
            continue
        rec = cur if cur is not None else between
        rec["n"] += 1
        rec["tools"][name] += 1
        cls = classify_cc_tool(name, inp if isinstance(inp, dict) else {})
        if cls:
            rec["k"] += 1
            rec["classes"].update(cls)
        if "P4" in cls:
            rec["spawns"].append(str(inp.get("prompt", inp.get("description", "")))[:4000])
    if cur is not None:
        chains.append(cur)
    out = [{"session": i, "n": r["n"], "k": r["k"], "classes": dict(r["classes"]), "tools": dict(r["tools"]), "spawns": r["spawns"], "kind": r["kind"]}
           for i, r in enumerate(chains)]
    out.append({"session": "between", "n": between["n"], "k": between["k"], "classes": dict(between["classes"]), "tools": dict(between["tools"]), "spawns": between["spawns"], "kind": "between"})
    return out


# ------------------------------------------------------------------ reporting
def q(xs, ps=(50, 75, 90, 95, 99)):
    xs = np.asarray(xs, dtype=float)
    return {p: float(np.percentile(xs, p)) for p in ps} if len(xs) else {}


def friction_costs(ns, ks):
    ns, ks = np.asarray(ns, float), np.asarray(ks, float)
    out = {"sessions": int(len(ns)), "mean_n": float(ns.mean()), "mean_k": float(ks.mean()),
           "share_k0": float((ks == 0).mean()), "share_k_ge3": float((ks >= 3).mean()),
           "k_over_n": float(ks.sum() / max(ns.sum(), 1)),
           "n_q": q(ns), "k_q": q(ks)}
    for p in (0.99, 0.95, 0.90):
        out[f"survival_uniform_p{p}"] = float(np.mean(p ** ns))
        out[f"survival_privileged_p{p}"] = float(np.mean(p ** ks))
    return out


def fmt_block(title, c):
    lines = [f"### {title}", "",
             f"- sessions: {c['sessions']:,}",
             f"- chain length n: mean {c['mean_n']:.1f}; median {c['n_q'][50]:.0f}; p90 {c['n_q'][90]:.0f}; p99 {c['n_q'][99]:.0f}",
             f"- privileged-class actions k: mean {c['mean_k']:.2f}; median {c['k_q'][50]:.0f}; p90 {c['k_q'][90]:.0f}; p99 {c['k_q'][99]:.0f}",
             f"- privileged share of actions k/n: {c['k_over_n']:.3f}",
             f"- sessions with **no** privileged action (a declaration gate costs them nothing): {c['share_k0']:.1%}",
             f"- sessions with 3 or more: {c['share_k_ge3']:.1%}",
             "",
             "| per-action survival p | uniform tax: mean pⁿ | declaration gate: mean pᵏ |", "|---|---|---|"]
    for p in (0.99, 0.95, 0.90):
        lines.append(f"| {p} | {c[f'survival_uniform_p{p}']:.3f} | {c[f'survival_privileged_p{p}']:.3f} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/ai_village")
    ap.add_argument("--out", default="docs/AI_VILLAGE_CHAINS.md")
    ap.add_argument("--limit", type=int, default=None, help="cap on computer_use_turns rows (debug)")
    ap.add_argument("--only", choices=["cc", "cu"], default=None, help="run only one source")
    a = ap.parse_args()
    data = Path(a.data)
    agents = {r["id"]: r for r in rows(data / "agents.jsonl.gz")}
    md = ["# Chain length and privileged-action density in the AI Village dataset", "",
          "*Generated by `analysis/ai_village_chains.py`. Source: `aidigestorg/ai-village` (AI Digest), "
          "research terms; aggregate statistics only. Privileged classes are assigned by regex over bash "
          "commands and tool arguments, mirroring Charter §5: P1 out-of-workspace file-tool paths (Claude Code stream only), P2 network, "
          "P3 credentials, P4 spawning another agent. The classifier is syntactic and content-blind; it is "
          "an under-count (GUI actions that reach the network through a browser are not visible to it).*", ""]

    # B first: cleanest mapping
    cc_path = data / "claude_code_messages.jsonl.gz"
    if cc_path.exists() and a.only != "cu":
        cc_all = claude_code(data, agents)
        between = [r for r in cc_all if r["kind"] == "between"][0]
        cc = [r for r in cc_all if r["kind"] == "session" and r["n"] > 0]
        c = friction_costs([r["n"] for r in cc], [r["k"] for r in cc])
        md.append("## B. Claude Code agent (Opus 4.5 on the Claude Agent SDK, 2026-01-26 to 2026-04-02)\n")
        md.append(fmt_block("Per computer-session span: world tool calls n, privileged-class calls k (polling, chat and memory calls excluded)", c))
        md.append(f"Tool calls made outside any computer-session span: {between['n']:,} world actions, {between['k']:,} privileged "
                  f"({between['k']/max(between['n'],1):.1%}); these are the agent working from its SDK loop directly and are not chained here.\n")
        tools = collections.Counter(); classes = collections.Counter(); spawns = []
        for r in cc:
            tools.update(r["tools"]); classes.update(r["classes"]); spawns += r["spawns"]
        md.append("Tool mix (all sessions): " + ", ".join(f"{k} {v:,}" for k, v in tools.most_common(12)) + "\n")
        md.append("Privileged classes (session-level counts): " + ", ".join(f"{k} {v:,}" for k, v in sorted(classes.items())) + "\n")
        n_sp = len(spawns)
        md.append(f"**Subagent spawns (P4):** {n_sp:,} across {sum(1 for r in cc if r['spawns'])} sessions. "
                  f"Of the spawn instructions, {sum(1 for s in spawns if re.search(r'village goal|do not|don.t|must not|never|only ', s, re.I)):,} "
                  f"contain any constraint-like language (`village goal`, `do not`, `must not`, `never`, `only`), a crude proxy for whether "
                  f"the parent transmitted its constraints; median instruction length {int(np.median([len(s) for s in spawns])) if spawns else 0} characters.\n")
    else:
        md.append("## B. Claude Code agent — file not present\n")

    # A: computer use
    cu_path = data / "computer_use_turns.jsonl.gz"
    if cu_path.exists() and a.only != "cc":
        cu = computer_use(data, agents, limit=a.limit)
        cu = [r for r in cu if r["n"] > 0]
        c = friction_costs([r["n"] for r in cu], [r["k"] for r in cu])
        md.append("## A. Computer-use sessions, all agents (2025-04-02 to 2026-09-19)\n")
        md.append(fmt_block("Per session: actions n, privileged-class bash actions k", c))
        bash_share = sum(r["bash"] for r in cu) / max(sum(r["n"] for r in cu), 1)
        md.append(f"Bash actions are {bash_share:.1%} of all actions; GUI actions (click, type, scroll) are the rest and are not classified, so k is a floor.\n")
        # by model family
        fam = collections.defaultdict(list)
        for r in cu:
            m = r["model"]
            f = "claude" if "claude" in m else "gpt/o" if m.startswith(("gpt", "o1", "o3", "o4")) else "gemini" if "gemini" in m else "other"
            fam[f].append(r)
        md.append("| model family | sessions | mean n | mean k | share k=0 | k/n |\n|---|---|---|---|---|---|")
        for f, rs in sorted(fam.items(), key=lambda kv: -len(kv[1])):
            cc_ = friction_costs([r["n"] for r in rs], [r["k"] for r in rs])
            md.append(f"| {f} | {cc_['sessions']:,} | {cc_['mean_n']:.1f} | {cc_['mean_k']:.2f} | {cc_['share_k0']:.1%} | {cc_['k_over_n']:.3f} |")
        md.append("")
        top = collections.Counter()
        for r in cu:
            top.update(r["classes"])
        md.append("Privileged classes (session-level counts): " + ", ".join(f"{k} {v:,}" for k, v in sorted(top.items())) + "\n")
    else:
        md.append("## A. Computer-use turns — file not present\n")

    md.append("## Reading\n")
    md.append("The uniform-tax column is what per-step friction would do to completion if each step survived with "
              "probability p: with real chain lengths it collapses quickly. The declaration-gate column is the same "
              "survival applied only at privileged-class actions, which is what the harness actually implements and "
              "what RESULTS.md found carries the effect. The gap between the two columns, and the share of sessions "
              "with k = 0, is the throughput argument for keying friction to a syntactic privileged class rather than "
              "to every step.\n")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
