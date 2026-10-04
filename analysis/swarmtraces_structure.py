"""Offline evidence-coverage audit of the publisher's redacted JSONL export.

Only record metadata, exact-text hashes and literal publisher redaction markers
are measured. Text is never executed, decoded, sent to a model or emitted.
Parent edges are artifact relations, not observed agent interactions.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re


KINDS = {"payload", "response", "recovered_text"}
FIELDS = {"id", "cite", "kind", "parent_id", "time_utc", "tags", "text"}
MARKERS = (
    (None, re.compile(r"\[REDACTED:([a-z_]+):[0-9]+\]")),
    ("credential", re.compile(r"\[CREDENTIAL [0-9]+\]")),
    ("user", re.compile(r"\[USER [0-9]+\]")),
    ("hf_repo_label", re.compile(r"\[HF REPO [0-9]+\]")),
    ("service_url", re.compile(r"\[SERVICE [0-9]+ URL [0-9]+\]")),
    ("service_host", re.compile(r"\[SERVICE HOST [0-9]+\]")),
)


def distribution(values):
    """Discrete nearest-rank quantiles; no interpolation between graph sizes."""
    values = sorted(values)
    if not values:
        return {"n": 0, "min": None, "p50": None, "p90": None,
                "p99": None, "max": None, "histogram": {}}
    result = {"n": len(values), "min": values[0], "max": values[-1]}
    for label, q in (("p50", .5), ("p90", .9), ("p99", .99)):
        result[label] = values[math.ceil(q * len(values)) - 1]
    result["histogram"] = dict(sorted(Counter(values).items()))
    return result


def graph_summary(nodes):
    """Resolve each child-to-parent path iteratively, including malformed graphs.

    Missing-parent and cycle-affected nodes are excluded from rooted component
    metrics and separately counted. Duplicate IDs are rejected at ingestion.
    """
    resolved = {}  # id -> (status, root id or None, depth or None)
    cycle_lengths = []
    for start in nodes:
        path, positions = [], {}
        current = start
        while current not in resolved:
            if current not in nodes:
                outcome = ("missing_parent", None, None)
                break
            if current in positions:
                cycle_lengths.append(len(path) - positions[current])
                outcome = ("cycle", None, None)
                break
            positions[current] = len(path)
            path.append(current)
            parent = nodes[current]["parent_id"]
            if parent is None:
                resolved[current] = ("rooted", current, 0)
                path.pop()
                outcome = resolved[current]
                break
            current = parent
        else:
            outcome = resolved[current]
        for node_id in reversed(path):
            status, root, depth = outcome
            outcome = (status, root, depth + 1 if depth is not None else None)
            resolved[node_id] = outcome

    status_counts = Counter(s for s, _, _ in resolved.values())
    sizes, depths, transitions, children = Counter(), [], Counter(), Counter()
    for node_id, node in nodes.items():
        status, root, depth = resolved[node_id]
        if status == "rooted":
            sizes[root] += 1
            depths.append(depth)
        parent = node["parent_id"]
        if parent in nodes:
            transitions[(nodes[parent]["kind"], node["kind"])] += 1
            children[parent] += 1
    components = list(sizes.values())
    return {
        "explicit_roots": sum(n["parent_id"] is None for n in nodes.values()),
        "parent_linked_records": sum(n["parent_id"] is not None for n in nodes.values()),
        "missing_parent_edges": sum(n["parent_id"] is not None and
                                    n["parent_id"] not in nodes for n in nodes.values()),
        "self_parent_edges": sum(k == n["parent_id"] for k, n in nodes.items()),
        "cycles": len(cycle_lengths), "cycle_lengths": distribution(cycle_lengths),
        "rooted_records": status_counts["rooted"],
        "records_affected_by_missing_parent": status_counts["missing_parent"],
        "records_affected_by_cycle": status_counts["cycle"],
        "rooted_components": len(components),
        "singleton_components": sum(s == 1 for s in components),
        "non_singleton_components": sum(s > 1 for s in components),
        "component_sizes_all_roots": distribution(components),
        "component_sizes_non_singleton": distribution(s for s in components if s > 1),
        "record_depths_edges_from_root": distribution(depths),
        "children_per_parent_with_children": distribution(children.values()),
        "parent_child_kind_counts": [
            {"parent_kind": a, "child_kind": b, "records": n}
            for (a, b), n in sorted(transitions.items())],
    }


def analyze(records):
    nodes, kinds, nonnull = {}, Counter(), Counter()
    text_hashes = Counter()
    occurrences, record_counts = Counter(), Counter()
    labels = defaultdict(set)
    by_kind = defaultdict(Counter)
    timestamped = 0
    for ordinal, row in enumerate(records, 1):
        # Error messages never contain record values or text.
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError(f"Unexpected schema at record {ordinal}")
        if any(not isinstance(row[k], str) for k in ("id", "cite", "kind", "tags", "text")):
            raise ValueError(f"Unexpected field type at record {ordinal}")
        if not row["id"] or row["id"] in nodes:
            raise ValueError(f"Empty or duplicate ID at record {ordinal}")
        if row["kind"] not in KINDS:
            raise ValueError(f"Unknown record kind at record {ordinal}")
        if row["parent_id"] is not None and (
            not isinstance(row["parent_id"], str) or not row["parent_id"]
        ):
            raise ValueError(f"Invalid parent ID at record {ordinal}")
        if row["time_utc"] is not None and not isinstance(row["time_utc"], str):
            raise ValueError(f"Invalid timestamp type at record {ordinal}")
        nodes[row["id"]] = {k: row[k] for k in ("parent_id", "kind")}
        kinds[row["kind"]] += 1
        nonnull.update(k for k, v in row.items() if v is not None)
        timestamped += bool(row["time_utc"])
        text_hashes[hashlib.sha256(row["text"].encode("utf-8")).digest()] += 1
        present = set()
        for label, pattern in MARKERS:
            for match in pattern.finditer(row["text"]):
                category = f"named:{label}" if label else f"redacted:{match.group(1)}"
                occurrences[category] += 1
                labels[category].add(match.group(0))
                present.add(category)
        record_counts.update(present)
        by_kind[row["kind"]].update(present)
    total = len(nodes)
    return {
        "schema_version": 1,
        "records": total, "kind_counts": dict(sorted(kinds.items())),
        "field_nonnull_counts": {k: nonnull[k] for k in sorted(FIELDS)},
        "records_with_nonempty_time_utc": timestamped,
        "exact_text": {
            "unique_sha256_values": len(text_hashes),
            "duplicate_records_beyond_first": total - len(text_hashes),
            "records_in_duplicate_groups": sum(n for n in text_hashes.values() if n > 1),
            "largest_identical_text_group": max(text_hashes.values(), default=0),
        },
        "graph": graph_summary(nodes),
        "marker_counts": {
            category: {"occurrences": occurrences[category],
                       "records": record_counts[category],
                       "distinct_literal_labels": len(labels[category]),
                       "records_by_kind": {kind: by_kind[kind][category] for kind in sorted(KINDS)}}
            for category in sorted(occurrences)
        },
        "interpretation": [
            "Record kinds and parent edges are publisher metadata, not observed agent interactions.",
            "Response labels alone do not establish successful execution or matched requests.",
            "Exact-text duplication is over released redacted text, not underlying actions.",
            "Marker occurrences, records and distinct labels are different denominators.",
            "Literal labels do not establish distinct secrets, people, hosts or successful use.",
            "Marker counts cover only the explicitly listed syntactic patterns; categories may overlap.",
            "Missing time_utc does not mean the original event or the text had no time information.",
        ],
    }


def read_records(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for ordinal, line in enumerate(stream, 1):
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON at line {ordinal}") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.out.resolve():
        parser.error("Output must differ from input")
    with args.input.open("rb") as stream:
        before = hashlib.file_digest(stream, "sha256").hexdigest()
    result = analyze(read_records(args.input))
    with args.input.open("rb") as stream:
        after = hashlib.file_digest(stream, "sha256").hexdigest()
    if before != after:
        raise ValueError("Input changed during analysis")
    result["source"] = {"compressed_sha256": before, "compressed_bytes": args.input.stat().st_size}
    with Path(__file__).open("rb") as stream:
        result["analysis_source_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"Audited {result['records']:,} records; wrote aggregate JSON to {args.out}")


if __name__ == "__main__":
    main()
