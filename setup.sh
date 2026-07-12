#!/usr/bin/env bash
# Installs the three tools `clip` needs. Safe to re-run — it skips whatever
# you already have. Nothing here phones home; transcription is local.
set -euo pipefail

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()  { printf '  \033[32m✓\033[0m %s\n' "$*"; }
no()  { printf '  \033[33m→\033[0m %s\n' "$*"; }

say "Checking what you already have"

MISSING=()
# openai-whisper goes through Homebrew too. `pip install --user openai-whisper`
# looks tidier but dies on PEP 668 ("externally-managed-environment") on any
# modern Homebrew python — which is exactly the machine most people are on.
for t in ffmpeg yt-dlp openai-whisper; do
  bin="$t"; [ "$t" = "openai-whisper" ] && bin="whisper"
  if command -v "$bin" >/dev/null 2>&1; then ok "$bin"; else no "$bin — will install"; MISSING+=("$t"); fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  if ! command -v brew >/dev/null 2>&1; then
    say "Homebrew is required to install: ${MISSING[*]}"
    echo "  Install it first (one line, from https://brew.sh):"
    echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo "  Then re-run this script."
    exit 1
  fi
  say "Installing: ${MISSING[*]}"
  brew install "${MISSING[@]}"
fi

say "Verifying"
FAIL=0
for t in ffmpeg yt-dlp whisper; do
  if command -v "$t" >/dev/null 2>&1; then ok "$t  $(command -v "$t")"; else
    printf '  \033[31m✗\033[0m %s NOT on PATH\n' "$t"; FAIL=1
  fi
done

if [ "$FAIL" -eq 1 ]; then
  say "Something did not land — see the errors above, then re-run."
  exit 1
fi

say "Done — you're ready"
cat <<'EOF'
  Add the skill to your AI:

    npx skills add ioku24/clip-for-creators

  Then just talk to it:

    "Pull three shorts out of this video: <youtube link>"

  It will read your transcript, propose the moments with reasons, and wait for
  your yes before cutting anything.
EOF
