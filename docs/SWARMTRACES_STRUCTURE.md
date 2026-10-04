# SwarmTraces: what the released record structure can establish

**An evidence-coverage audit, not a reconstruction of agent activity.** The local export has 189,579 records and 61,125 parent edges. Every parent edge terminates at an explicit root. The largest connected component has 859 records but a maximum depth of one edge. Treating its size as an 859-step action chain would therefore be incorrect.

## Source and scope

The hackathon lists SwarmTraces as an eligible external dataset ([organizer logistics](https://swarmchasing.com/logistics/)). The publisher's [evidence viewer](https://swarmtraces.org/viewer/) describes payloads, decoded layers and responses. Its [report](https://swarmtraces.org/#limitations) warns of incomplete reconstruction, limited outcome evidence, uncertain attribution and unreliable timing. Those warnings constrain interpretation of the export; our analysis does not independently establish the incident narrative.

We analyzed the existing local copy of `data/swarmtraces/redacted.jsonl.gz`, associated with the publisher's [redacted download](https://swarmtraces.org/data/final/redacted.jsonl.gz). The remote binary was not independently re-fetched for this audit. Results identify the exact local snapshot:

- Compressed bytes: **15,214,685**.
- Compressed SHA-256: `7b66ab21674de52fcd3f557652f68b1801170c998e2f266862124e6edf283488`.
- Analysis: [`analysis/swarmtraces_structure.py`](../analysis/swarmtraces_structure.py).
- Machine-readable output, including analysis-source hash: [`audit/swarmtraces_structure.json`](audit/swarmtraces_structure.json).

This is a census of that export, not a random sample of all swarm activity. The script reads JSON and treats the text as inert data. It counts metadata and literal redaction placeholders and hashes released text for exact duplication. It does not execute or decode text, identify live targets, recover secrets, classify exploit behavior, contact endpoints from the records or call a model. Only aggregate output is committed; the input stays gitignored.

## Record inventory

| Publisher kind | Records |
|---|---:|
| `payload` | 91,037 |
| `recovered_text` | 75,534 |
| `response` | 23,008 |
| **All records** | **189,579** |

All records have the fields `id`, `cite`, `kind`, `parent_id`, `time_utc`, `tags` and `text`. IDs are unique. **All 189,579 `time_utc` values are null.** There is no dedicated agent-identity field. This does not imply that timestamps or agent names never occur inside text; this audit neither extracts nor verifies them.

There are 163,851 distinct SHA-256 hashes of released text. Thus 25,728 records repeat text already present elsewhere; 44,763 records belong to duplicate-text groups. The largest identical-text group contains 1,094 records. Redaction itself can make different originals identical, so these are not duplicate-action estimates. Conversely, different text does not establish independent activity.

## Parent graph

| Structural quantity | Count |
|---|---:|
| Explicit roots / connected components | 128,454 |
| Singleton components | 102,206 |
| Components with at least two records | 26,248 |
| Parent-linked records | 61,125 |
| Missing parent references | 0 |
| Cycles / self-parent edges | 0 / 0 |
| Maximum depth, in parent edges | **1** |

| Parent kind → child kind | Edges |
|---|---:|
| `payload` → `recovered_text` | 42,707 |
| `payload` → `response` | 18,417 |
| `recovered_text` → `recovered_text` | 1 |

Across all components, the median size is 1, p90 is 2, p99 is 10 and maximum is 859. Conditioning on the 26,248 non-singleton components changes those quantiles to 2, 5 and 13. Quantiles use the discrete nearest-rank definition. The component-size histograms and their denominators are retained in the JSON.

These links connect records in the evidence export. No field-level guarantee that they encode execution order, delegation or inter-agent communication was established. Their observed star structure cannot supply action-chain lengths, swarm size, propagation depth or execution duration. In particular, the 859-record component is one root plus 858 children. It is not evidence of 858 helpers or 859 sequential operations. This does not contradict the publisher's separate account of URL-fragment chains: the export's parent graph need not preserve those chains.

## Redaction-marker inventory

These are literal counts of selected publisher-style placeholders, not behavioral labels. An occurrence counts each match; a record counts once per category; a distinct label counts an exact placeholder string. The latter is not independently verified entity resolution.

| Marker category | Occurrences | Records containing it | Distinct literal labels |
|---|---:|---:|---:|
| `REDACTED:destination` | 116,646 | 77,030 | 28,086 |
| `CREDENTIAL` | 42,790 | 31,210 | 2,673 |
| `REDACTED:secret_key` | 3,336 | 3,084 | 372 |
| `SERVICE … URL` | 58,128 | 50,539 | 4,004 |
| `HF REPO` | 7,465 | 5,323 | 520 |
| `REDACTED:hf_repo` | 803 | 716 | 19 |

The JSON includes every matched category and record counts by kind. The two repository-label conventions are kept separate. Categories can overlap within a record and may refer to the same underlying entity. Marker counts also repeat across related records and duplicated text. They must not be summed into estimates of distinct victims, credentials, destinations, privileged operations or successful exfiltration. Absence of a matched marker does not establish absence of sensitive material. The recognizer covers the explicitly listed syntactic formats, not every possible redaction style.

## Questions this audit answers

| Forensic question | Supported answer |
|---|---|
| What is the unit being counted? | Export records, separated by publisher kind. |
| Is the parent graph internally consistent? | Yes for this snapshot: unique IDs, all references resolve, no cycles. |
| Are records a timed sequence of agent actions? | Not established; structured time is wholly absent. |
| Do large components mean long action chains? | No; all linked records are direct children of roots. |
| Can we count credential use or contacts from placeholders? | No; we can count only placeholder occurrences and containing records. |
| Can these data estimate gate effectiveness? | No; no intervention or matched counterfactual is provided. |

The contribution is a reproducible check against mistaken units, denominators and graph interpretations. It extends the project's forensic question set to a different evidence format. It does not add evidence for the effectiveness of the procedural broker.

## Reproduction and checks

From the repository root, using Python 3.11 or newer:

```bash
python analysis/swarmtraces_structure.py data/swarmtraces/redacted.jsonl.gz --out docs/audit/swarmtraces_structure.json
python -m pytest -q tests/test_swarmtraces_structure.py
```

The analyzer uses only the standard library. It rejects unexpected schemas and duplicate IDs rather than silently changing the denominator, and checks that the input hash remains unchanged during analysis. Nine synthetic tests cover out-of-order records, long paths, missing parents, cycles and affected descendants, duplicate IDs, marker denominators, empty inputs and omission of text from output. A separate direct-edge check on the real export confirmed that every referenced parent is a root and independently reconciled all component-size and edge totals. No payload execution or paid API calls were needed.
