# Admin

Minimal operations console for the v0.1 marketplace:

- Dashboard
- Player review / approve / reject
- Order management
- Settlement view

## Run

Start the FastAPI backend first, then:

```bash
cd apps/admin
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000`. Demo mode discovers the seeded PLATFORM identity automatically.
