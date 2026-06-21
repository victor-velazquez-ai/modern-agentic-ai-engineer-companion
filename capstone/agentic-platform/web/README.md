# `web/` — Next.js frontend (Ch 37–38)

The platform's user surface: a **streaming chat workspace** in front of the
FastAPI backend, with the run timeline, tool-call + citation rendering, and
approval cards hanging off it as the app grows. App Router + TypeScript +
Tailwind.

> Built in **Ch 37** (frontend mental model) and **Ch 38** (§38 Build — the
> streaming chat UI with live SSE from the backend). Standalone scaffold:
> [`templates/web-starter/`](../../../templates/web-starter/).

```bash
cd web
corepack pnpm install        # or npm install
pnpm dev                     # http://localhost:3000  (mock by default)
```

With `COMPANION_MOCK=1` (the default in `.env.local.example`) the chat streams a
canned reply, so the UI runs with **zero configuration** — no backend, no keys.

## Structure (Appendix C)

```text
web/
├── app/                     # App Router
│   ├── layout.tsx           #   app shell
│   ├── page.tsx             #   the chat workspace page
│   ├── globals.css          #   Tailwind entry
│   ├── components/
│   │   ├── Chat.tsx         #   streaming chat surface (useChat)
│   │   └── Message.tsx      #   one message bubble
│   └── api/chat/route.ts    #   server route: proxies the backend run SSE stream
└── lib/                     # API client · auth · SSE handling
    ├── config.ts            #   typed env access (server-only)
    ├── auth.ts              #   session + bearer-token resolution (stub)
    ├── api.ts               #   typed calls to the platform API (streamRun, ...)
    └── sse.ts               #   parse the backend's RunEvent SSE stream
```

The split mirrors the appendix: **`app/`** holds the App Router pages and the
streaming UI; **`lib/`** holds the API client, auth, and SSE handling. The route
handler is transport glue only — no agent logic lives in the frontend.

## Wiring to the backend

The chat route proxies the platform API's run stream:

```
GET  {AGENT_API_URL}/v1/runs/{id}/stream?input=...   → SSE RunEvent frames
```

`lib/sse.parseSSE` turns those frames into typed `RunEvent`s; the route
translates `token` events into the AI SDK data-stream format so `useChat()`
renders them live. To go live, in `.env.local`:

```bash
COMPANION_MOCK=          # unset to leave mock mode
AGENT_API_URL=http://localhost:8000
AGENT_API_TOKEN=...      # if the backend requires auth
```

## Notes

- This is a **stub structure**, not a finished app — it gives you the App Router
  layout, the streaming seam, and the lib/ boundary to build on (Ch 38 fills in
  the run timeline, tool-call chips, citations, and approval cards).
- `auth.ts` is a stub: replace `getSession` with your real JWT/cookie
  verification (the backend enforces authn/z, rate limits, and tenancy — Ch 26).
- `output: "standalone"` in `next.config.mjs` so the app ships as a container
  alongside the API.
