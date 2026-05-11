# bud-app-frontend

Frontend application for the Bud platform — a comprehensive test automation and runner orchestration dashboard.

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

## Deployment

This frontend is designed to be environment-agnostic using runtime configuration injection.

### Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `BACKEND_UPSTREAM` | Nginx upstream for the API proxy (`/api`) | `bud-backend.bud.svc.cluster.local:8000` |
| `BLOOM_APP_URL` | URL of the Bloom PLM application (for sidebar links) | `http://localhost:3001` |
| `BUD_APP_URL` | Public URL of this Bud instance (for self-referencing) | `http://localhost:3000` |

### Docker

```bash
docker build -t bud-app-frontend .

# Run with custom upstream and cross-links
docker run -p 8080:80 \
  -e BACKEND_UPSTREAM=backend:8000 \
  -e BLOOM_APP_URL=https://bloom.example.com \
  bud-app-frontend
```

## Related Repos

- Backend: [MbedLabs/bud-app-backend](https://github.com/MbedLabs/bud-app-backend)

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See the [LICENSE](LICENSE) file for the full text.

Copyright (C) 2026 EmbedLabs.

For commercial licensing options that do not require AGPL compliance, contact dev@embedlabs.net. Contributions are accepted under the [CLA](CLA.md) — see [CONTRIBUTING.md](CONTRIBUTING.md).
