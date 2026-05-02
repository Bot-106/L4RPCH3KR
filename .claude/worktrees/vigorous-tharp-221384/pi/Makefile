.PHONY: contracts test lint run

contracts:
	datamodel-codegen \
		--input ../contracts/schemas \
		--input-file-type jsonschema \
		--output larpchekr/contracts/generated \
		--output-model-type pydantic_v2.BaseModel

test:
	pytest

lint:
	ruff check .

run:
	python -m larpchekr.main
