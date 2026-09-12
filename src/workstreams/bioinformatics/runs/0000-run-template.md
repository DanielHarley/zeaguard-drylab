# Run ID

`<stable run identifier>`

## Date

`YYYY-MM-DD` with timestamp and timezone when available.

## Commit

`<commit hash>` and whether the worktree was dirty.

## Branch

`<branch name>`

## Execution status

`PLANNED | RUNNING | COMPLETED | FAILED | COMPLETED_FOR_INSPECTION_CANONICAL_REPRODUCTION_PENDING`

## Question / objective

State the bounded computational objective.

## Inputs

Link manifests and immutable inputs. Reference their hashes rather than copying metadata already represented reliably elsewhere.

## Configuration

Link configuration and related ADRs. Record deviations from the declared canonical environment.

## Method

Summarize the executed transformation and identify the implementation entry point.

## Outputs

Link machine readable outputs and their manifest when one exists.

## Validation / QC

Record checks actually executed, their result, and the scope of each check.

## Results

Record observations required for review. Prefer links to structured result files for complete metrics.

## Interpretation

State the interpretation conditional on the declared method and evidence.

## What this run does NOT establish

State claims outside the run's evidentiary scope. Successful execution does not demonstrate scientific validity. Computational reproducibility does not establish scientific validity.

## Anomalies / deviations

Record departures from configuration, environment, protocol, or expected behavior. Use `none observed` only when supported.

## Related decisions

`<relative links to ADRs>`

## Related Issue / PR / commits

`<links and hashes, or not recoverable>`

## Evidence classification

1. `directly demonstrated`: direct inputs, manifests, tool output, environment observations, and integrity checks.
2. `derived/computed`: outputs produced from recorded inputs by the declared method.
3. `inferred/interpreted`: conclusions dependent on policy thresholds or scientific judgment.
4. `unresolved`: absent or insufficient evidence, including identities that the method cannot distinguish.
