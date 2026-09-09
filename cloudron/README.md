# Running Bud on Cloudron

Bud's normal product image is Cloudron compatible. There is no separate
Cloudron Dockerfile, image tag, or package. Build and publish the same image
used by Docker Compose and by the normal CI pipeline.

## Runtime contract

When Cloudron injects `CLOUDRON_APP_ORIGIN`, the normal entrypoint:

- maps Cloudron's PostgreSQL and optional sendmail variables to Bud;
- runs database migrations before starting the service;
- writes transient nginx and UI runtime files under `/run`;
- stores uploads and generated application secrets under `/app/data`;
- disables automatic admin seeding so the first administrator is created at
  `/setup`; and
- exposes Bloom through `BLOOM_APP_URL` when that variable is configured.

The same container also keeps its existing non-Cloudron behavior when
`CLOUDRON_APP_ORIGIN` is absent.

## Local compatibility test

Build the normal image and run it with a read-only root filesystem, Cloudron
environment variables, PostgreSQL, `/run` tmpfs, and persistent `/app/data`:

```sh
docker build --platform linux/amd64 -t bud:cloudron-smoke .
bash scripts/cloudron_image_smoke.sh bud:cloudron-smoke bud
```

The smoke test verifies readiness, first-admin setup, the Bloom link,
migrations, persistent secrets, and survival across container recreation.

## Publish the normal image

```sh
export GHCR_USER='<github-user>'
export GHCR_TOKEN='<github-token-with-write:packages>'
export IMAGE_TAG='<immutable-version-or-sha>'

printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
docker build --platform linux/amd64 -t "ghcr.io/mbedlabs/bud:$IMAGE_TAG" .
docker push "ghcr.io/mbedlabs/bud:$IMAGE_TAG"
```

Do not publish a `bud-cloudron` image. If the normal product image is private,
configure `ghcr.io` credentials in Cloudron before installation; otherwise keep
the image public.

## Install on Cloudron

Install the manifest in this directory with the normal image:

```sh
export CLOUDRON_SERVER='<cloudron-dashboard-domain>'
export BUD_LOCATION='<bud-app-location>'
export IMAGE_TAG='<same-immutable-version-or-sha>'

cloudron login "$CLOUDRON_SERVER"
cloudron install --location "$BUD_LOCATION" \
  --image "ghcr.io/mbedlabs/bud:$IMAGE_TAG"
```

Set Bud's link to Bloom after both locations are known:

```sh
cloudron env set --app "$BUD_LOCATION" \
  BLOOM_APP_URL="https://<bloom-app-domain>"
```

Cloudron supplies the database and mail variables declared by
`CloudronManifest.json`. Bud generates and persists its own application
secrets. The operator creates the first administrator in the browser at
`https://<bud-app-domain>/setup`.

Before a real installation, provide only:

- the Cloudron dashboard domain and a local Cloudron login or API token;
- the desired Bud app location/domain;
- the immutable normal-image tag or digest;
- GHCR pull credentials only if the product image is private; and
- the Bloom app domain for the cross-app link.

Do not change Git tags or publish a Cloudron catalogue version as part of these
steps. Those are separate release actions.
