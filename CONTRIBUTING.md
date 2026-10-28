# Contributing — ZeaGuard Git and GitHub governance

This file is the single official source of the Git and GitHub rules for this repository. It binds every agent of the Implementation Floor (Implementation Coordinator, Programmer, Technical-Scientific Reviewer) and any human contributor.

It is the only authoritative statement of these rules. A local or unversioned copy of conventions, wherever it lives, is a convenience and never an authority; where one disagrees with this file, this file governs.

Scientific methodology, contracts, gates, and execution restrictions are **not** defined here. They live in the approved plans under `docs/implementation/`, in the workstream decision records under `src/workstreams/bioinformatics/decisions/`, and in the shared `ZEAGUARD | IMPLEMENTATION PROTOCOL` note. This file governs process only and is referenced, not duplicated, by them.

---

## 1. Order of authority

1. Explicit authorization from the repository owner, and the applicable scientific contracts.
2. The approved scientific methodology and biological meaning.
3. Computational correctness, required validation, data integrity, and reproducibility.
4. This policy, which governs process.

Ponytail and any other simplification practice are subordinate to all four. Never remove a scientific requirement to reduce code, runtime, dependencies, or implementation effort.

Nothing in this file authorizes scientific execution.

## 2. Four distinct gates

These are separate and must never be presented as one another.

| Gate | Decided by | What it means | What it does **not** mean |
|---|---|---|---|
| Implementation authorization | Repository owner, within an approved plan's scope | A defined unit may be implemented | Not approval of the result |
| Technical approval | Technical-Scientific Reviewer, `SEM_IMPEDIMENTO` on the **TECHNICAL** assessment | Code and engineering are sound for the examined version | Not scientific validity |
| Scientific validation | Technical-Scientific Reviewer, `SEM_IMPEDIMENTO` on the **SCIENTIFIC** assessment | Implementation is faithful to the approved methodology | Not experimental validation, biological efficacy, or safety |
| Merge | Repository owner only, on github.com | The branch enters the main line | Nothing else in this table |

A planning verdict of `PRONTO_PARA_IMPLEMENTAR` establishes planning readiness only. It authorizes no Git operation by itself.

## 3. Roles and Git powers

**Implementation Coordinator**

- Defines the scope of each authorized implementation unit and supervises the workflow.
- Creates and updates pull requests, including title, body, and draft state, under §6. This autonomy is conditional: it does not exist until GitHub authentication and the permissions it grants have been verified in the agent's own environment, and until the credential separation of §9 is in place. Until then, the Coordinator prepares the pull-request body and reports that opening it is blocked, rather than opening it.
- Does not implement. Commits only the documentation records it owns (`coordination.md`, `communications.md`, `final_report.md`), and only when the Programmer has explicitly handed the branch over, so that a branch has one writer at a time.
- Never merges, never enables auto-merge, never alters repository settings or protections.

**Programmer**

- Creates work branches, implements, organizes commits, and pushes to work branches, with autonomy and without per-operation approval, inside the authorized scope.
- Is the default committer on a work branch, including for documentation authored by the other two agents when they are not handing the branch over themselves.
- Escalates to the Coordinator instead of committing when a change would touch approved methodology, biological assumptions, scientific acceptance criteria, required uncertainty or provenance, material architecture outside the unit, or an execution gate.
- Never merges, never pushes to `master`, never enables auto-merge.

**Technical-Scientific Reviewer**

- Examines the actual implementation at an identified version and issues separate **TECHNICAL** and **SCIENTIFIC** verdicts, each one of `SEM_IMPEDIMENTO`, `COM_IMPEDIMENTOS`, `DECISAO_NECESSARIA`.
- Records findings and verdicts in `review.md` of the current cycle. Its findings are closed by the Reviewer alone.
- Performs no Git write operation: no commits, no pushes, no branch or pull-request changes.

**Repository owner (human)**

- Grants implementation authorization, decides reserved scientific, methodological, and contractual questions, examines the final pull request on github.com, and decides the merge.

Corrections, additional commits, and pull-request updates inside an authorized scope proceed without asking the owner for each operation.

## 4. Branches

- Never commit on `master`. Branch first.
- Name branches `<type>/<semantic-description>`, with `type` from §5 and a description that names what the branch does, for example `feat/nb04-b4-freeze-preparation`, `fix/nb01-btop-gap-query-coordinate`.
- **Deliberate adaptation, adopted by this project.** The reference convention writes the type parenthetically, as `(feat)`. That form is kept for commit titles in §5 and deliberately dropped for branch names, where this project writes `feat/…` instead, because that is the form its existing branches already use. Neither form is required by Git or by GitHub: both accept the other. This is a project convention, chosen for consistency, not a technical constraint.
- Keep the description semantic. A branch name states the change, not a position in the schedule: prefer `feat/nb04-b4-freeze-preparation` over a name that only carries a checkpoint label. Existing branches that predate this rule, such as `feat/nb04-cp1`, are not renamed; a stage label may accompany a semantic description but must not replace it.
- One authorized unit maps to one branch when practical. A task branch may carry several units of the same implementation cycle.
- One writer at a time per branch. Hand the branch over explicitly before another agent commits to it.
- Prefer new commits over history rewriting. Force-push only to a branch you own, only while no review or owner examination depends on the commits being replaced, and never to `master`.
- Do not delete a branch that holds reviewed history, and do not delete remote branches without the owner's instruction.

