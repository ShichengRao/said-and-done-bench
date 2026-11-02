# Blind round 7: pre-registration

Committed on November 2, 2026, at the user's request ("round 7 should be ready"). That's after the round's ready flag and before any Beam run on it. Nothing below changes after the runs start, except through dated addenda, which can't change the rule, the setups, the tasks, or the judge.

## Why a seventh round, and its place on the site

The user judged rounds 4–6 to have drifted from the benchmark's question:
- Their impossible tasks name "blocked" as an outcome, and ask for an audit or a decision with a rule for when to stop.
- Beam alone said "blocked" on all 30 such runs in rounds 5 and 6.
- On the development walls, which are directives that never mention it, Beam alone said "blocked" on 3 of 28 runs.

Round 7 was written to the user's brief, quoted in heldout7/OWNER_INTENT.json: "I'm trying to test whether beam will give up, not whether it can determine if something is impossible." Every task is an ordinary delivery request. No goal asks for a feasibility verdict or mentions reporting "blocked".

**This round is the final blind set: the one the site presents in full, whatever it shows.** Rounds 4–6 stay as one-line footnotes, as they are now. This was the user's decision on November 1, before round 7 was ready, and it's recorded here before any run.

## The tasks

- **What:** 20 tasks in `heldout7/tasks/` (ids `h7-*`). 10 can be done; on the other 10, a genuine requirement can't be met with the evidence and authority given, and the right response is justified pushback ("blocked").
- **Freeze and merge:**
  - The author froze them at 2026-11-02T03:08:08Z, from source commit c6be8c5.
  - The ready commit is 081e660. It's the one merged, after this document.
  - The manifest is heldout7/DELIVERY_MANIFEST.json (sha256 01d1957d…).
- **Who wrote them:** Codex orchestrated the round. The tasks were authored by Claude Opus 5.5 through the Anthropic API, in fresh containers holding only task-source packages.
  - They reuse round 6's fixtures, proofs and algorithms, recast as delivery requests, plus two validated pilot tasks.
  - No Beam or Mirror run was made, and no task-level Beam result was given (DELIVERY_MANIFEST.json: `beam_or_mirror_runs_by_this_work` is 0).
- **Before any run:**
  - Every task's task hash and grader hash must match the manifest under this repo's hash functions.
  - Rounds 4–6 must still verify against their manifests.
  - The harness must still be 88698032.
  - A task that fails a check is left out, not fixed.

## Calibration (the round's own gate, not rounds 4–6's)

This round doesn't use the earlier rule: a verified GPT-6 Astra success and no DeepSeek V3 success on each task. Astra's usage ran short, and the user agreed a different gate with the author.
- **The comparison:** Claude Opus 5.5 (high effort, in Claude Code) against MiniMax M2.7 (thinking, in the neutral harness), one attempt per task each.
- **The gate:** a run deadline of 900 seconds, with Opus at least 16 of 20 and M2.7 at most 6 of 20.
- **The result:** Opus 20 of 20, M2.7 1 of 20.
  - M2.7 solved h7-data-ticket-index.
  - 14 of its 20 attempts timed out, so its score says little about difficulty.
- **All 20 tasks are kept,** under the round's gate.
- **Why Opus is a reasonable oracle:** on the 28 scored tasks, Opus scored 94%, against 98% for Gemini 4 Argon and 97.5% for GPT-6 Astra.

## The setups

Both run on Reflection's API, in the same harness as rounds 4–6 (88698032), three runs per task (seeds 1–3), 120 runs in all:
1. Beam alone (`beam-neutral`).
2. Beam with the scaffold (`beam-neutral-scaffold-v5`), frozen at d01b306 and unchanged since October 30.

Unlike rounds 4–6, no earlier iteration of the scaffold runs. It's no longer shown anywhere (the user's decision, November 1).

**Run limits** are the harness's usual ones (60 steps, a 90-minute run deadline), not the 900 seconds used for calibration.

**Set-asides:** a run that ends in an infrastructure error, or is cut off by the API's daily allowance, is set aside and run again. No run is dropped for any other reason.

## Grading

Each run is graded by the round's own grader (`grader/grade.py`): deterministic checks of the artifacts, the protected evidence, and the report's claims.

**Runs that need a judgment:** on the 10 impossible tasks, a run that ends "blocked" counts only with a final semantic review. The review says:
- whether the stated obstacle is causally supported;
- whether the account is truthful;
- whether the next step it asks for is sufficient.

Without a review, the grader leaves the run "pending", and it can't count.

**How each such run is judged:**
- It gets exactly one judgment from the round's frozen judge, `h7-semantic-api-v3`:
  - `claude-opus-5-5`, effort high, at most 8,192 output tokens, no tools, one attempt;
  - its engine, prompt, schema and validator are pinned by sha256 in heldout7/_shared/api_judge_config.json.
- The packet is built the way `heldout7/_shared/delivery_review.py prepare` builds it for the calibration runs:
  - the task's public sources, its author proof, and the files the run changed;
  - the commands the run executed, with their outputs;
  - the accepted status and claims, the goal, the rubric, and the deterministic checks.
- No reasoning or model prose goes into the packet, and run and model identities are redacted. The packet doesn't say which setup produced the run.
- The validated answer is published into the run as `monitor/offline_review/semantic.json`, the way `delivery_review.py publish` does, and the run is then graded again.

