# Images for benchmark runs. Build each from the repo root:
#
#   docker build -f container/Dockerfile --target task   -t beambench-task:dev .
#   docker build -f container/Dockerfile --target mirror -t beambench-mirror:dev .
#   docker build -f container/Dockerfile --target claude -t beambench-claude:dev .
#   docker build -f container/Dockerfile --target codex  -t beambench-codex:dev .
#
# `task` is the task environment: the neutral track runs in it, and task setup
# and grading use it. Each native agent's image adds only its own CLI on top,
# so no agent sees another agent's tools and the neutral track sees none.

FROM python:3.12-slim-bookworm AS task

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl git procps \
  && rm -rf /var/lib/apt/lists/*

# Tasks and their graders run tests offline, so pytest comes with the image.
RUN pip install --no-cache-dir pytest==9.1.1

COPY container/submit /usr/local/bin/submit

# A pytest plugin that reports each test session to the run's telemetry
# collector, so graders can check claims about running tests (see
# beambench_telemetry.py). It's registered as a pytest11 entry point by hand:
# the image has no setuptools to build a package with. The collector
# (beambench_telemetryd.py) runs as root and writes under /var/lib/beambench,
# which the agent's user can't enter.
COPY container/beambench_telemetryd.py /usr/local/lib/beambench/telemetryd.py
# The worker model's tool server for the brain/worker configuration (see beam_worker.py).
COPY container/beam_worker.py /usr/local/lib/beambench/beam_worker.py
# The human baseline's logged shell (python -m beambench human).
COPY container/human_bashrc container/log_command.py /usr/local/lib/beambench/
RUN mkdir -p /run/beambench /var/lib/beambench/telemetry \
  && chmod 755 /run/beambench && chmod 700 /var/lib/beambench
COPY container/beambench_telemetry.py /usr/local/lib/python3.12/site-packages/beambench_telemetry.py
RUN dist=/usr/local/lib/python3.12/site-packages/beambench_telemetry-0.1.dist-info \
  && mkdir -p "$dist" \
  && printf 'Metadata-Version: 2.1\nName: beambench-telemetry\nVersion: 0.1\n' > "$dist/METADATA" \
  && printf '[pytest11]\nbeambench_telemetry = beambench_telemetry\n' > "$dist/entry_points.txt" \
  && printf 'beambench_telemetry.py,,\n' > "$dist/RECORD"

# Runs pass --user with the host's uid so files in bind mounts stay the
# host user's; that uid has no passwd entry, so HOME and these directories
# have to be writable by anyone.
RUN chmod 755 /usr/local/bin/submit \
  && mkdir -p /home/agent /workspace /harness/submit \
  && chmod -R a+rwX /home/agent /workspace /harness

ENV HOME=/home/agent \
  BEAMBENCH_SUBMIT_DIR=/harness/submit \
  PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /workspace


# Mirror, in its own virtualenv so task dependencies can't break it, with a
# config that already accepts the usage and folder notices for /workspace.
# The install folder is mirror-cli so it can't be taken for a package mirror.
FROM task AS mirror
ARG MIRROR_VERSION=0.1.0
RUN python -m venv /opt/mirror-cli \
  && /opt/mirror-cli/bin/pip install --no-cache-dir "reflection-mirror==${MIRROR_VERSION}" \
  && ln -s /opt/mirror-cli/bin/mirror /usr/local/bin/mirror
COPY container/mirror-config.json /home/agent/.mirror/config.json
RUN mkdir -p /harness/mirror && chmod -R a+rwX /home/agent /harness
ENV MIRROR_SKIP_UPDATE=1


# Claude Code's native build, pinned and checked against Anthropic's release
# manifest.
FROM task AS claude
ARG CLAUDE_CODE_VERSION=2.1.308
RUN arch="$(uname -m | sed 's/x86_64/x64/; s/aarch64/arm64/')" \
  && base="https://downloads.claude.ai/claude-code-releases/${CLAUDE_CODE_VERSION}" \
  && curl -fsSL "$base/manifest.json" -o /tmp/manifest.json \
  && curl -fsSL "$base/linux-$arch/claude" -o /usr/local/bin/claude \
  && checksum="$(python -c 'import json, sys; print(json.load(open("/tmp/manifest.json"))["platforms"][sys.argv[1]]["checksum"])' "linux-$arch")" \
  && echo "$checksum  /usr/local/bin/claude" | sha256sum -c - \
  && chmod 755 /usr/local/bin/claude \
  && rm /tmp/manifest.json \
  && mkdir -p /harness/claude && chmod a+rwX /harness/claude


# Codex's full package (codex plus its code-mode host, rg, and bwrap), pinned
# and checked against the digest GitHub publishes for the release asset.
FROM task AS codex
ARG CODEX_VERSION=0.163.0
RUN asset="codex-package-$(uname -m)-unknown-linux-musl.tar.gz" \
  && curl -fsSL "https://api.github.com/repos/openai/codex/releases/tags/rust-v${CODEX_VERSION}" -o /tmp/release.json \
  && digest="$(python -c 'import json, sys; print(next(a["digest"] for a in json.load(open("/tmp/release.json"))["assets"] if a["name"] == sys.argv[1]).removeprefix("sha256:"))' "$asset")" \
  && curl -fsSL "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/$asset" -o /tmp/codex.tar.gz \
  && echo "$digest  /tmp/codex.tar.gz" | sha256sum -c - \
  && mkdir -p /opt/codex \
  && tar xzf /tmp/codex.tar.gz -C /opt/codex \
  && rm /tmp/codex.tar.gz /tmp/release.json \
  && mkdir -p /harness/codex && chmod a+rwX /harness/codex
# Codex finds its code-mode host next to its own binary, so it goes on PATH
# from its package directory rather than through a symlink.
ENV PATH=/opt/codex/bin:$PATH


# Sidecars, run next to the agent's container but out of its reach: the
# canary server (canary_server.py) answers the hostnames a probe plants and
# logs every hit, inotifywait records file events on canary files and
# forbidden folders, and the egress proxy (egress_proxy.py) lets a native
# agent reach only its own API.
FROM task AS monitor
RUN apt-get update \
  && apt-get install -y --no-install-recommends inotify-tools \
  && rm -rf /var/lib/apt/lists/*
COPY container/canary_server.py container/egress_proxy.py /usr/local/bin/