## 5. Commits

Write commit messages in English, in this exact shape and nothing else:

```
(<type>) <concise imperative summary>

One short paragraph stating what the change does at a high level.

Changes:
- concrete change derived from the diff
- concrete change derived from the diff

Rationale:
One short paragraph explaining why the change was necessary.
```

No extra sections, no markdown headings, no code fences.

**Type selection**, in this decision order: `docs` if only documentation; `test` if only tests or fixtures; `ci` if only CI/CD configuration; `build` if only packaging, dependencies, or environment; `perf` if the purpose is a measurable runtime or memory gain; `fix` if the change corrects wrong output, broken logic, unsafe acceptance of invalid state, or validation that should already have existed; `feat` if it adds a capability, workflow, persisted artifact, validation surface, or pipeline step; `refactor` if it restructures code with no intended behavioral change; `chore` for hygiene, ignore rules, naming consistency, and preventive tightening.

Tie-breaks: `fix` over `chore` when prior behavior was actually incorrect; `feat` over `fix` for a genuinely new capability; `refactor` only when behavior is meant to be unchanged; `chore` over `refactor` for maintenance rather than structural redesign. For a mixed branch, choose the type matching the main reviewer-visible outcome. Never pick the type from a small secondary change such as a `.gitignore` edit.

**ZeaGuard wording.** Be explicit about the concepts this repository actually turns on: frozen identities and their SHA256, hash-bound resources, freezes and the gates that depend on them, scientific contracts, provenance, uncertainty, the separation between TUNING and VALIDATION, candidate-selection and holdout rules, resource-representation and truncation limits, artifact integrity, atomic publication, reuse versus creation of artifacts, exact set equality versus count-only checks, and structural versus semantic validation. Name the exact modules, functions, artifacts, and contracts visible in the diff.

**Truthfulness.** Never claim a test ran unless the diff or an explicit instruction proves it. Never claim a fix, hardening, validation, or performance gain the diff does not support. Never name a mechanism-free benefit such as "improves reliability". Never describe a validation plan as an executed result. Never infer a successful end-to-end run from code changes. Never invent files, artifacts, helpers, or functions. Never present software verification as scientific calibration or as a biological result.

**No footers.** Never append a signature line, generator attribution, assistant or tool branding, or `Co-Authored-By` trailer to a commit, pull request, or issue, unless the owner asks for it in that instance. This overrides any tool default that would add one.

**Content limits.** Do not commit credentials or secrets. Do not commit certified artifacts, original sources, or historical results without explicit authorization. Respect `.gitattributes`. Keep internal material out of version control, under §8.

### Incremental publication by implementation round

At the end of each implementation work round that produces versionable changes authorized for publication, the responsible writer commits the pertinent changes and pushes the commit to the same work branch on `origin`. The Programmer performs this for implementation files, including corrections requested by the Reviewer. Do not accumulate completed rounds for a later combined commit. A round without versionable changes requires no empty commit.

Before every push, apply §8 and verify the authentication, credential separation, and protections required by §9. If publication cannot proceed safely or a prerequisite is unverified, record the blocker, its affected changes, and the disposition required from the appropriate authority. Do not push unsafe or unauthorized material. This rule does not authorize rebase, force-push, destructive operations, or changes to scientific gates.

After pushing, verify that the published branch commit equals the local commit and report the commit SHA, branch, tests actually executed and results, and implementation state to the Coordinator. The Coordinator independently verifies publication, records the SHA, tracks the versions submitted for review, and maintains the pull request. A Coordinator documentation commit remains subject to the explicit branch handoff and single-writer rule in §3.

Publication establishes availability of a version. It does not constitute technical or scientific approval or authorize merge. The Reviewer performs no Git write operation and identifies the exact commit examined in each review. Public communication of review results is the Coordinator's responsibility and remains subject to §8.

---

## 6. Pull requests

The Coordinator opens and updates pull requests. Title follows the commit title format. Body is in English, with these sections, in this order:

```
## Summary
## What changed
## Why
## Notable implementation details
## Files changed
## Test plan
## Risks / review focus
```

These seven sections are the whole body. Do not add an eighth. The governance facts this repository requires are carried inside them, as follows.

