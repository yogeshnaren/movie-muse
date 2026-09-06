# MM-001 verification commands

Run from a clean checkout of this commit with Python 3.11+ and Node 20.

```bash
python3 -m pip install -r requirements-dev.txt
cd frontend && npm ci && cd ..
python3 scripts/validate_handoff.py
PYTHONPATH=src python3 scripts/mm_status.py validate
PYTHONPATH=src python3 scripts/mm_status.py check-scopes
PYTHONPATH=src python3 scripts/mm_status.py runnable
PYTHONPATH=src python3 scripts/mm_status.py boundaries
PYTHONPATH=src python3 scripts/mm_status.py secrets
python3 -m ruff check src tests scripts backend
python3 -m mypy
python3 -m pytest
cd frontend && npm run typecheck && npm run test -- --run
./scripts/gates/manifest_and_staleness.sh
./scripts/gates/static_quality_and_boundaries.sh
./scripts/verify_all.sh   # must fail closed: missing migrations_backup_and_recovery
```

Acceptance for MM-001:

- Clean bootstrap works in this environment
- Lockfiles committed (`requirements-dev.txt`, `backend/requirements.txt`, `frontend/package-lock.json`)
- CI fails on lint/type/test/schema/DAG errors
- No real secret in source or logs
- Module-boundary tests reject cross-module internals
- Status tool lists only MM-001 as runnable
- `verify_all.sh` does not print the PASS sentinel
