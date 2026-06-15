.PHONY: install run api migrate revision lint test fmt up down

install:
	pip install -e ".[dev]"

run:
	python -m cloud5.bot.main

api:
	uvicorn cloud5.admin.api:app --host 0.0.0.0 --port 8000 --reload

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(m)"

lint:
	ruff check src tests

fmt:
	ruff format src tests
	ruff check --fix src tests

test:
	pytest -q

up:
	docker compose up -d

down:
	docker compose down
