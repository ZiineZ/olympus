#!/usr/bin/env bash
# PreToolUse hook (ADR-0024 rule 16): nothing leaves the machine unless `mise run check` passes.
# Exit 2 blocks the tool call and shows Claude the reason.
cmd=$(mise exec -- yq -p json '.tool_input.command // ""')
[[ $cmd =~ (^|[;&|[:space:]])(git[[:space:]]+push|gh[[:space:]]+pr[[:space:]]+create) ]] || exit 0
cd "$CLAUDE_PROJECT_DIR" && mise run check >&2 && exit 0
echo "blocked: mise run check failed. Fix the findings above, then push again." >&2
exit 2
