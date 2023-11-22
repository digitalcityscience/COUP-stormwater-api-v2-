
VENV = .venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip

create-env:
	python3 -m venv $(VENV)

venv: create-env
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

start:
	docker compose up --build

fmt:
	black ./stormwater_api/ ./tests/
	isort ./stormwater_api/ ./tests/

lint:
	black --check ./stormwater_api/ ./tests/ 
	isort --check ./stormwater_api/ ./tests/
	flake8 ./stormwater_api/ ./tests/
	mypy ./stormwater_api/ ./tests/

build:
	docker compose build

test-it: build 
	docker compose --env-file .env.example run --rm -it  --entrypoint bash stormwater-api -c "/bin/bash"
	docker compose down -v

test-docker: build
	docker-compose --env-file .env.example run --rm  stormwater-api sh -c "sleep 5 && pytest $(pytest-args)"
	docker compose down -v