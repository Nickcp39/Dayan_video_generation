# Frozen Han Li Recipe

Start with [the handoff document](../../docs/HANLI_PIPELINE_HANDOFF.md).

- `lock.json`: SHA256/size inventory and expected runtime identity. Never rebuild
  this file to bypass a failed check. The documented digest is recorded in the
  check-results document outside this directory.
- `render_baseline.json`: the full successful 10fps graph, not the failed 16fps run.
- `project.example.json`: schema and approved defaults. Source paths and shot
  annotations belong to the original project; adapt them in a NEW project.
- `validation/tests.json`: completed offline tests, including source hashes.
- `execution.lock`: transient single-run lock, created only during `run`.

The baseline files are not an installer. Large model/engine paths remain on this
machine. A different machine or recipe needs explicit migration and validation.
The historical release under `releases/hanli-pipeline-v1-20260913` stays unchanged.
