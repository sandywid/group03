.PHONY: test cov clean

test:
	pytest

cov:
	pytest --cov=server --cov-report=term-missing:skip-covered --cov-report=html --cov-report=xml

clean:
	rm -rf .pytest_cache htmlcov .coverage coverage.xml