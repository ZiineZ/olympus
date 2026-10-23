# syntax=docker/dockerfile:1.10
# Athena: Claude Code plus the repo's own toolchain (ADR-0024). Built from the repo root by .github/workflows/athena-image.yaml.
FROM docker.io/library/debian:trixie-slim@sha256:62bd423aeee912639ca8ee681c2b762cb3e25137e0a92b20be455898a9f034ad

# Renovate bumps these versions; the PR must also update the matching --checksum below (runbook 05)
# renovate: datasource=npm depName=@anthropic-ai/claude-code
ARG CLAUDE_CODE_VERSION=2.1.303
# renovate: datasource=github-releases depName=jdx/mise extractVersion=^v(?<version>.+)$
ARG MISE_VERSION=2026.10.15

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git less openssl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 1000 --create-home --home-dir /home/athena athena

# Pinned by version and checksum; DISABLE_AUTOUPDATER below keeps it that way
ADD --chmod=755 --checksum=sha256:375988f457756524234695cf2d8f64ace99c5f68682e47ea24862a843c191450 \
    https://downloads.claude.ai/claude-code-releases/${CLAUDE_CODE_VERSION}/linux-x64/claude /usr/local/bin/claude
ADD --chmod=755 --checksum=sha256:e3b186d4c70627f27037be615becaf4acfb30e41fb6a1819486717dc94e4e2a9 \
    https://github.com/jdx/mise/releases/download/v${MISE_VERSION}/mise-v${MISE_VERSION}-linux-x64 /usr/local/bin/mise

# The same tools, versions and checksums as Stan's machines and CI (.config/mise.lock). They live outside
# /home/athena, which is the PVC, and are linked onto PATH so they work in any directory.
ENV MISE_DATA_DIR=/opt/mise MISE_YES=1
COPY .config/mise.toml .config/mise.lock /opt/olympus/.config/
RUN --mount=type=secret,id=github_token,env=GITHUB_TOKEN \
    cd /opt/olympus && mise trust && mise install \
 && mkdir -p /opt/tools/bin && for d in $(mise bin-paths); do ln -sf "$d"/* /opt/tools/bin/; done \
 && rm -rf /root/.cache /root/.local

COPY 04-platform/06-agent/athena/image/gitconfig /etc/gitconfig
COPY --chmod=755 04-platform/06-agent/athena/image/bin/ /usr/local/bin/

ENV PATH=/usr/local/bin:/opt/tools/bin:/usr/bin:/bin \
    HOME=/home/athena \
    MISE_TRUSTED_CONFIG_PATHS=/home/athena/olympus \
    DISABLE_AUTOUPDATER=1 \
    DISABLE_TELEMETRY=1 \
    DISABLE_ERROR_REPORTING=1
# Not CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: it turns Remote Control off (ADR-0036)
USER 1000
WORKDIR /home/athena
CMD ["athena-init"]
