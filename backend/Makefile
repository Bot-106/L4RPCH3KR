.PHONY: contracts test lint run migrate revision

contracts:
	datamodel-codegen \
		--input ../contracts/schemas \
		--input-file-type jsonschema \
		--output app/contracts/generated \
		--output-model-type pydantic_v2.BaseModel

migrate:
	alembic upgrade head

revision:
	@read -p "message: " msg && alembic revision --autogenerate -m "$$msg"

test:
	pytest

lint:
	ruff check .

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
