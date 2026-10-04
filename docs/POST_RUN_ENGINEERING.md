# Maintenance after completion of the frozen experiment

All 400 main and 10 pilot episodes had completed before these changes. The main run used the source recorded in its manifest (Git `139078b`); its schedule and worlds were committed at `dd0b247`. The original data and analysis were committed before this maintenance. No paid reruns were made.

Two defensive fixes followed the completed run:

- If a process dies after writing `started.json` but before a terminal result, the report loader now calls that attempt `interrupted_no_result`, retains any logged completed violation, and treats completion as unavailable. It no longer calls the attempt unstarted. None of the 410 completed episodes needed this path; the generated primary report is byte-identical before and after the change.
- SQLite now limits individual values/rows to 1 MiB and SQL statements to 100,000 bytes. The existing VM-instruction limit alone did not bound a large single-function allocation. Offline replay confirms the new limit does not change any saved tool result.

The frozen experiment's strict grader is preserved. Six Suite A failures arose from noncanonical survey identifiers or mathematically equivalent zero-valued quarter cells; their correction is a disclosed post hoc sensitivity, with every affected episode listed in `docs/REPAIR_OUTPUT_SENSITIVITY.md`. B-L5 also has representation conventions worth clarifying before a new study (for example, SQL NULL versus zero for a provider with no claims). No further normalization was silently introduced. Its strict failure count must not be read as evidence that every table value was wrong. These issues do not alter the primary completed-violation outcome.

For exact execution-source reproduction, use the commit recorded in the relevant manifest. To start a new campaign with current maintenance code, initialize a new output directory; the runner intentionally refuses to continue a frozen manifest whose source hashes differ. Root `RESULTS.md` is the interpretation of the completed experiment, including its limitations. Independent Village classifier validation and experiments with actual delegated work remain outstanding; neither is claimed by this repair.
