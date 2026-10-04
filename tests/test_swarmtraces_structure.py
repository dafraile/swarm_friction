import json

import pytest

from analysis.swarmtraces_structure import analyze, distribution


def row(id, parent=None, kind="payload", text="example"):
    return dict(id=id, parent_id=parent, kind=kind, text=text,
                cite="example", time_utc=None, tags="")


def test_parent_graph_is_order_independent_and_counts_artifacts():
    rows = [row("c", "b", "recovered_text"), row("a"),
            row("b", "a", "response"), row("isolated")]
    result = analyze(rows)
    assert result == analyze(reversed(rows))
    graph = result["graph"]
    assert graph["rooted_components"] == 2
    assert graph["singleton_components"] == 1
    assert graph["component_sizes_non_singleton"]["max"] == 3
    assert graph["record_depths_edges_from_root"]["max"] == 2
    assert graph["parent_linked_records"] == 2
    assert result["exact_text"]["duplicate_records_beyond_first"] == 3


def test_missing_parents_cycles_and_descendants_are_not_treated_as_roots():
    rows = [row("root"), row("missing", "absent"), row("desc", "missing"),
            row("x", "y"), row("y", "x"), row("z", "x"), row("self", "self")]
    graph = analyze(rows)["graph"]
    assert graph["rooted_records"] == 1
    assert graph["missing_parent_edges"] == 1
    assert graph["records_affected_by_missing_parent"] == 2
    assert graph["cycles"] == 2
    assert graph["records_affected_by_cycle"] == 4
    assert graph["self_parent_edges"] == 1
    assert graph["cycle_lengths"]["histogram"] == {1: 1, 2: 1}


def test_markers_have_separate_denominators_and_no_content_is_emitted():
    text = "PRIVATE_SENTINEL [CREDENTIAL 1] [CREDENTIAL 1] [CREDENTIAL 2] [REDACTED:secret_key:001]"
    result = analyze([row("a", text=text), row("b", kind="response", text="[CREDENTIAL 1]")])
    assert result["marker_counts"]["named:credential"] == {
        "occurrences": 4, "records": 2, "distinct_literal_labels": 2,
        "records_by_kind": {"payload": 1, "response": 1, "recovered_text": 0},
    }
    serialized = json.dumps(result)
    assert "PRIVATE_SENTINEL" not in serialized
    assert "[CREDENTIAL 1]" not in serialized
    assert "[REDACTED:secret_key:001]" not in serialized


@pytest.mark.parametrize("rows", [
    [row("same"), row("same")], [row("")], [row("a", parent=1)],
    [row("a", kind="unknown")], [{"id": "incomplete"}],
])
def test_invalid_export_fails_instead_of_silently_changing_denominators(rows):
    with pytest.raises(ValueError):
        analyze(rows)


def test_empty_and_long_graphs():
    assert analyze([])["records"] == 0
    assert distribution([])["max"] is None
    result = analyze(row(str(n), str(n - 1) if n else None) for n in reversed(range(2500)))
    assert result["graph"]["record_depths_edges_from_root"]["max"] == 2499
