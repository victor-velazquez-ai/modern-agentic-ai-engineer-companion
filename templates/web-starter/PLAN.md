# Template — Web Starter (Next.js streaming chat)
> Realizes book Ch 37, 38 · Status: 📋 planned (Phase 1)

## What it scaffolds
A Next.js **App Router** + TypeScript + Tailwind frontend wired with the **Vercel AI SDK** for
streaming chat — a route handler that proxies to your model/agent backend and a `useChat` chat
UI — so you have a real streaming interface in front of an agent, with the agent logic stubbed.

## When to copy it
You need a web UI that streams an agent's responses token-by-token — an internal tool, a demo,
or the front end of your product — and want a modern, typed, deploy-ready starter rather than
wiring SSE/streaming from scratch. Copy the folder and `pnpm dev`.

## Planned file tree
```text
web-starter/
├── README.md                  # run + deploy (Vercel); "copy me"
├── package.json               # next, react, ai (Vercel AI SDK), @ai-sdk/*, tailwind, typescript
├── tsconfig.json              # strict: true
├── next.config.mjs
├── tailwind.config.ts · postcss.config.mjs · app/globals.css
├── .env.local.example         # ANTHROPIC_API_KEY / AGENT_API_URL ; (never .env.local itself)
├── .eslintrc / biome.json     # lint config
└── app/
    ├── layout.tsx · page.tsx  # shell + the chat page
    ├── api/
    │   └── chat/route.ts      # POST handler: streams from model/agent (Edge-ready) — ▢ wire backend
    ├── components/
    │   ├── Chat.tsx           # useChat() — streaming messages, input, send
    │   └── Message.tsx        # one bubble (markdown render)
    └── lib/
        └── api.ts             # client helper / backend base URL from env
```

## Defaults baked in
- **App Router + TS strict:** modern Next.js, `strict: true`, server route handler for the
  model call (no key in the browser).
- **Streaming via the Vercel AI SDK:** `route.ts` returns a streaming response; `Chat.tsx` uses
  `useChat()` so tokens render as they arrive — the whole point of the template.
- **Tailwind preconfigured:** minimal, clean chat styling out of the box.
- **Secrets server-side only:** the model/agent key lives in the route handler's env
  (`.env.local`, git-ignored); the example file is `.env.local.example`. Nothing sensitive ships
  to the client. A `MOCK`/echo path lets the UI run with no key.
- **Backend-agnostic:** `route.ts` can call a provider SDK directly **or** proxy
  `AGENT_API_URL` (your FastAPI service) — both paths stubbed with a `TODO`.
- **Deploy-ready:** Vercel defaults; model default is the latest, most capable Claude model.

## Maps to the book
- **Ch 37 — Modern Frontend Essentials:** the TS/React/Next mental model, made concrete.
- **Ch 38 — Building AI Interfaces:** the streaming chat UI (🔧 Build the frontend).
- **Notebook:** the [`learn/part-09-…/38-building-ai-interfaces/`](../../learn/) walkthrough
  builds this surface. **Template:** `route.ts` proxies
  [`../fastapi-agent-service/`](../fastapi-agent-service/PLAN.md) (its SSE/`/v1/runs`).
  **Capstone:** mirrors `web/` (App Router pages, streaming chat, `lib/` API+SSE client) in
  [`../../../chapters/92-appendix-capstone.typ`](../../../chapters/92-appendix-capstone.typ).

## Phase-2 definition of done
- [ ] `pnpm install && pnpm dev` runs; the chat page streams tokens (mock/echo path, no key).
- [ ] `pnpm build` and `pnpm typecheck`/lint pass (TS strict, no errors).
- [ ] Backend wiring (provider SDK or `AGENT_API_URL`) is a clear `▢`/`TODO`; key stays server-side.
- [ ] `.env.local.example` only — **no secret committed**; nothing sensitive reaches the client bundle.
