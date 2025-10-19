.PHONY: test cov clean

test:
	LOG_PATH=logs/app.log python -m pytest

cov:
	LOG_PATH=logs/app.log python -m pytest

clean:
	rm -rf .pytest_cache htmlcov .coverage coverage.xml
