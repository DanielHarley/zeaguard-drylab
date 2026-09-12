# Bioinformatics run records

This directory stores contextual records for consequential Bioinformatics executions.

The governing distinction is:

`DECISION -> ADR`

`EXECUTION -> Run Record`

A Run Record describes what was executed, using which recorded inputs and configuration, what validation occurred, what outputs were produced, and how the results may be interpreted. It does not replace manifests, machine readable reports, notebook outputs, or ADRs.

Create a Run Record when an execution needs durable context, interpretation, deviations, limitations, or links to methodological decisions. Ordinary notebook execution does not require one automatically.

Do not duplicate values that can be recovered reliably from a manifest or JSON report unless a review contract explicitly requires them. Prefer links and hashes. Keep scientific interpretation, limitations, deviations, and evidentiary boundaries in the Markdown record.

Each record must distinguish `directly demonstrated`, `derived/computed`, `inferred/interpreted`, and `unresolved` evidence. Execution success does not demonstrate scientific validity. Reproducibility does not establish scientific validity. Computational identity classifications remain conditional on the related decision policy.

Use the form `YYYY-MM-DD_short-run-name.md` and start from [0000-run-template.md](0000-run-template.md).
