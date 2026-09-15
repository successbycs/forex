# GDELT publisher egress

This package runs the GDELT publisher fetcher behind a dedicated Docker caller
network. It has no host port, Docker socket, trading authority, or generic URL
route. `forex-gdelt-private` contains n8n, PostgreSQL, and the fetcher;
`forex-gdelt-outbound` is attached only to the fetcher so publisher HTTPS still
works without granting n8n direct publisher access. PostgreSQL also stays on
its original shared network for the rest of the stack. The existing `n8n`
service receives two values from the ignored,
owner-only `/home/chris/.config/forex/gdelt-n8n.env`: an egress bearer and an
independent HMAC signing key. The bearer authenticates the caller; the HMAC
prevents a bearer holder from inventing an arbitrary fetch URL.

On T480 run `python3 scripts/provision_gdelt_egress_secrets.py` once. It makes
the ignored owner-only files with fresh distinct secrets and prints no secret
material. If values must be supplied manually, create the file from
`gdelt-n8n.env.example`, make it mode `0600`, and create two matching
mode-`0600` secret files at
`/home/chris/.config/forex/gdelt-egress-bearer` and
`/home/chris/.config/forex/gdelt-candidate-signing-key`. Apply `compose.yaml`
and `compose.n8n.override.yaml` beside the shared infrastructure Compose
project. The installer checks the n8n container sees both values and can reach
the private health endpoint before it activates either workflow. None of these
machine-local files are tracked by this repository.

The workflow retrieves the four fixed GDELT archives through the same boundary;
that route accepts only the canonical `data.gdeltproject.org/gdeltv2/` GKG ZIP
pattern. It is not a general download proxy. Before the Compose fragment is applied, `scripts/n8n_m11_install.py` builds the
egress image from the fixed Forex repository root, labels it with the SHA-256
of its exact three-file build input, and verifies that label using Docker image
inspection. The Dockerfile copies precisely those manifest files, so unrelated
repository content cannot change the reviewed image identity. This avoids an
accidental build context from the shared repository. Its Python base is pinned
to the reviewed `python:3.12-slim` OCI index digest
`sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea`;
an image rebuild therefore cannot silently move to a later `3.12-slim` base.

`forex-gdelt-publisher-egress.service` remains a host-only diagnostic template;
when using it, set both `FOREX_GDELT_EGRESS_BEARER_FILE` and
`FOREX_GDELT_CANDIDATE_SIGNING_KEY_FILE` to mode-`0600` files. It is not
installed or started by this repository.
