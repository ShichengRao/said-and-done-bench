# Reading and evaluation exposure

The current brief was read in full before this redesign. It specifies heldout5, h5 IDs, and only codex-2/codex-3 for native calibration. The existing isolated blind-round-4 worktree and branch were reused; no main history was inspected.

The owner reported that Beam correctly marked blocked in 20 of 30 attempts across the ten impossible Round 4 tasks (three attempts each), and separately reported 2/28 on the original task collection. The owner declined a request for task-level results to avoid tailoring the redesign to Beam. No task-level Beam results, transcripts, task identities behind those successes/failures, or original-result files were received or sought afterward. The new design is informed by aggregate feedback; it is not described as having zero evaluation exposure.

Review uses this team's own Round 4 tasks, calibration and sanity-check evidence, the expressly permitted harness/task helpers, and new Round 5 source and runs. Public Reflection workflow materials were refreshed before authoring. No scaffold implementation, scaffold prompt source, forbidden prior experiment directories, benchmark website results, or main Git history were opened. No Beam or Mirror run was performed.

The earlier high-level CLI-help exposure and other limited reading disclosures in [Round 4's record](../heldout4/BLINDNESS.md) remain applicable history. CLI help was not used in this redesign. Normal runtime imports and cryptographic hashing of harness files are required by the unchanged run/freeze infrastructure; they are not source inspection of the forbidden modules.

Independent source reviewers inspect other authors' contracts, references, graders, and controlled temporary examples. Calibration agents run in fresh task containers without access to solutions or graders. Task authors do not receive additional Beam-specific signals. All calibration-driven revisions, if any, must remain visible with their prior source and outcomes.
