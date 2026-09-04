# 🏙️ Radar da Moradia SP

**Portal de consulta de transações imobiliárias reais de São Paulo, a partir das guias de ITBI pagas.**

Projeto Integrador em Computação 2 — **UNIVESP (Universidade Virtual do Estado de São Paulo)**. O argumento central é simples: mostrar **o preço que o comprador de fato pagou**, não o que o vendedor pede.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-6.1-092E20)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC)
![Lint](https://img.shields.io/badge/lint-ruff%20%2B%20djlint-FCC21B)

---

## 🎯 O problema

Quem vai comprar um imóvel em São Paulo decide no escuro. Os valores de anúncio são pedidos, não fechados; os dados de transação real ficam presos em guias de ITBI que ninguém consulta. O resultado é **assimetria informacional** — o comprador não sabe se o preço pedido está perto do que a região vem praticando.

## 💡 A solução

O município publica as **guias de ITBI pagas** (imposto sobre a transmissão de imóveis): valor da transação, base de cálculo, endereço, tipo e área do imóvel. O Radar consolida essas guias num banco, corrige as distorções conhecidas da base (fração transmitida, datas antigas, linhas defeituosas), geocodifica cada transação e entrega:

- **busca por região** (rua, CEP ou bairro);
- o **valor típico do metro quadrado** da região — a mediana de R$/m², com a faixa de preços e quantas vendas sustentam o número;
- as transações da região **no mapa**, com a precisão de cada ponto;
- **série temporal** e **comparação** entre regiões.

---

## 🛠️ Stack

| Camada        | Ferramentas                                                                                                            |
| ------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **Backend**   | Django 6.1, Python 3.12 (local) / 3.14 (CI e Docker), python-decouple                                                  |
| **Banco**     | SQLite (WAL) — sem servidor de banco; o dado cabe num arquivo                                                          |
| **Dados**     | guias de ITBI (`.xlsx` da Secretaria da Fazenda de SP) → mineração em streaming, **sem `pandas`/`shapely`** no runtime |
| **Geo**       | referência de lote/distrito pré-calculada offline e **versionada** em `radar/dados_geo/`; _lookup_ em runtime          |
| **Frontend**  | HTML + CSS + JS, renderização no servidor; MapLibre GL no mapa (fase 4); ícones de tipo de imóvel de [Tabler Icons](https://tabler.io/icons) (MIT) |
| **Servidor**  | Gunicorn + WhiteNoise                                                                                                  |
| **Segurança** | `django-axes` no login do admin; `django-ratelimit` nos endpoints públicos; `.env` via `python-decouple`              |
| **Qualidade** | pytest, pytest-django, ruff, djlint, bandit, pip-audit                                                                 |
| **Deploy**    | GitHub Actions → GHCR → VM Oracle Cloud Always Free, atrás de Cloudflare Tunnel (sem porta exposta)                    |

---

## 📂 Estrutura do repositório

```
radar/            App Django: models, views, admin, e radar/carga/ (coerção,
                  normalização, mineração, geo_ref) + o comando carregar_itbi
radar/dados_geo/  Referência de geocodificação versionada (269 setores, ~13 MB)
config/           Settings (base/development/production), URLs, WSGI/ASGI
scripts/          prefetch_geo.py (gera a referência geo, offline) e utilitários
tests/            Suíte pytest; tests/dados/ tem a amostra sintética do CI
templates/        base.html, 404/500, admin customizado, telas do radar
static/           CSS (tokens.css / base.css), fontes, imagens, JS
docs/             Documentação técnica versionada (ver tabela no fim)
.github/          Workflow único de CI + CD (ci-cd.yml)
```

---

## 🚀 Quick start

Requer **Python 3.12+** e Git. `make` é opcional mas recomendado.

```bash
git clone <url> radar-moradia && cd radar-moradia

make install        # cria venv/ e instala requirements-dev.txt
make setup-env      # copia .env.example para .env
make migrate        # cria o banco (vazio)
make run            # http://localhost:8000
```

O banco nasce **vazio** — não há dump versionado. Para ter dado dentro, ver
**[docs/setup.md](docs/setup.md) → "Carregar dados"** (você precisa de uma planilha
de ITBI, ou pode usar a amostra de teste para experimentar).

Superusuário do admin: `make createsuperuser`.

### 🐳 Docker

```bash
docker build -t radar-moradia .
docker run -p 8000:8000 --env-file .env radar-moradia
```

---

## 🧪 Testes & qualidade

```bash
make test     # pytest tests/ -v
make lint     # ruff check . + djlint templates/
make format   # ruff format . + djlint --reformat
make sast     # bandit + pip-audit
```

O `.github/workflows/ci-cd.yml` roda lint, checagem de migrações, pytest e SAST a cada push e PR; o deploy só acontece se tudo passar na `main`.

---

## 🗺️ Como os dados entram

A planilha de ITBI **não vai para o repositório** (18–27 MB, e o repo será público). O que é versionado é a **referência de geocodificação** (`radar/dados_geo/`), gerada uma vez, offline, por `scripts/prefetch_geo.py`.

Duas formas de carregar uma planilha:

- **pela linha de comando** — `python manage.py carregar_itbi --arquivo <planilha>.xlsx`;
- **pelo admin** — `/admin/` → _Cargas mensais_ → _Carregar planilha_ (upload, roda em segundo plano).

A carga aceita abas de qualquer ano (`JAN-2025`, `MAR-2024`…) e é idempotente por mês:
cada mês entra numa transação só, então uma interrupção nunca deixa mês pela metade. Detalhes em **[docs/carga-itbi.md](docs/carga-itbi.md)**.

---

## ☁️ Deploy

`push` na `main` → GitHub Actions constrói a imagem, publica no GHCR e faz `docker run` na VM via SSH, com _rollback_ automático se o _health check_ reprovar. A VM **não expõe porta**: o `cloudflared` abre um túnel de saída para a Cloudflare, que serve o TLS.

Configuração sensível vem de _secrets_ do GitHub (ver `.env.example`).

---

## 📚 Documentação

| Documento                          | Conteúdo                                                                                           |
| ---------------------------------- | -------------------------------------------------------------------------------------------------- |
| **[docs/setup.md](docs/setup.md)** | Como executar (Linux, Windows, Docker), variáveis de ambiente, carregar dados, manutenção do banco |
