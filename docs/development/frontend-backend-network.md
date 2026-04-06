# Frontend ↔ Backend networking

## Symptom: `Failed to fetch` in the browser

The browser could not complete the HTTP request. Common causes:

1. **Proxy target wrong** — the app uses `src/app/api/v1/[[...path]]/route.ts` to forward `/api/v1/*` to `BACKEND_INTERNAL_URL`. That host must be reachable **from the Next.js server process** (not from your browser).
   - **Docker Compose `frontend` service:** `BACKEND_INTERNAL_URL=http://backend:8000` (default in `docker-compose.yml`).
   - **Local `npm run dev` on the host:** set `BACKEND_INTERNAL_URL=http://127.0.0.1:8000` or rely on the route default (`127.0.0.1:8000`).

2. **Backend not running** or port not published (`8000:8000` in Compose).

3. **Prefer same-origin API** — leave `NEXT_PUBLIC_API_URL` empty so the client uses `/api/v1` and avoids CORS. Direct calls to `http://localhost:8000/api/v1` require backend CORS to allow your frontend origin (e.g. `http://localhost:3500`).

After changing `BACKEND_INTERNAL_URL`, restart the Next.js dev server. If you still get errors, the proxy may return **502** with JSON explaining that the upstream host is unreachable.
