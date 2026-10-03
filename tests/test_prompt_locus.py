from friction.charter import ToolCall
from friction.episode import Episode, ScriptedAgent
from friction.gates import Broker
from friction.tasks import load_tasks, REF
TASKS = {t["id"]: t for t in load_tasks()}

def test_prompt_locus_enforces_nothing_but_records_what_it_would_deny():
    plan = [ToolCall("fs_read", {"path": "/archive/claims_2024.csv"}), ToolCall("submit", {"answer": str(REF["claims_2024_total"])})]
    def factory(agent_id, instruction, parent_id, meta_tools, role=None):
        return ScriptedAgent(agent_id, plan, policy="naive")
    ep = Episode(TASKS["B-S1"], "structured", "prompt", 1, "scripted", factory, Broker(friction="structured", locus="prompt"))
    row = ep.run()
    assert row["violation_completed"] and row["denied_calls"] == 0
    g = ep.ctx.rows[0]["gate_results"]
    assert all(v["allow"] for v in g) and any("NOT ENFORCED" in v["reason"] for v in g)
