# CI e Docker usam 3.14; ajuste aqui quando tiver 3.14 local.
PYTHON_BIN ?= python3.12
PYTHON = venv/bin/python
PIP = venv/bin/pip
PYTEST = venv/bin/pytest
RUFF = venv/bin/ruff
MANAGE = $(PYTHON) manage.py

.PHONY: help install setup-env migrate run test lint format createsuperuser sast collectstatic reset-db deploy-script

help: ## Exibe esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Cria o venv e instala as dependencias de desenvolvimento
	$(PYTHON_BIN) -m venv venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

setup-env: ## Cria o arquivo .env a partir do exemplo
	cp -n .env.example .env || true

migrate: ## Aplica as migracoes
	$(MANAGE) migrate

makemigrations: ## Gera migracoes a partir dos models
	$(MANAGE) makemigrations

run: ## Sobe o servidor de desenvolvimento
	$(MANAGE) runserver

test: ## Executa os testes
	$(PYTEST) tests/ -v

lint: ## Verifica estilo com ruff
	$(RUFF) check .

format: ## Formata o codigo com ruff
	$(RUFF) format .

collectstatic: ## Coleta os arquivos estaticos
	$(MANAGE) collectstatic --noinput

createsuperuser: ## Cria um superusuario para o /admin
	$(MANAGE) createsuperuser

reset-db: ## Apaga o banco local e recria do zero
	rm -f db.sqlite3
	$(MAKE) migrate

sast: ## Analise de seguranca estatica (Bandit + pip-audit)
	@echo "==> Bandit"
	venv/bin/bandit -c bandit.toml -r radar/ config/
	@echo ""
	@echo "==> pip-audit"
	venv/bin/pip-audit -r requirements.txt

deploy-script: ## Instala/atualiza o script de deploy na VM (uso: make deploy-script VM=ubuntu@IP)
	@test -n "$(VM)" || (echo "Informe o destino: make deploy-script VM=ubuntu@IP"; exit 1)
	scp scripts/deploy_remote.sh $(VM):/tmp/deploy_remote.sh
	ssh $(VM) 'sudo install -m 755 /tmp/deploy_remote.sh /usr/local/bin/radar-deploy.sh && rm -f /tmp/deploy_remote.sh && /usr/local/bin/radar-deploy.sh < /dev/null 2>&1 | head -1'
