# web-starter — Next.js streaming-chat frontend

> Realizes book **Ch 37 (Modern Frontend Essentials)** and **Ch 38 (Building AI Interfaces)**.
> A copy-into-your-job **template**: sane defaults + `TODO` markers + **no business logic**.

A Next.js **App Router** + **TypeScript (strict)** + **Tailwind** frontend wired with the
**Vercel AI SDK** for streaming chat. A server route handler proxies your model/agent backend
and a `useChat()` UI streams the response token-by-token — so you have a real streaming
interface in front of an agent, with the agent logic left to you.

It runs **with zero configuration** out of the box: the default `mock` backend streams a canned
reply with **no API key**, so you can build and style the UI before any backend exists.

---

## Copy me

This is a template — **take it**, don't submodule it:

```bash
# 1. copy the scaffold into your project (you own it now)
cp -r templates/web-starter ~/work/my-chat-ui && cd ~/work/my-chat-ui

# 2. install dependencies (pnpm recommended; npm/yarn/bun also work)
pnpm install

# 3. create your local env file (git-ignored) — defaults to the keyless mock path
cp .env.local.example .env.local

# 4. run it — the UI streams immediately, no key needed
pnpm dev          # → http://localhost:3000

# 5. find every placeholder and fill it in
grep -rn "TODO" .   # or search TODO / ▢ in your editor
```

Then delete this "Copy me" section and make the README yours.

---

## Wire a backend

Pick a backend by setting `CHAT_BACKEND` in `.env.local`. The key (if any) lives **only** in the
server route handler — nothing sensitive ever reaches the browser.

| `CHAT_BACKEND` | What it does | What you must set |
|---|---|---|
| `mock` *(default)* | Echo path; streams a canned reply | nothing — runs keyless |
| `anthropic` | Calls the Claude API directly from the route handler | `ANTHROPIC_API_KEY` (model defaults to `claude-opus-4-8`) |
| `agent` | Proxies your own backend's SSE stream | `AGENT_API_URL` (+ optional `AGENT_API_TOKEN`) |

The one file you edit to wire a backend is **`app/api/chat/route.ts`**. It is transport only —
the three backend functions are stubbed with clear `▢ TODO` markers. The `agent` path already
speaks the [`../fastapi-agent-service`](../fastapi-agent-service/PLAN.md) SSE contract
(`GET /v1/runs/{id}/stream?input=…` emitting JSON `RunEvent` frames), so the two templates
connect out of the box.

> **Secrets stay server-side.** `app/lib/api.ts` and `route.ts` are server modules. Never read a
> secret in a `"use client"` component and never prefix an API key with `NEXT_PUBLIC_`, or it
> ships to the browser bundle.

---

## File tree

```text
web-starter/
├── README.md                  # this file
├── package.json               # next, react, ai (Vercel AI SDK), @ai-sdk/*, tailwind, typescript
├── tsconfig.json              # strict: true
├── next.config.mjs
├── tailwind.config.ts · postcss.config.mjs
├── .eslintrc.json · biome.json   # lint + format config
├── .env.local.example         # ANTHROPIC_API_KEY / AGENT_API_URL  (copy to .env.local — git-ignored)
├── .gitignore                 # ignores .env.local and build output
└── app/
    ├── layout.tsx · page.tsx  # shell + the chat page
    ├── globals.css            # Tailwind entry + base styles
    ├── api/
    │   └── chat/route.ts      # POST handler: streams from mock | anthropic | agent  ▢ wire backend
    ├── components/
    │   ├── Chat.tsx           # useChat() — streaming messages, input, send
    │   └── Message.tsx        # one bubble (Markdown render)
    └── lib/
        └── api.ts             # server-side backend config from env
```

---

## Scripts

| Command | What it does |
|---|---|
| `pnpm dev` | Run the dev server with hot reload |
| `pnpm build` | Production build |
| `pnpm start` | Serve the production build |
| `pnpm typecheck` | `tsc --noEmit` — strict type check, no errors allowed |
| `pnpm lint` | `next lint` (ESLint) |
| `pnpm check` | Biome lint + format check |

---

## Deploy (Vercel)

Zero-config on [Vercel](https://vercel.com): import the repo, and add your environment variables
in **Project → Settings → Environment Variables** (`CHAT_BACKEND`, plus `ANTHROPIC_API_KEY` or
`AGENT_API_URL`/`AGENT_API_TOKEN` depending on the backend). Do **not** commit `.env.local`.

The route handler uses the **Edge runtime** (`export const runtime = "edge"`) for low-latency
streaming. Switch it to `"nodejs"` in `app/api/chat/route.ts` if your backend client needs Node
APIs.

---

## Definition of done (fill the TODOs, then verify)

- [ ] `pnpm install && pnpm dev` runs; the chat page streams tokens (mock path, no key).
- [ ] `pnpm build` and `pnpm typecheck` / lint pass (TS strict, no errors).
- [ ] Backend wired in `route.ts` (`anthropic` provider or `AGENT_API_URL`); the key stays server-side.
- [ ] `.env.local.example` is the only env file committed — **no secret committed**; nothing
      sensitive reaches the client bundle.

---

## Maps to the book

- **Ch 37 — Modern Frontend Essentials:** the TS/React/Next mental model, made concrete.
- **Ch 38 — Building AI Interfaces:** the streaming chat UI (🔧 Build the frontend).
- **Capstone:** mirrors the capstone's `web/` (App Router pages, streaming chat, `lib/` API +
  SSE client).
