# Prepare for Open Sourcing

## Current development-phase decision
Bud is currently using a development-first deployment model similar in spirit to the internal Fleet Monitoring setup.

That means the short-term priority is:
- push changes quickly
- build and deploy quickly
- reduce ambiguity about what version is actually live

This is intentionally optimized for development speed, not for final public open-source release hygiene.

## What we are doing now
- Keep deployment behavior optimized for fast internal iteration.
- Use version bumps aggressively for visibility during development.
- Treat the version shown in the UI and build outputs as a practical signal of what is live.
- Prefer automatic update/deploy behavior over manual release ceremony while development is moving fast.

## Why this is temporary
For a public open-source project, we should later reduce environment-specific and deployment-specific assumptions.
The public repo should stay generic and reusable.

## What should change later
Before open sourcing broadly, we should revisit these points:
1. Remove or isolate deployment logic that is specific to Contabo or the private EmbedLabs infra.
2. Move toward a cleaner release model where versioning and releases are intentional and documented.
3. Replace development-phase convenience behaviors with a more standard release/promotion path.
4. Review branding, internal URLs, secrets assumptions, and any operational shortcuts.
5. Revisit version numbering and normalize it for public release.

## Development-phase visibility rule
During this phase, version visibility matters more than elegant release ceremony.
If a new image is running, it should be obvious from the app version visible to Amine.

## Migration target later
Longer term, the likely target is:
- generic CI in app repos
- cleaner release/version policy
- infra-specific deployment logic kept outside the app repos where possible
