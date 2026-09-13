# Workspace handoff

Mode selection: read `docs/VIDEO_MODES.md`. Direct animation from character/storyboard
images is a separate accepted workflow; read `docs/DIRECT_ANIMATION_HANDOFF.md`
and use `scripts/direct_animation.py`. Preserve the accepted project 007 and its
release. Do not apply the character-replacement SAM2/DWPose steps to direct I2V.
Do not overwrite its recipe lock to bypass checker failures. New work gets a new
project/attempt; reviews must bind to current artifacts and reflect actual review.

These rules apply to Han Li character/voice short-video reuse only. Other projects
in this workspace have independent workflows.

- Read `docs/HANLI_PIPELINE_HANDOFF.md` before Han Li generation or continuation.
- Use `scripts/hanli_guard.py` as the entry point. Keep the approved worker,
  weights, references and frozen historical release unchanged.
- Do not change models, seed, frame rate, inference parameters or the lock to
  make a failed check pass. A new recipe needs explicit user approval.
- New input videos use new project/attempt directories. Never overwrite the
  accepted project `projects/006-hanli-reuse-10s/retry_10fps`.
- Stop on FAIL/BLOCKED. Resume known ComfyUI prompt IDs; never blindly resubmit
  an ambiguous request. Never interrupt another user's job.
- Human review is required for voice, masks and final delivery. Do not invent
  user approval or claim ASR proves perfect pronunciation.
- The accepted baseline has a user-reported, unidentified omitted character.
  Preserve that limitation; it has not been fixed.
- Do not start unrelated downloads, automations or training during this work.
