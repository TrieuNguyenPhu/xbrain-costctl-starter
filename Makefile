.PHONY: install install-dev test cov sample help clean

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

test:
	pytest -v tests/

cov:
	pytest --cov=commands --cov-report=term-missing tests/

help:
	./costctl.py --help

sample-ec2:
	./costctl.py list ec2 > sample_output/list_ec2_$$(date +%F).txt
	@echo "Wrote sample_output/list_ec2_$$(date +%F).txt"

clean:
	find . -name __pycache__ -prune -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov
