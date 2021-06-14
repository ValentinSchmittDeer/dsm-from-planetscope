#!/usr/bin/make -f

.PHONY: python-environment clean clean-docker clear test lint

registry := us.gcr.io/planet-gcr/product
service_name := qc-assessment-service


clean:
	rm -rf static
	find . -path '*/__pycache__/*' -delete
	find . -type d -iname '__pycache__' -delete
	find . -type f -iname '*.pyc' -delete
	find . -type f -iname '*requirements.txt' -delete

lint:
	flake8 .
	black . --check

test:environment
	pytest tests

format:
	autoflake . -r --in-place --remove-all-unused-imports --exclude migrations
	black .
	isort .

python-environment:
	bash scripts/setup_virtual_env.sh
	pip install pip-tools

wipe-python-environment:
	pyenv uninstall -f dsm 2>/dev/null; true
	rm .python-version 2>/dev/null; true
	rm -rf .venv 2>/dev/null; true

environment:python-environment
	pip install -r requirements.txt
	bash scripts/install_gdal.sh

