Bud is test management for teams that build hardware.

It keeps the things a bench actually produces in one place: test plans and the
cases inside them, the runs executed against a given firmware or board revision,
the pass/fail record, and the artifacts each run leaves behind — logs, traces,
captures.

Runs can be recorded by hand, or reported automatically by a runner installed on
the bench machine, which registers against this instance with a shared key and
streams results back as they happen.

Results can be synchronised into Bloom, EmbedLabs' requirements tool, so that a
requirement carries the evidence that verifies it rather than a link to it.
