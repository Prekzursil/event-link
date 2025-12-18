.PHONY: lint lint-ui lint-backend format format-ui format-backend format-check format-check-backend

BACKEND_PYTHON ?= $(shell if [ -x backend/.venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)

lint: lint-ui lint-backend

lint-ui:
	cd ui && npm run lint

lint-backend:
	cd backend && $(BACKEND_PYTHON) -m ruff check .

format: format-ui format-backend

format-ui:
	cd ui && npm run format

format-backend:
	cd backend && $(BACKEND_PYTHON) -m ruff check --fix .
	cd backend && $(BACKEND_PYTHON) -m black .

format-check: format-check-backend

format-check-backend:
	cd backend && $(BACKEND_PYTHON) -m black --check .
