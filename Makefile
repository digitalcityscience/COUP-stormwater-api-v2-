
VENV = .venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip

create-env:
	python3 -m venv $(VENV)

venv: create-env
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

fmt:
	black ./stormwater_api/ ./tests/
	isort ./stormwater_api/ ./tests/

lint:
	black --check ./stormwater_api/ ./tests/ 
	isort --check ./stormwater_api/ ./tests/
	flake8 ./stormwater_api/ ./tests/
	mypy ./stormwater_api/ ./tests/
	
