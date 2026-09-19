# Movie Muse

Creator-controlled professional filmmaking workspace. V2.1 replaces rich-text-as-domain-model with a typed `ScreenplayDocument`, local-first persistence, and a 47-package DAG.

Canonical completion ledger: `movie_muse_build_status.yaml`.  
Final gate: `./scripts/verify_all.sh` must print `MOVIE_MUSE_PROTOTYPE_VERIFICATION=PASS`.

## Runtimes

- Python 3.11 (compatible with 3.12)
- Node.js 20
- Lockfiles: `requirements-dev.txt`, `backend/requirements.txt`, `frontend/package-lock.json`

## Bootstrap

```bash
./scripts/bootstrap.sh
# or
make bootstrap
```

Copy `.env.example` to `.env`. Never commit secrets.

## Quality

```bash
make lint
make typecheck
make test
make test-frontend
make gates
python3 scripts/mm_status.py runnable
python3 scripts/validate_handoff.py
```

`make gates` runs the MM-001 quality gates. `./scripts/verify_all.sh` stays fail-closed until every named release gate exists and passes.

## Layout

- `src/movie_muse` — modular monolith (public module APIs only)
- `backend` — FastAPI application host
- `frontend` — Web application host
- `config/verification-scopes.yaml` — fingerprint path mapping
- `docs/adr` — architecture decisions

Existing Screenplay SaaS hosts remain. Domain modules land in later DAG packages.

## Docker Compose

```bash
docker-compose up --build
```

- Backend API → http://localhost:8000/health
- Frontend UI → http://localhost:3000
