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

- Backend: [MufeIO/bud-app-backend](https://github.com/MufeIO/bud-app-backend)

## License

MIT License — Copyright (c) 2025 EmbedLabs
