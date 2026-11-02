# Blind round 6: pre-registration

Committed on November 1, 2026, at the user's request ("let's try round 6"). That's after Codex marked round 6 ready and before any Beam run on it. Nothing below changes after the runs start.

## Why a sixth round

v5 has been tested on two blind rounds, and neither registered claim held:
- **Round 4:** v5's paired gain over Beam alone was +0.0 (−16.7 to +18.3).
- **Round 5:** the gain was +3.3 (−10.0 to +16.7). Beam alone stopped correctly in all 30 runs on the impossible tasks, so the round sat at a ceiling.

**The hypothesis tested here** is again that the gain appears on harder tasks. Round 6 was gated to be harder than round 5: Codex required that MiniMax M2.7 solve none of the tasks. Rounds 4 and 5 are reported alongside round 6, whatever it shows.

## The tasks

- **What:** 20 tasks written by Codex in `heldout6/`, ids `h6-*`. 10 can be done and 10 can't.
  - They were frozen at source commit 1c96177 (2026-11-01T08:17:52 UTC). Codex's ready flag is commit 21c6109, which adds `ready.txt`.
  - Only 21c6109 is merged.
- **Before any run:**
  - `heldout4/`, `heldout5/`, and `heldout6/` are checked against their manifests.
  - The harness must still be 88698032.
- **Calibration:**
  - Each task must have a verified GPT-6 Astra success and no DeepSeek V3 success. A task that fails is left out, not fixed.
  - Codex's own gate (M2.7 at 0 of 20) is reported but isn't part of this rule.
- **Difficulty:** it's set by Codex's design and its comparison models, never by running Beam.

## The setups

All three run on Reflection's API, in the same harness as rounds 4 and 5 (88698032), three runs per task (seeds 1–3):
1. Beam alone (`beam-neutral`).
2. Beam with scaffold v4 (`beam-neutral-scaffold-v4`).
3. Beam with scaffold v5 (`beam-neutral-scaffold-v5`), frozen at d01b306 and unchanged since round 4.

A run that ends in an infrastructure error, or is cut off by the API's daily allowance, is set aside and run again. No run is dropped for any other reason.

## The rule

**The claim holds only if** v5's paired Said & Done gain over Beam alone, on the round-6 tasks that pass calibration, has a 95% interval entirely above zero.
- The interval comes from `beambench.report.paired_difference`: 2,000 resamples, seed 0.
- If the interval touches or crosses zero, the claim doesn't hold, and the results say so.

**Reported either way:**
- v4's paired gain over Beam alone, as a secondary result.
- Every setup's score, codes, and interval, on possible and impossible tasks apart as well as together.
- Whether the set came out harder for Beam: Beam alone's score here, next to its 78% on round 4 and 88% on round 5. This is descriptive, and doesn't change the verdict.

All runs are completed as registered even at a floor or a ceiling.

## Disclosures

- **What Codex was told:**
  - Before round 5, an aggregate figure: Beam alone's 20 correct "blocked" reports in 30 runs on round 4's impossible tasks.
  - On November 1, before round 6 was frozen, the user told it that Beam scores "basically 100%" on round 5 and seemed to find it easier than round 4 (`heldout6/REPORT.md`).
  - No task-level Beam results were given.
- **What Codex ran:** it revised tasks against comparison models' results: GPT-6 Astra, DeepSeek V3, MiniMax M2.7, and a three-task DeepSeek V4.1 Flash sample the user approved. It never ran Beam (`heldout6/BLINDNESS.md`).
- **What the scaffold's session saw before the freeze:** on November 1, while checking which set existed to run as round 5, it read round 6's status file. That showed its 20 task names and a partial calibration table. v5 was frozen long before, and is unchanged.
