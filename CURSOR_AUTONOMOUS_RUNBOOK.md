# Running Movie Muse V2.1 Autonomously in Cursor

Version: `2.1.0`

## Important expectation

Movie Muse contains 47 substantial work packages and multiple external-provider gates. No single prompt, context window or agent run can be guaranteed to finish the entire product. The reliable form of autonomy is a persistent goal, dependency-ordered work, isolated worktrees/Cloud Agent branches, automatic testing, independent verification and a single authoritative status ledger.

Do not spend credits by asking several agents to rebuild the same foundation. Spend them on independent DAG nodes, adversarial testing, cross-platform verification and independent review.

## 1. Put the handoff in the real product repository

The handoff directory is a specification package, not yet a Movie Muse code repository. Create or open the repository Cursor will build, then copy every file—including `.cursor/`—from `MOVIE_MUSE_V2_HANDOFF` into its root.

Before using Cloud Agents, commit and push the baseline to GitHub, GitLab, Bitbucket or Azure DevOps. Cursor Cloud Agents clone a connected repository, work on separate branches and push changes back.

Run locally at the repository root:

```bash
python3 scripts/validate_handoff.py
./scripts/verify_all.sh
```

The first command must PASS. The second must initially fail with `MOVIE_MUSE_PROTOTYPE_VERIFICATION=NOT_READY`; that proves the release gate is fail-closed before implementation.

Commit this clean baseline before asking Cursor to implement MM-001.

## 2. Configure Cursor before spending credits

1. Open Cursor Dashboard → Spending. Record the exact credit balance, expiration/reset date, Cursor Models pool, Other Models pool and whether on-demand usage is enabled.
2. If you do not want charges beyond the expiring credit, disable on-demand usage or set a hard spend limit no higher than the amount you are willing to pay after credits. A spend limit is a ceiling, not a guarantee that every promotional credit applies to every product.
3. Connect the repository provider in Cursor Dashboard. Confirm Cursor has read/write access to this repository.
4. Configure a Cloud Agent environment/snapshot or `.cursor/environment.json` so a fresh VM can install dependencies and run tests without manual intervention.
5. Add secrets in Cursor's Cloud Agent Secrets UI, not in repository files. Add only the provider secrets needed for the current package.
6. Keep the supplied `AGENTS.md` and `.cursor/rules/*.mdc` at repository root. Cursor loads them automatically.

