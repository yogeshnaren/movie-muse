PYTHON ?= python3
export PYTHONPATH := src$(if $(PYTHONPATH),:$(PYTHONPATH))

.PHONY: bootstrap lint typecheck test test-frontend status gates verify-all secrets

bootstrap:
	./scripts/bootstrap.sh

lint:
	$(PYTHON) -m ruff check src tests scripts backend

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest

test-frontend:
	cd frontend && npm run test -- --run

status:
	$(PYTHON) scripts/mm_status.py validate
	$(PYTHON) scripts/mm_status.py runnable

secrets:
	$(PYTHON) scripts/mm_status.py secrets

gates:
	./scripts/gates/manifest_and_staleness.sh
	./scripts/gates/static_quality_and_boundaries.sh

verify-all:
	./scripts/verify_all.sh
