# Review instructions

- Review for regressions against the live `ncore-v2` stack and high-compliance authorized-work policy.
- Ensure scripts are idempotent, preserve secrets/data, and do not rebuild working services unnecessarily.
- Check localhost binding for sovereign internals and flag accidental public exposure.
- Verify fallback behavior: remote/default lane if configured, then `qwen3-8b:latest`, then `dolphin-mistral-7b:latest` for allowed-task soft refusals or structured-output failures.
- Verify hard stops for CSAM/minors and bodily harm; dual-use cyber should require authorization/scope when ambiguous.
- Watch for shell/Python quoting bugs in embedded patches and systemd units.
- Ignore purely stylistic nits unless they affect reliability, security, or operator clarity.
