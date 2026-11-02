# Blind round 5: pre-registration

Committed on October 30, 2026, before any task in this round is frozen or run. The decisions are the user's, relayed by the website session. Nothing below changes after the runs start.

## Why a fifth round

Round 4's pre-registered claim didn't hold: scaffold v5's paired Said & Done gain over Beam alone was +0.0 points (95% interval −16.7 to +18.3), and Beam alone scored 47 of 60 (`docs/blind-round-results.md`, 3056d6d). **The hypothesis tested here** is that the gain appears on harder tasks. Round 4's result stands, and it's reported alongside this round's, whatever this round shows.

## The tasks

- **What:** 20 tasks written by Codex, a separate agent with no access to the scaffold, its prompts, or any results. They go on Codex's own branch (`blind-round-5`), in a new folder (`heldout5/`), with ids `h5-*`.
- **Disclosure:** Codex had already started when this was written. It was told only to make the problems harder than round 4's. It got no per-task results and nothing about where Beam succeeded or failed, though the instruction itself implies round 4 was too easy. Anything else Codex is told about earlier rounds before its freeze is added here, dated, before the freeze.
- **Difficulty is set by design.** The only model runs used to check or select tasks are the calibration anchors' below. Neither Beam nor any other model in the comparison is run on a task before the freeze, so no task is chosen on Beam's baseline. A check Codex runs after the freeze on other models, as in round 4, is reported, and doesn't change or drop any task.
- **Calibration:** before any Beam run, each task is checked against the two calibration anchors' runs. GPT-6 Astra must have a verified success, and DeepSeek V3 must not.
  - A task that fails calibration is left out and listed as left out. It isn't fixed.
  - The task files must match the hashes in the round's FROZEN.md.
- **Round 4 stays as graded.** Round 4's tasks (`heldout4/`, merged at 826a69c) aren't edited. When round 5 is merged, `heldout4/` is checked against round 4's `FREEZE_MANIFEST.json`, and the merge doesn't go ahead if anything there changed.
- **Blindness:** the session that built the scaffold hasn't opened Codex's branch and won't until the round is frozen and merged. Since round 4, that session has read round 4's results, grades, and the scaffold's verdicts, and some of Beam's own reasoning on round 4's tasks. It hasn't seen anything of round 5.

## The setups

All three run on Reflection's API, in the same harness as round 4 (harness 88698032), three runs per task (seeds 1–3):
1. Beam alone (`beam-neutral`).
2. Beam with scaffold v4 (`beam-neutral-scaffold-v4`), as published.
3. Beam with scaffold v5 (`beam-neutral-scaffold-v5`), frozen at d01b306 (tag `scaffold-v5-frozen`), unchanged since round 4. Nothing learned from round 4 goes into it.

A run that ends in an infrastructure error, or is cut off by the API's daily allowance, is set aside and run again, as everywhere else in the benchmark. No run is dropped for any other reason.

## The rule

**The claim holds only if** v5's paired Said & Done gain over Beam alone, on the round-5 tasks that pass calibration, has a 95% interval entirely above zero.
- The interval is computed by `beambench.report.paired_difference`: resample tasks, then each task's runs, 2,000 resamples, seed 0. These are the same method and settings as round 4 and every other interval in the results.
- If the interval touches or crosses zero, the claim doesn't hold, and the results say so.

**Reported either way:**
- v4's paired gain over Beam alone, as a secondary result.
- Every setup's score, codes, and interval, on possible and impossible tasks apart as well as together.
- Whether the set came out harder: Beam alone's score here, next to its 47 of 60 on round 4. This is descriptive only, and doesn't change the verdict.

As in round 4, all runs are completed as registered, scored, and reported, with the rule's verdict, even if the scores sit at a floor or a ceiling. A replacement set would be its own pre-registered round, reported alongside this one.

## Addendum: what the scaffold's session saw (October 30, before any round-5 Beam run)

- **Task names:** while checking its own runs, the session that built the scaffold listed processes and containers with a filter broad enough to match Codex's calibration runs. It saw four round-5 task names and nothing else of those tasks: `h5-fin-credit-release`, `h5-fin-refund-replay`, `h5-data-redacted-export`, `h5-data-region-placement`. v5 was frozen at d01b306 before this and doesn't change.
- **Calibration models:** the same listing showed Codex running two models on round-5 tasks before its freeze: DeepSeek V4.1 Flash, which is one of the benchmarked models, and MiniMax M2.7. This doesn't match "Difficulty is set by design" above. How it's resolved is the user's decision, and it's recorded here before the freeze.

## Addendum: difficulty checks (the user's decision, October 30, before the freeze)

This replaces "Difficulty is set by design" above.
- Codex may check difficulty with the two anchors and with intermediate models, and may drop or revise tasks on those runs before its freeze. The intermediate models include DeepSeek V4.1 Flash, one of the benchmarked models, and MiniMax M2.7.
- Its FROZEN.md lists every model run on the tasks before the freeze.
- **Beam is never run on a round-5 task before the freeze.** No task is chosen on Beam's own results.
- **Why this doesn't bias the rule:** the rule is a paired comparison within Beam (v5 against Beam alone on the same tasks). Flash's leaderboard score comes from the 28 main tasks, not these.
- The calibration check above still applies after the freeze: a task that fails it is left out, not fixed.

## Addendum: running round 5 as it stands (November 1, before any round-5 Beam run)

- **The user's decision:** Codex ran out of credit before finishing, and the user said to run the set that exists.
- **What exists:** round 5, which Codex froze at 2026-10-31T05:33 UTC (commit fd61473, from source commit 00361f5). It has 20 tasks, `h5-*`: 10 can be done and 10 can't.
  - Codex then started a round 6 (`heldout6/`, `h6-*`). It isn't frozen, and only some of its tasks have calibration runs. It isn't used.
- **The merge:** only the freeze commit, fd61473, was merged (651b8ab). It adds `heldout5/` and 21 task tests, and changes nothing else.
- **The checks passed** (`scripts/verify_blind_round.py heldout4 heldout5`):
  - `heldout4/` matches its manifest.
  - Every round-5 task, grader, and source file matches round 5's manifest.
  - The harness is 88698032, the frozen build.
- **Calibration:** every round-5 task has a verified GPT-6 Astra success and no DeepSeek V3 success, so none is left out.
- **Difficulty:** DeepSeek V4.1 Flash had a verified success on all 20 tasks (one run each), and MiniMax M2.7 on 4. Codex's freeze record says the set isn't shown to be harder than round 4. As registered, the round runs in full whatever it shows.
- **Disclosures from Codex's record** (`heldout5/BLINDNESS.md`, `heldout5/ROUND4_BASELINE.json`):
  - Codex was given two aggregate figures. Beam said "blocked" correctly in 20 of 30 attempts on round 4's ten tasks that can't be done, and passed 2 of 28 runs on the main walls. Codex asked for task-level results and was refused. It received none.
  - This corrects the first addendum's "nothing about where Beam succeeded or failed": that holds at the task level, but these aggregates were given.
  - Each round-5 task is a redesign of the round-4 task with the same name.
  - Codex didn't open the scaffold's code or prompts. Round 4's command-line-help exposure (`heldout4/BLINDNESS.md`) stays on record.
