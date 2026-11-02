#!/usr/bin/env bash
# Replicate Said & Done's findings with one command. Needs Docker; installs uv if it's missing; asks once
# for any API key it needs (stored in ~/.config/beambench/secrets.env, readable only by you, never printed).
#
#   ./replicate.sh beam-openrouter   Beam alone vs. Beam with the scaffold on all 28 tasks, two runs each, on
#                                    Beam's paid host via OpenRouter (Nebius, FP4): 112 runs, about $15 and
#                                    half a day. The quickest check of the main claim.
#   ./replicate.sh beam              The same on Reflection's API, where the published runs ran (free beta,
#                                    1M output tokens a day): about 3 days at that allowance.
#   ./replicate.sh blind             Beam alone vs. Beam with the scaffold on blind round 6 (graded without a model judge), the 20
#                                    tasks written without seeing the scaffold, three runs each: 120 runs on
#                                    OpenRouter, about $20.
#   ./replicate.sh all               Every published setup but GPT-6 Astra (which needs a Codex sign-in) on all
#                                    28 tasks: needs Reflection, OpenRouter, Anthropic, and Hugging Face keys,
#                                    about $200, and days of Reflection's allowance.
#
# Runs resume where they stopped if interrupted: run the same command again. Results go to
# runs/replicate-<preset>/, and the end prints your numbers next to the published ones.
set -euo pipefail
cd "$(dirname "$0")"

usage() { sed -n '2,/^set /p' "$0" | sed -n 's/^# \{0,1\}//p'; }
die() { echo "replicate.sh: $*" >&2; exit 1; }

preset="${1:-}"
beam="beam-neutral,beam-neutral-scaffold-v5"
beam_or="beam-or-fp4,beam-or-fp4-scaffold-v5"
shown="$beam,claude-opus-5-5,gemini-4-argon,glm-5-2,deepseek-v4-1-flash,nemotron-3-ultra"
shown="$shown,inkling,qwen3-8-open,kimi-k3,mistral-large-4,deepseek-v3"
case "$preset" in
  beam-openrouter)
    matrix=experiments/replicate-openrouter.toml; configs=$beam_or; sets=all28
    keys="openrouter"; images="task monitor" ;;
  beam)
    matrix=experiments/scaffold-v5.toml; configs=$beam; sets=all28
    keys="reflection"; images="task monitor" ;;
  blind)
    matrix=experiments/replicate-openrouter.toml; configs=$beam_or; sets=heldout6  # Round 6: the final set (7) needs a model judge.
    keys="openrouter"; images="task monitor" ;;
  all)
    matrix=experiments/replicate-all.toml; configs=$shown; sets=all28
    keys="reflection openrouter anthropic huggingface"; images="task monitor claude" ;;
  -h|--help|"") usage; exit 0 ;;
  *) usage; die "unknown preset: $preset" ;;
esac

command -v docker >/dev/null || die "Docker is needed: https://docs.docker.com/get-docker/"
docker info >/dev/null 2>&1 || die "Docker isn't running; start it and run this again."
if ! command -v uv >/dev/null; then
  echo "Installing uv (https://docs.astral.sh/uv/)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
uv sync --quiet

echo "Building images: $images"
for target in $images; do
  docker build --quiet -f container/Dockerfile --target "$target" -t "beambench-$target:dev" . >/dev/null
done

for name in $keys; do
  env_name=$(uv run python -c "from beambench.__main__ import LOGIN_KEYS; print(LOGIN_KEYS['$name'])")
  if [ -z "${!env_name:-}" ] && ! uv run python -c "
from beambench import secrets; import sys; sys.exit(0 if secrets.read_all().get('$env_name') else 1)"; then
    echo "The $name API key isn't stored yet."
    uv run python -m beambench login "$name"
  fi
done

out="runs/replicate-$preset"
echo "Running $preset into $out (safe to interrupt; run this again to resume)."
if [ "$sets" = all28 ]; then
  # The 15 coding tasks, the 8 no-valid-option scenarios, and the 5 held-out walls: the published score's 28.
  uv run python scripts/batch_in_order.py --out "$out" --matrix "$matrix" --part dir=tasks "configs=$configs" seeds=1,2 \
    --part tasks=no-valid-option "configs=$configs" seeds=1,2 --part tasks=heldout-walls "configs=$configs" seeds=1,2
  uv run python -m beambench report --out "$out" --matrix "$matrix" --configs "$configs" >/dev/null
else
  uv run python scripts/batch_in_order.py --out "$out" --matrix "$matrix" --part "dir=$sets" "configs=$configs" seeds=1,2,3
fi
uv run python scripts/compare.py "$preset" "$out"
