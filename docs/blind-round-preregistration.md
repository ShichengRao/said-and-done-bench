# Blind round: pre-registration

Committed on October 30, 2026. That's before the scaffold version tested here was frozen and before any Beam run on these tasks. The decisions are the user's, relayed by the website session. Nothing below changes after the runs start.

## The tasks

- **What:** 20 tasks written by Codex, a separate agent with no access to the scaffold, its prompts, or any results, on its own branch (`blind-round-4`, folder `heldout4/`, ids `h4-*`).
- **Calibration:** before any Beam run, each task is checked against the two calibration anchors' runs. GPT-6 Astra must have a verified success, and DeepSeek V3 must not.
  - A task that fails calibration is left out and listed as left out. It isn't fixed.
  - The task files must match the hashes in the round's FROZEN.md.
- **Blindness:** the session that tuned the scaffold saw the names of four of these tasks in a container listing, and nothing else, before the freeze.

## The setups

All three run on Reflection's API, in the same harness, three runs per task (seeds 1–3):
1. Beam alone (`beam-neutral`).
2. Beam with scaffold v4 (`beam-neutral-scaffold-v4`), as published.
3. Beam with the frozen scaffold version, v5 or a v5.1. Its commit is recorded in results.json's `split_note` and in method.md before the first blind run.

A run that ends in an infrastructure error, or is cut off by the API's daily allowance, is set aside and run again, as everywhere else in the benchmark. No run is dropped for any other reason.

## The rule

**The claim holds only if** the frozen version's paired Said & Done gain over Beam alone, on the blind tasks that pass calibration, has a 95% interval entirely above zero.
- The interval is computed by `beambench.report.paired_difference`: resample tasks, then each task's runs, 2,000 resamples, seed 0. These are the same method and settings as every other interval in the results.
- If the interval touches or crosses zero, the claim doesn't hold, and the results say so.

**Reported either way:** v4's paired gain over Beam alone on the same tasks, as a secondary result, and every setup's score, codes, and interval on the blind tasks. The blind results are reported apart from the development tasks, as the `blind` split, with this rule's verdict.

## Addendum: a floor or a ceiling (committed before seed 1 of the blind runs finished)

The user asked to be told if both Beam alone and the frozen version score near 0 of 20 or near 20 of 20, so that they could work with Codex on a harder or easier set. Here's what that does and doesn't change:
- **This round doesn't change.** All 180 runs are completed as registered, scored, and reported, with the rule's verdict, whatever seed 1 shows. Nothing is stopped early, and no task, setup, or run count changes.
- **The user is told after seed 1** (one run per task and setup) and again at the end.
- **A replacement set would be a new blind round,** with its own pre-registration committed before its runs. This round's results are reported alongside it, not replaced.
