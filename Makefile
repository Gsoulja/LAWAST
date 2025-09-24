# LAWAST Makefile
.PHONY: help setup run test demo clean

help:
	@echo "LAWAST - Swiss Legal AI Assistant"
	@echo "================================="
	@echo "make setup  - Initial setup"
	@echo "make run    - Run CLI"
	@echo "make demo   - Run demo"
	@echo "make test   - Run tests"
	@echo "make clean  - Clean cache"

setup:
	python quick_start.py
	pip install -r requirements.txt

run:
	python -m src.interfaces.cli.main

demo:
	@echo "Demo: Employment termination question"
	python -m src.interfaces.cli.main "Can I fire an employee for theft?"

extract:
	python scripts/extract_target_laws.py

test:
	python -m pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf data/cache/*
