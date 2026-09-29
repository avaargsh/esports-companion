# Admin Console

v0.1 contains a lightweight Vue 3 + Vite operations console.

Scope is intentionally limited to:

- Dashboard
- Player Review
- Order Management
- Settlement

## Run

Start the API first, then:

```bash
cd apps/admin
npm install
npm run dev
```

Open http://localhost:5173.

The console uses the demo admin identity from `/api/v1/dev/demo-identities`. Override the API server with:

```bash
VITE_API_ORIGIN=http://YOUR_HOST:8000 npm run dev
```

Production authentication/RBAC is deliberately outside v0.1.
