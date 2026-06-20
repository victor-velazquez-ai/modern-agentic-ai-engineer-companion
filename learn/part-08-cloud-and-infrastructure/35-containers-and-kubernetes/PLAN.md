# Ch 35 — Containers & Kubernetes

> Companion plan · Part VIII · book file `chapters/35-containers-and-kubernetes.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Containers are the one piece of this part that's genuinely cheap to run locally and pays off
immediately, so this chapter gets a hands-on **walkthrough**: Dockerize the capstone's FastAPI
service into a small, layered, non-root, multi-stage image and run it with Compose — no cloud
needed. Kubernetes, by contrast, is expensive to operate and the book's whole point is *when
not to reach for it*, so K8s is handled as a **concept lab**: read real manifests, simulate
desired-state reconciliation and HPA scaling offline, and practice the Fargate-vs-K8s decision
— without standing up a cluster. The Docker walkthrough's output becomes
`templates/dockerfile-and-compose/`.

## Planned notebooks

### 35-01 · `35-01-dockerize-a-service.ipynb` — 🔧 Build: Dockerize the capstone API
- **Type:** walkthrough  *(this is the chapter's 🔧 Build surface for containerization)*
- **Maps to:** §35.1 (Docker: containers for AI services — multi-stage, non-root, slim runtime)
- **Objective:** containerize the FastAPI agent service into a small, cache-efficient,
  non-root image and run it locally with `docker compose` — the artifact every later deploy uses.
- **Prereqs:** Ch 25 (FastAPI service); Docker installed locally (the one real local dependency).
- **Cell arc:**
  - 🧠 mental model: an image = code + runtime + deps frozen; "ship your machine" reproducibility.
  - Author a **multi-stage** Dockerfile (build stage installs deps; slim runtime copies only
    artifacts) — the §35.1 shape, `USER 1000`, explicit `CMD` for uvicorn.
  - Build the image and inspect layers/size; 🔮 *predict* which change busts the layer cache,
    then reorder `COPY` to fix it.
  - A minimal `docker-compose.yml` wiring the API + a Postgres + Redis for local dev.
  - Run `compose up`, hit the health endpoint, read logs; tear down cleanly.
  - ⚠️ pitfall: running as root / fat images / secrets baked into layers — show each, then fix
    (non-root user, slim base, secrets via env at runtime not build).
  - ⚠️ pitfall (GPU, §35.1 tip): CUDA base image must match host driver + NVIDIA runtime — the
    #1 "works locally, fails in cluster" trap; explained (not run, to stay GPU-free).
  - 🎯 senior lens: small, reproducible images are the unit of deploy for Fargate/ECR (Ch 33)
    and K8s alike; the Dockerfile is the contract.
  - Ends pointing at the production version: [`templates/dockerfile-and-compose/`](../../../templates/dockerfile-and-compose/).
- **Datasets/fixtures:** reuses a minimal FastAPI app stub in `data/` (or imports the Ch 25
  service shape); no large data.
- **APIs & cost:** **none / offline.** Local Docker only — **no cloud, no spend.** (If Docker
  isn't available, the cells degrade to printing the commands; no API key anywhere.)
- **You'll be able to:** produce a lean, non-root, multi-stage image and run the service with
  Compose — the build artifact every cloud deploy in this part consumes.

### 35-02 · `35-02-kubernetes-without-a-cluster.ipynb` — Read manifests, simulate desired-state
- **Type:** concept-lab
- **Maps to:** §35.2 (K8s core concepts + when you need it), §35.3 (deploying/scaling: HPA,
  health probes), §35.4 (Helm, operators, ecosystem)
- **Objective:** understand Deployment/Service/Ingress/HPA and the declarative reconcile loop —
  and make the Fargate-vs-Kubernetes call — without operating a cluster.
- **Prereqs:** 35-01; Ch 28 (liveness/readiness probes); Ch 33 (Fargate/EKS trade-off).
- **Cell arc:**
  - 🧠 mental model: declarative desired-state — you declare N replicas, the controller makes
    reality match (restart, reschedule, rebalance).
  - Read a small set of YAML manifests (Deployment, Service, Ingress, HPA, ConfigMap/Secret) and
    parse them in-cell to label each object's job — no `kubectl`, no cluster.
  - A tiny offline "reconciler": current replicas vs desired → actions; kill a pod, watch it
    "restart" in the simulation. 🔮 *predict* the action before each step.
  - Simulate the **HPA** scaling Celery workers to queue depth (Ch 31): feed a backlog curve,
    compute target replicas; 🔮 *predict* the scale-up point.
  - Health probes (Ch 28): show how readiness gates traffic and liveness triggers restart — as
    a small state machine, offline.
  - Helm/operators: templated charts and day-two automation — a conceptual cell, not a deploy.
  - ⚠️ pitfall (§35.2): adopting K8s for what Fargate or two containers would serve — model the
    operational cost; reach for K8s only at real scale/teams/GPU-scheduling/portability needs.
  - 🎯 senior lens (§35.4): operational leverage *vs* operational cost — choose the infra your
    team can operate *well*, not the most powerful one.
- **Datasets/fixtures:** a few small committed `data/*.yaml` manifests + a synthetic queue-depth
  series generated in-cell.
- **APIs & cost:** none — fully offline. **No cluster, no cloud, no spend.** Manifests are parsed
  and simulated, never applied.
- **You'll be able to:** read K8s manifests fluently, explain desired-state reconciliation and
  HPA scaling, and defend a Fargate-vs-Kubernetes decision on your team's real constraints.

## Feeds (cross-pillar)
- **Blueprint(s):** — (the containerized service underpins service-shaped blueprints; no new one).
- **Template(s):** **produces** [`templates/dockerfile-and-compose/`](../../../templates/dockerfile-and-compose/)
  (the multi-stage Dockerfile + Compose for local dev) — the 35-01 build hardened into a
  copy-into-your-job scaffold.
- **Capstone:** the image from 35-01 is what `capstone/app/` and `capstone/workers/` ship as;
  the manifests in 35-02 are the K8s-path reference for the capstone's deploy story. Advances
  checkpoint `checkpoints/ch35-containerized`.

## Dependencies
- Ch 25 (FastAPI service to containerize) · Ch 28 (health probes) · Ch 33 (Fargate/EKS, ECR).
  Ch 36 (IaC) deploys the resulting image.

## Phase-2 definition of done
- [ ] 35-01 builds and runs locally with Docker/Compose (no cloud, no spend); degrades
      gracefully to printed commands if Docker is absent. 35-02 runs fully offline (no cluster).
- [ ] The Dockerfile shape (multi-stage, non-root, slim) and the K8s objects/HPA/probes match
      the book's §35 content; the Fargate-vs-K8s guidance matches the §35.2/§35.4 lenses.
- [ ] 35-01 ends by pointing at `templates/dockerfile-and-compose/`; secrets via env only, none
      baked into images.
- [ ] Each notebook ends with recap + exercises and links onward (template, capstone, Ch 36 IaC).
