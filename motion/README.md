# Motion library

This workspace renders approved `/direct` beat manifests as transparent
ProRes 4444 overlays for `clip.py --overlay`.

Install the pinned workspace and render all eight verified golden samples:

```bash
npm install
npm run golden
```

Validate an unapproved beat sheet without rendering:

```bash
node scripts/render-beats.mjs beats.json --transcript <workdir>/transcript.json --check
```

After approval, remove `--check`; the CLI renders `out/beats/*.mov`, verifies
their alpha channel, and prints the exact `clip.py` overlay and SFX flags.

Beat timing is finished OUTPUT time. Use the EDL after `--tighten`.
Creator styling belongs only in `src/tokens.ts` or manifest token overrides.
