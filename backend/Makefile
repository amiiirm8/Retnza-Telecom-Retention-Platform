.PHONY: install test test-all test-non-db lint seed clean

install:
	pip install -r requirements.txt

test:
	python -m pytest -v

test-all:
	python -m pytest -v --tb=short

test-non-db:
	python -m pytest -v \
		app/tests/test_recommendation_rules.py \
		app/tests/test_schema_contracts.py

lint:
	ruff check app/
	mypy app/ --ignore-missing-imports

seed:
	python scripts/seed_db.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
