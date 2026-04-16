# bud-app-frontend

Frontend application for the Bud project — Test automation dashboard.

> **Note:** This repository was split from the original [MbedLabs/bud-web-app](https://github.com/MbedLabs/bud-web-app) monorepo.
> Git history has been preserved for all files that were under `frontend/`.

## Stack

- **React** (TypeScript)
- **Vite**
- **Tailwind CSS**

## Development

```bash
npm install
npm run dev
```

The dev server runs on http://localhost:3000 by default.

## Docker

```bash
docker build -t bud-app-frontend .
docker run -p 3000:80 bud-app-frontend
```

## Related Repos

- Backend: [MbedLabs/bud-app-backend](https://github.com/MbedLabs/bud-app-backend)

## License

This project is licensed under the **GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)**. See the [LICENSE](LICENSE) file for the full text.

Copyright (C) 2024-2026 EmbedLabs.

For commercial licensing options that do not require AGPL compliance, contact dev@embedlabs.de. Contributions are accepted under the [CLA](CLA.md) — see [CONTRIBUTING.md](CONTRIBUTING.md).
