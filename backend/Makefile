.PHONY: contracts test lint run migrate

contracts:
	python -m app.scripts.generate_contracts

migrate:
	python -m app.scripts.init_db

test:
	pytest

lint:
	ruff check .

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
