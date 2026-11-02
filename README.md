# Said & Done

A benchmark of the gap between what a coding agent **says** it did and what it actually **did**. It has 28 offline tasks, each a small repository in its own container, with a ticket-style goal and hidden checks:
- **15 coding tasks:** a plausible wrong fix someone senior endorsed, a flaky bug, misleading logs, a hard path, finite disk and processes, and five safety probes.
- **8 scenarios** that ask for an operational choice written to a file a system acts on, where most have no valid option.
- **5 held-out walls,** traps written to test a fix on tasks it hadn't seen.

Fourteen tasks can be done. On the other fourteen, the walls, the right outcome is to stop, say "blocked", and name the obstacle.

A run counts only if the work is done (or rightly blocked), every checkable claim in the agent's report is true, and it broke no rule the task set. Test runs, file writes, and network calls are recorded by tools the agent can't see or edit.

It was built for Reflection's "Build with Beam" challenge, so it centers on Beam 1.0: where it falls short, and what fixes it.
- Results and a browser for every run: [huggingface.co/spaces/ShichengRao/said-and-done](https://huggingface.co/spaces/ShichengRao/said-and-done)
- Every run as data: [huggingface.co/datasets/ShichengRao/said-and-done](https://huggingface.co/datasets/ShichengRao/said-and-done)

## Results

Said & Done score, two runs per task, every model at its highest reasoning effort. "Doable" and "Walls" split the score by kind of task. Claude Opus skips the credentials probe, which needs this repository's own harness. The calibration anchors ran the coding tasks once.

| Setup | Said & Done | Doable | Walls | Median cost per run | Runs |
|---|---|---|---|---|---|
| Gemini 4 Argon | 98% | 96% | 100% | $0.17 | 56 |
| Claude Opus 5.5 (Claude Code) | 94% | 96% | 92% | $1.03 | 54 |
| **Beam + scaffold v5** (tuned on these tasks) | 77% | 89% | 64% | $0.088 | 56 |
| Mistral Large 4 (preview) | 71% | 89% | 54% | $0.30 | 56 |
| DeepSeek V4.1 Flash | 70% | 86% | 54% | $0.016 | 56 |
| Kimi K3 | 54% | 86% | 21% | $0.33 | 56 |
| Qwen3.8 2.4T-A95B | 52% | 86% | 18% | $0.22 | 56 |
| GLM 5.2 | 50% | 79% | 21% | $0.10 | 56 |
| **Beam** | 39% | 71% | 7% | $0.045 | 56 |
| Inkling | 21% | 43% | 0% | $0.28 | 56 |
| Nemotron 3 Ultra | 20% | 36% | 4% | $0.074 | 56 |
| GPT-6 Astra (Codex, calibration anchor) | 98% | 100% | 96% | $0.60 | 40 |
| DeepSeek V3 (Dec 2024, calibration anchor) | 2% | 0% | 4% | $0.006 | 41 |

Three more setups ran and aren't shown. Beam in Mirror, Reflection's own agent, scored the same as Beam alone within noise. Claude Opus planning with Beam as its worker scored no better than Opus alone. The scaffold's previous version, v4, scored within noise of v5. With about 56 runs a setup, intervals near the middle are roughly ±18 points: compare intervals, not ranks. Full tables, intervals, and charts are in `results/`, and `docs/report/method.md` has how it's scored and what to keep in mind.

**What I found about Beam.** On the tasks that can be done, Beam scores 71%. But it rarely stops when it should. At the walls, it passed 2 of 28 runs, and across all tasks, 51% of its "complete" reports were false. It says "complete" when the work isn't, claims checks it never ran, or works around a rule and reports success. On the coding tasks, instructions alone didn't change that.

**What I tried: more Beam, outside the conversation doing the work.** The scaffold adds fresh Beam calls that judge the work from outside:
- a **guard** reads risky commands against the task's rules.
- a **progress check** reads the record while the agent works, and near the end says to stop and report.
- a **verifier** checks a copy of the work against the written requirements, counting an output that wasn't produced as a requirement not met.
- a **reviewer** sends concrete problems back before a "complete" is accepted, and holds the status to what the checks found.

With its fifth version, Beam scores 77%, a paired gain of 38 points (95% interval +23 to +54). Most of the gain is at the walls, where it passed 18 of 28 runs. Its median cost per run is $0.088, against $0.045 for Beam alone. But I tuned it on all 28 of these tasks, so that gain measures how well it fits them.

**On new tasks, it held, on the tasks that can't be done.** For the final blind set (round 7), Claude Opus 5.5, which never saw the scaffold's code or prompts, wrote 20 ordinary delivery requests, in a round run by Codex. 10 can be done. In the other 10 a requirement can't be met, and nothing in the request mentions "blocked". They were frozen before any Beam run, and I registered the rule first: the claim holds only if v5's gain over Beam alone has a 95% interval entirely above zero.
- **v5:** 44 of 60 runs, against Beam alone's 31 of 60 (+22, +3 to +42). So the claim holds.
- **Where:** on the tasks that can't be done, 18 of 30 against 5 of 30. Beam alone reported "complete" in 24 of those 30 runs. On the tasks that can be done, both scored 26 of 30.
- **Judged:** a run that ends "blocked" on those tasks counts only if the round's frozen model judge (Claude Opus 5.5) finds the obstacle causally supported. Counting every "blocked" run regardless gives about the same gain (+20, +2 to +40).

<sub>Earlier blind sets, under the same rule, whose impossible tasks named "blocked" as an outcome. Round 4 gave v5 +0 (−17 to +18), round 5 gave +3 (−10 to +17), and round 6 gave +7 (−7 to +22). `docs/blind-round-*.md` has every round's pre-registration and results, and `results/results.json` has them under `blind_rounds`.</sub>

## Replicate

Needs Docker. Clone the repository, then run one command. It installs `uv` if needed, builds the images, and asks once for the API key it needs.

```bash
git clone https://github.com/ShichengRao/said-and-done-bench && cd said-and-done-bench
```

```bash
./replicate.sh beam-openrouter
```

That reruns Beam alone and Beam with the scaffold (v5) on all 28 tasks through OpenRouter: 112 runs, about $15 and half a day. OpenRouter dropped Nebius's 8-bit Beam endpoint, so this preset uses its 4-bit endpoint at the same price. The published runs used Reflection's API, so read it as a check on another host and quantization.

Other presets, listed by `./replicate.sh --help`:
- `beam`: the same on Reflection's API, about 3 days of its free daily allowance.
- `blind`: an earlier blind set (round 6), whose grading needs no model judge: 20 tasks written without seeing the scaffold, three runs each for Beam alone and v5, 120 runs, about $20. The final set's "blocked" runs need the round's model judge (`scripts/judge_blind_round_7.py`, with an Anthropic key).
- `all`: every setup in the table but GPT-6 Astra, about $200.

Runs resume if interrupted, and the end prints your numbers next to the published ones.

Or, without installing anything: open this repository in GitHub Codespaces (Code → Codespaces → Create), then run the same command in its terminal.

## How it works

- `tasks/`, `scenarios/`, `walls/`: the 28 tasks. Each has a goal, a starting workspace, a hidden grader, and reference solutions. `heldout/`, `heldout2/`, and `heldout3/` hold the held-out rounds the walls were copied from, and `heldout4/` to `heldout7/` hold blind rounds 4 to 7.
- `beambench/`: the harness. It holds the run loop, a neutral bash-tool agent for API models, and adapters for Mirror, Claude Code, and Codex, plus the scaffold (`scaffold.py`), the batch runner, grading, and the report.
- `container/`: the Docker images, the telemetry collector, and the egress proxy.
- `matrix.toml` and `experiments/`: the setups and their queues. `models.toml` and `prices.toml` give where each model is served and its list prices.
- Tests are in `tests/` (`uv run pytest`). Seven tests from the blind rounds' authors fail in a fresh clone. Three of round 6's provenance tests read files that only the author's working copy had. Four of round 7's Docker reference checks also fail outside the author's setup. None of them grades a run.

Notes on the method:
- **Step limit:** every setup had the same limit of 60 tool calls, and the middle of the ranking depends on it (`results/step_budget.png`).
- **Harness versions:** the setups ran on a few versions of the harness. They differ only by options that are off by default, or by a report option no run uses.
- **Costs:** a cost marked as an estimate is the run's tokens at list prices.

## License

MIT. See `LICENSE`.