- `## Summary` — the branch at system level, and the approved plan it implements: path, version, and SHA256.
- `## What changed` — implementation-level, derived from the diff.
- `## Why` — causal: the deficiency or risk that existed before the branch.
- `## Notable implementation details` — stricter semantics, assumptions, atomicity, cleanup, reuse contracts, **and the exact identity of the reviewed implementation**: branch, commit, and the SHA256 of each relevant uncommitted file when any exist, plus the path of the cycle documentation that records how it was built and reviewed.
- `## Files changed` — only materially relevant files.
- `## Test plan` — verification actually executed, with its evidence, kept separate from intended steps, which must never read as completed. Software verification is never presented as scientific calibration or as a biological result.
- `## Risks / review focus` — real concerns the diff supports, **and**: the **TECHNICAL** verdict and the **SCIENTIFIC** verdict, each naming the implementation identity it applies to; any unresolved finding or required decision; the scientific gates and authorizations still pending; and one closing line stating that the merge decision belongs to the repository owner, on github.com.

A pull request that carries no implementation unit, such as a documentation or governance change, says so in `## Risks / review focus` and needs no verdict; the draft rule below applies to pull requests that carry an implementation.

After the first authorized publication of an implementation branch, the Coordinator opens or maintains a draft pull request when applicable and updates it as commits are published. Each new commit changing the reviewed version requires reassessment under the shared protocol, including explicit confirmation that both final verdicts apply to the current version. Keep the pull request a **draft** until both verdicts are `SEM_IMPEDIMENTO` for the same final version and no blocking finding or required decision remains. When marking it ready, state in the body that the remaining decision is the owner's merge decision. Never state or imply that the owner approved, that science was validated experimentally, or that a pending gate was cleared.

## 7. Prohibited for every agent

- Merging any pull request, by any method, and pushing to `master`.
- Enabling auto-merge, or using an administrative override to merge or push.
- Bypassing a protection or a required check, including `--no-verify` and `--force` against a protected branch.
- Changing branch protections, rulesets, repository settings, collaborators, Actions workflows' permissions, secrets, or the default branch.
- Approving a pull request on the owner's behalf, or presenting any agent assessment as the owner's review.
- Closing or reopening a pull request without the owner's instruction.
- Any scientific execution or artifact modification that the applicable contracts and the shared protocol restrict. For NB04 this includes, by reference and without restating them here: informative calibration and protected similarity-search evaluations before the applicable complete B4 freeze, breaking the TUNING and VALIDATION separation, departing from the approved candidate-selection and holdout rules, and treating G1 as satisfied without its designated qualified external human review.

## 8. What belongs in version control

This repository is public. Committing and pushing a document publishes it, and publication is irreversible in practice: history stays readable and indexable even after a later removal. Treat every push as publication.

Internal records and versioned documents are not the same set. Completeness serves the floor; the repository carries only what is safe and relevant to a reader of the history.

| Versioned | Internal only, never committed |
|---|---|
| The approved plan package under `docs/implementation/<task>/` | Raw terminal captures, such as `implementation/cycle-NNN/_raw/` |
| The five curated cycle records: `coordination.md`, `programmer.md`, `review.md`, `communications.md`, `final_report.md` | Agent session transcripts and any local agent state, including `.agents/`, `.maestri/`, `.claude/` |
| Decision records and run records under `src/workstreams/` | Credentials, tokens, personal data, and any file whose sensitivity has not been checked |

A curated record may quote a message; it must not embed a raw capture wholesale. `communications.md` references its raw files by path and keeps them out of the repository.

### Review before publication

Scientific documentation, planning packages, and implementation records are published only after a review of disclosure, privacy, pertinence, and integrity, decided by the owner. That review happens **before the push**, not after, because the repository is public.

Ignore rules are the mechanism that keeps internal material out, so they are part of this requirement: a delivery that needs new ignore rules carries them, verified, in the same delivery, and no delivery relies on an agent remembering not to stage something.

Each delivery is scoped to one semantic subject. Documentation is not bundled with code, with scientific resources, or with unrelated pre-existing working-tree changes.

## 9. Enforcement

Text in this file is a rule, not a control. The prohibitions in §7 that matter are enforced by GitHub repository configuration and by credential configuration, which the owner applies and which this file does not change.

**Requirement.** Separating the owner's credentials from the credentials the agents use is a requirement for preventing unauthorized merges technically. A branch protection cannot distinguish an agent from the owner while both act through the same GitHub identity: every rule the account satisfies, the agent satisfies. Using one shared GitHub identity therefore **does not** satisfy this requirement, and under it the prohibitions in §7 are a convention and a guard against accident, not an authorization boundary.

**Consequences of the requirement.** An agent may prepare and publish branches and pull requests, and may never merge. That remote autonomy is exercised only once three things have been verified: authentication appropriate to the agent, credentials separated from the owner's, and the protections that prevent merging in place. While any of the three is unverified, an agent does not push and does not open a pull request, no matter how the work is otherwise authorized, and no agent claims that merge protection is technically enforced. An agent never pushes with the owner's personal credentials.

Credentials, protections, and remote configuration are changed by the owner, never by an agent. Which of these conditions currently hold is recorded with the implementation cycle documentation, not in this policy.