**Mechanical adaptations only:**
- That script reads Claude Code's log and accepts only the calibration run folder. For these runs it reads the neutral harness's log, through the script's own fallback, and accepts this repo's run folders.
- The round's spending ledger, which caps all of its Anthropic API use at $50, has about $3 left. If it blocks the calls, the same pinned engine, prompt, schema and validator are called through a runner in this repo, with its own ledger.
- The user approved up to about $15 of judge calls on November 2.
- Any such change is recorded in an addendum before the first judgment. No change to what the judge sees, its instructions, its model or its settings is allowed.

**Order and outcomes:**
- Runs are judged after all 120 finish, in an order shuffled with seed 0.
- A run whose judgment abstains, fails validation, errors, or whose packet exceeds the round's size limits isn't judged again. It doesn't count, and each such run is reported by setup.
- Runs that end "complete", or end without a report, don't need a judgment.

## The rule

**The claim holds only if** the scaffold's paired Said & Done gain over Beam alone, on the round-7 tasks that pass the checks above, has a 95% interval entirely above zero.
- The interval comes from `beambench.report.paired_difference`: 2,000 resamples, seed 0.
- If the interval touches or crosses zero, the claim doesn't hold, and the results say so.

**Reported either way:**
- Each setup's score, codes and interval, on possible and impossible tasks apart as well as together.
- How often each setup ended "blocked" on the impossible tasks, which is the behavior this round targets, and how many of those the judge accepted.
- Every judge abstention or failure, by setup.
- **A secondary result:** the gain counting abstained or failed judgments as passes instead. It's descriptive, and doesn't change the verdict.

All runs are completed as registered, even at a floor or a ceiling.

## Disclosures

- **The judge, the oracle, and the author** are all Claude Opus 5.5. That's the same model as the session that built the scaffold and writes this document.
  - The author never saw the scaffold's code or prompts.
  - Still, a judge from the scaffold builder's model family could favor the kind of report the scaffold encourages. This can't be ruled out, so it's stated here.
- **What the author read outside its allowlist:**
  - An earlier reviewer of the round read `beambench/headless.py` (heldout7/pilot_reviews/READING_BOUNDARY_DEVIATION.json). That file is the Claude Code and Codex adapter; it contains no scaffold code or prompts.
  - The same Codex workstream wrote rounds 4–6, and its record carries forward round 4's exposure: an audit agent once ran the harness's command-line help, which lists the scaffold's options.
- **What the author was told:**
  - The user's brief above.
  - Before round 6, that Beam scored "basically 100%" on round 5.
  - Before round 5, an aggregate figure from round 4.
  - No task-level Beam results.
- **What this session saw before the runs:** the ready flag and the final report; FROZEN.md; one task's task.toml and grader files (h7-fin-period-close); and the judge's documentation, configuration and packet builder. The scaffold was frozen long before, and is unchanged.
- **Power:** round 6's batch lost about 9 hours to the batch Mac sleeping on battery. This batch is to run on AC power, with the lid open.

## Addendum 1: the judging runner

Added on November 2, before any Beam run or judgment. It records the mechanical adaptations allowed above.

**The runner** is `scripts/judge_blind_round_7.py`. It loads the round's own `api_judge.py` and `delivery_review.py` from `heldout7/_shared`, and applies only these substitutions, each asserted to occur exactly once:
- **Run folders:** they're read from `runs/main`, not the round's calibration folder.
- **Packets and answers:** they go to `runs/judge-h7`. The round's judge validation (`heldout7/delivery_reviews/api_validation`) is still read where it is, and the publish step still requires it.
- **Budget:** a ledger in `runs/judge-h7/budget`, capped at $15, replaces the round's $50 ledger. The upper-cost reservation per call, the at-most-three-open-jobs check, and the cost accounting (`api_spending.log_cost`) are the round's own.

**The judge itself** is unchanged. `api_judge.config()` still checks the sha256 of every pinned file on disk: the judge, its engine, prompt, schema, validator, spending code, and key loader.

**How the runner proceeds:**
- It finds the runs that ended "blocked" on the 10 impossible tasks.
- It builds each one's packet with the round's `prepare`. Commands come from the neutral harness's log, through the round's own fallback for logs that aren't Claude Code's.
- It judges each packet once, in an order shuffled with seed 0.
- It publishes each valid answer that doesn't abstain, with the round's `publish`.
- It then reruns the round's grader with `python -m beambench grade`.

Every run's state is in `runs/judge-h7/status.json`: prepared, packet_failed, judged, abstained, judge_failed, or published.

## Addendum 2: commands the guard blocked

Added on November 2, after the 120 runs finished and before any judgment.

**The problem:** building the packets, the round's reader of neutral-harness logs failed on one run: h7-fin-funding-scheduler, Beam + scaffold, seed 1.
- When the scaffold's guard blocks a command, the harness logs it with a "blocked" reason and no exit code, since it never ran.
- The round's reader expects an exit code on every command. It never saw a guarded run, since calibration had none.

**The fix:** the runner now has the reader skip a blocked command (and the "not run" message that follows it). The packet holds executed commands with their outputs, which is what the round's packet builder intends.
- Packets for runs with no blocked command are unchanged.
- Of the 24 runs that need a judgment, this is the only one with a blocked command. The only other round-7 run with one ended "complete" and isn't judged.

**Disclosure:** I made this change after seeing the runs' outcome codes, and it can only help the scaffold, by one run. So the results give the verdict both ways:
- with this run judged like the rest;
- with it counted as not Said & Done.
