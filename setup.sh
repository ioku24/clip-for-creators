#!/usr/bin/env bash
# Installs the three tools `clip` needs. Safe to re-run — it skips whatever
# you already have. Nothing here phones home; transcription is local.
set -euo pipefail

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()  { printf '  \033[32m✓\033[0m %s\n' "$*"; }
no()  { printf '  \033[33m→\033[0m %s\n' "$*"; }

say "Checking what you already have"

MISSING=()
for t in ffmpeg yt-dlp; do
  if command -v "$t" >/dev/null 2>&1; then ok "$t"; else no "$t — will install"; MISSING+=("$t"); fi
done

if command -v whisper >/dev/null 2>&1; then
  ok "whisper"
  NEED_WHISPER=0
else
  no "whisper — will install"
  NEED_WHISPER=1
fi

if [ ${#MISSING[@]} -gt 0 ]; then
  if ! command -v brew >/dev/null 2>&1; then
    say "Homebrew is required to install ${MISSING[*]}"
    echo "  Install it first (one line, from https://brew.sh):"
    echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo "  Then re-run this script."
    exit 1
  fi
  say "Installing ${MISSING[*]}"
  brew install "${MISSING[@]}"
fi

if [ "$NEED_WHISPER" -eq 1 ]; then
  say "Installing whisper (speech-to-text, runs on your machine)"
  command -v python3 >/dev/null 2>&1 || { echo "  python3 not found — install it, then re-run."; exit 1; }
  # --user keeps this out of the system python; pipx would be tidier but is one
  # more thing to install, and this is a gift, not a platform.
  python3 -m pip install --user --quiet --upgrade openai-whisper
fi

say "Verifying"
FAIL=0
for t in ffmpeg yt-dlp whisper; do
  if command -v "$t" >/dev/null 2>&1; then ok "$t  $(command -v "$t")"; else
    printf '  \033[31m✗\033[0m %s NOT on PATH\n' "$t"; FAIL=1
  fi
done

if [ "$FAIL" -eq 1 ]; then
  say "Something didn't land"
  echo "  If whisper is missing, its install dir may not be on your PATH. Try:"
  echo "    export PATH=\"\$(python3 -m site --user-base)/bin:\$PATH\""
  echo "  Add that line to ~/.zshrc to make it stick."
  exit 1
fi

say "Done — you're ready"
cat <<'EOF'
  Add the skill to your AI:

    npx skills add <your-github-user>/clip-for-creators

  Then just talk to it:

    "Pull three shorts out of this video: <youtube link>"

  It will read your transcript, propose the moments with reasons, and wait for
  your yes before cutting anything.
EOF