Current Cursor documentation: [usage and limits](https://cursor.com/help/models-and-usage/usage-limits), [models and pricing](https://cursor.com/docs/models-and-pricing), [Cloud Agents](https://cursor.com/docs/cloud-agent), [rules](https://cursor.com/docs/rules).

## 3. Choose models deliberately

- Use Auto → Intelligence or the strongest reliable reasoning/coding model visible in your account for MM-001–MM-021, architecture migrations, merge logic, security, FDX/layout and independent verification.
- Use Auto → Balance or a cost-efficient coding model for mechanical fixtures, adapters, UI plumbing and repeated test/debug cycles.
- Use different strong model families for implementation and independent verification when possible; independence is stronger when the verifier is not merely replaying the same model's assumptions.
- Use long/max context only if the option is actually available on your plan and a task needs it. Current usage-based plans do not include legacy Max Mode; do not rely on old tutorials.
- Keep contexts package-scoped. A focused agent that reads one work package plus its dependencies is usually more effective than repeatedly sending the entire repository.

## 4. Start the persistent orchestrator

In Cursor Desktop, open the repository, open Agent (`Cmd/Ctrl+I`), select Cloud if you want it to continue without your machine, and send:

```text
/goal Execute the complete Movie Muse V2.1 implementation as a persistent objective.

Read AGENTS.md, all .cursor/rules/*.mdc files, README_HANDOFF.md,
MOVIE_MUSE_V2_ARCHITECTURE.md, FEATURE_TRACEABILITY_AND_GAP_REVIEW.md,
MOVIE_MUSE_WORKING_PROTOTYPE_BUILD_PLAN.md, dependency_dag.yaml,
movie_muse_build_status.yaml, and CURSOR_MASTER_EXECUTION_PROMPT.md completely.

Run python3 scripts/validate_handoff.py first. Preserve all 47 work packages and
follow the dependency DAG. You are the sole manifest/orchestration owner. Work
through runnable packages, starting with MM-001. Implement, test, debug, commit,
invalidate stale dependent closure, and request independent verification exactly
as the execution prompt requires. Never mark your own implementation PASS. Never
replace required live evidence with mocks. Continue while safe runnable work
exists; if externally blocked, record the exact blocker and continue other
independent runnable work. Full success exists only when scripts/verify_all.sh
exits 0 and prints its exact PASS sentinel.
```

Cursor documents `/goal` as a long-lived objective. The optional built-in `/loop` skill can provide recurring check-ins while the goal runs. Do not use `/loop` to repeatedly restart failed work without reading the failure.

Official references: [Cursor Agent and `/goal`](https://cursor.com/docs/agent/overview), [Cloud Agent best practices](https://prod.cursor.com/docs/cloud-agent/best-practices).

## 5. Keep one manifest owner

The orchestrator is the only agent allowed to merge branches and edit the canonical `movie_muse_build_status.yaml`. Parallel worker agents must return a proposed pass/evidence record but must not mark the canonical item PASS.

This avoids manifest conflicts and prevents two branches from validating against different dependency states.

## 6. Use DAG waves for parallel credit-efficient work

Do not start a wave until every dependency needed by its nodes is merged and current PASS. Waves 0–10 are mostly sequential foundation work. Later waves contain useful parallelism:

```text
Wave 0:  MM-001
Wave 1:  MM-002
Wave 2:  MM-003, MM-004
Wave 3:  MM-005
Wave 4:  MM-006
Wave 5:  MM-007, MM-008
Wave 6:  MM-009, MM-010, MM-011
Wave 7:  MM-012
Wave 8:  MM-013
Wave 9:  MM-014
Wave 10: MM-015
Wave 11: MM-016, MM-017, MM-027
Wave 12: MM-018
Wave 13: MM-019
Wave 14: MM-020
Wave 15: MM-021
Wave 16: MM-022, MM-023, MM-024, MM-025, MM-031
Wave 17: MM-026, MM-030, MM-032, MM-033, MM-035, MM-040, MM-041
Wave 18: MM-028, MM-034, MM-036, MM-044
Wave 19: MM-029, MM-037, MM-045
Wave 20: MM-038
Wave 21: MM-039, MM-042
Wave 22: MM-043, MM-046
Wave 23: MM-047
```

These are topological availability waves, not permission to run every item simultaneously. Limit active implementation agents to roughly 2–4 until tests and merge throughput show the repository can support more. Use Cursor worktrees/Cloud Agent branches for every parallel item.

Cursor supports isolated worktrees and `/worktree`; `/best-of-n` is useful for competing implementations of a particularly risky bounded change, but only one result should be merged. See [Cursor worktrees](https://prod.cursor.com/docs/configuration/worktrees).

## 7. Worker-agent prompt

Start a separate Cloud Agent/worktree only after the orchestrator confirms the item is runnable:

```text
Implement exactly MM-NNN from the Movie Muse V2.1 build plan at the supplied
baseline commit. Read all repository rules and the item's architecture,
dependencies and acceptance criteria. Do not implement dependent work packages.
Do not edit the canonical build-status manifest and do not mark PASS.

Build the complete vertical slice, including migrations, errors, tests, security,
rights, accessibility, observability and user-visible behavior appropriate to
risk. Run focused and affected suites, debug root causes, commit the exact tested
state, and return: commit SHA, files changed, exact commands/results, evidence
paths, scope keys, external gates, limitations and a proposed pass-record payload
for an independent verifier. A mock may prove a contract but may not satisfy a
required live/sandbox gate.
```

After review, merge the implementation commit into the orchestrator branch before independent verification. Re-run affected dependencies and staleness checks after each merge.

## 8. Independent-verifier prompt

Use a fresh Cloud Agent/worktree and preferably a different strong model:

```text
Independently verify MM-NNN at commit <SHA>. You did not implement this item.
Read .cursor/agents/independent-verifier.md, the normative architecture and the
complete MM-NNN acceptance criteria. Start clean: fresh checkout, database,
cache and fixtures. Recompute its input fingerprint and dependency currency.
Run the supplied commands plus risk-based negative, authorization, offline,
concurrency, crash, stale-data, migration, platform or provider checks. Inspect
actual user-visible behavior and committed/content-addressed evidence.

Do not change product code and do not accept skipped required checks. Return a
manifest-ready verifier record with identity, independence basis, environment,
commit, commands, results, evidence and limitations. Return FAIL with the
smallest reproducible failure if any criterion is missing or stale.
```

Only the orchestrator may merge a verifier result into the canonical manifest and mark the package PASS.

## 9. External gates that cannot be made autonomous by prompting

Prepare these before their owner packages become runnable:

- Final Draft licensed/manual round-trip environment.
- Remote model API account and test budget.
- Zoom sandbox/OAuth application.
- Google Meet/Workspace sandbox and restricted-scope approval where required.
- Image-generation provider.
- Veo-class video provider.
- Test email/message delivery channel.
- Broker/carrier or approved insurance specialist sandbox.

Human account creation, legal acceptance, OAuth consent, spending authorization and licensed Final Draft inspection remain human actions. Cursor must record `BLOCKED_EXTERNAL`, not invent credentials or mark them complete.

## 10. Monitor progress and credit use

At least daily:

1. Check Cursor Dashboard → Spending for remaining credit, both usage pools and on-demand charges.
2. Check Cloud Agents for failed/setup-blocked runs before launching more agents.
3. Run `python3 scripts/validate_handoff.py` on the orchestrator branch.
4. Inspect `movie_muse_build_status.yaml` for `FAIL`, `BLOCKED_EXTERNAL` and `STALE`.
5. Merge small verified batches; do not let many long-lived branches drift.
6. Use expensive models on unresolved high-risk failures, independent verification and architecture—not repetitive formatting or duplicate brainstorming.

Cloud Agents are billed at selected-model API pricing, and larger context windows increase usage. Cursor's Spending dashboard shows remaining allowances and request-level usage; unused monthly usage does not roll over. Promotional account credits may have additional account-specific terms, so the dashboard is authoritative for whether a given run consumes the expiring balance.

## 11. CLI alternative

Cursor CLI reads `AGENTS.md` and `.cursor/rules` and supports non-interactive execution with full write access:

```bash
cursor-agent -p "Read CURSOR_MASTER_EXECUTION_PROMPT.md and execute the next runnable Movie Muse work package. Begin by validating the handoff and dependency state."
```

Use `cursor-agent ls` and `cursor-agent --resume=<thread-id>` to continue sessions. The CLI is useful for CI/automation, but Cloud Agents are preferable when you want the work to continue without keeping your machine online. See [Cursor CLI](https://docs.cursor.com/en/cli/using).

## 12. Completion check

Do not infer completion from the amount of credit consumed. Completion is only:

```bash
python3 scripts/validate_handoff.py
./scripts/verify_all.sh
```

with every manifest item and final-required external gate current PASS, followed by the exact final line:

```text
MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS
```

