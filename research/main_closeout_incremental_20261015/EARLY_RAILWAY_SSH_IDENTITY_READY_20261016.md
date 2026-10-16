# BTC15 EARLY — isolated Railway transfer SSH identity (2026-10-16)

**Status: PRIVATE KEY CREATED / PUBLIC KEY READY. SSH authentication NOT YET ENABLED. No authentic live capture or transfer has been started.**

Existing isolated Railway capacity project `btc15-early-capacity-test`
- Project ID: `87ad03d5-e1d6-47d6-b1ea-159cd7594686`
- Service ID: `1fff593b-8b09-4cc4-8c51-f9603082657f`
- Dedicated volume ID: `2dba2ef6-b84d-4abf-9d04-58a1e77082c5`
- Path: `/research-evidence/ssh-identity/btc15_early_isolated_transfer_ed25519`
- Script: `research/main_closeout_incremental_20261015/prepare_isolated_railway_ssh_identity.py`
- Git commit: `610c5ff080a23a1eab3fb4e1e35f309769a024bf`
- One-time deployment: `7c4dfc94-9848-4cb4-ac3b-6de48fdcf974`, SUCCESS
- Private key has mode `0600`, located **only on the isolated Railway volume**. Neither GitHub nor Railway logs expose private key bytes.

Public key (safe to register/share):
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFeCjkWvOfudDYFrp7rsgBVU8LUyZ6uKIgqEnr7serl+ btc15-early-evidence-railway-20261016
```

Public-key SHA-256 (as text bytes): `b605d1d33345e2114bf622eb108c56e9416c3c08e63fb36229bdf43b9e454438`

Key fingerprint: `SHA256:GP5+ctgq2NaFe5WIgzYTm10RAFAXtsx3zu5CwYTWdBM`

Observed readiness report:
- `isolated_project_verified = true`
- `private_key_stored_on_isolated_volume = true`
- `private_key_contents_printed = false`
- `registered_with_railway = false`
- `ssh_host_trusted = false`
- `authentic_source_transfer_attempted = false`
- `recording_campaign_started = false`
- `production_change = false`

**User action/consent required:** Register public key in Railway Account Settings > SSH Keys. Understand Railway account SSH keys are not a read-only permission; they may grant interactive shell access to account services. Registration is optional and should be explicitly approved by the account owner. Revoke this key after the evidence transfer/campaign has completed.

**After registration (no automatic activation):** Independently verify `ssh.railway.com` host key, source service SSH instance identities (MAIN has an official service domain; V81 may require its instance ID), then run a bounded read-only non-mutating command and check source campaign identity. Only then configure the original finisher and separately consider activating native MAIN/V81 recording. Never run `finish.py` as an SSH connectivity test: its finish RPC asks the recorder to stop and seal.

This file is documentation of the already-created isolated key, **not** authorization to restart production, modify secrets/variables, widen permissions further, or place orders.
