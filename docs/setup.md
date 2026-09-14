# Executando o projeto

- [Pré-requisitos](#pré-requisitos)
- [Atalhos via Makefile](#atalhos-via-makefile)
- [Setup inicial](#setup-inicial)
- [Linux / macOS](#linux--macos)
- [Windows](#windows)
- [Docker](#docker)
- [Carregar dados](#carregar-dados)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Acessando o sistema](#acessando-o-sistema)
- [Manutenção do banco](#manutenção-do-banco)

## Pré-requisitos

- Python **3.12+** (a CI e o Docker usam 3.14)
- pip
- Git
- Make (opcional, mas recomendado)

## Atalhos via Makefile

| Comando                | Descrição                                        |
| ---------------------- | ------------------------------------------------ |
| `make install`         | Cria o `venv/` e instala `requirements-dev.txt`. |
| `make setup-env`       | Copia `.env.example` para `.env`.                |
| `make migrate`         | Aplica as migrações.                             |
| `make run`             | Sobe o servidor em http://localhost:8000.        |
| `make test`            | Roda a suíte pytest.                             |
| `make lint`            | `ruff check .` + `djlint templates/`.            |
| `make format`          | `ruff format .` + `djlint --reformat`.           |
| `make createsuperuser` | Cria um usuário do `/admin`.                     |
| `make reset-db`        | Apaga o `db.sqlite3` local e recria do zero.     |
| `make sast`            | Bandit + pip-audit.                              |

## Setup inicial

Antes de tudo, o arquivo de variáveis:

```bash
cp .env.example .env
```

O `.env.example` já vem com valores de desenvolvimento — não precisa editar para rodar local.

---

### Linux / macOS

```bash
# 1. venv
python3.12 -m venv venv
source venv/bin/activate

# 2. dependências
pip install -r requirements-dev.txt

# 3. banco (nasce vazio)
python manage.py migrate

# 4. servidor
python manage.py runserver
```

Acesse: http://localhost:8000

---

### Windows

```bat
python -m venv venv
venv\Scripts\activate

pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver
```

Acesse: http://localhost:8000

---

### Docker

A imagem roda Gunicorn + WhiteNoise; o `entrypoint.sh` roda `migrate` sozinho antes
de subir o servidor.

```bash
docker build -t radar-moradia .
docker run -p 8000:8000 --env-file .env radar-moradia
```

Com o `.env` de desenvolvimento, o container roda em **modo dev** (o `.env` define
`DJANGO_SETTINGS_MODULE=config.settings.development`, que sobrepõe o padrão da imagem).
Para exercitar as _settings_ de produção local, use um `.env` com
`DJANGO_SETTINGS_MODULE=config.settings.production`, `SECRET_KEY`,
`ALLOWED_HOSTS=localhost` e `CSRF_TRUSTED_ORIGINS=http://localhost:8000`.

---

## Carregar dados

O banco nasce **vazio**. Não há dump versionado: o dado vem das guias de ITBI pagas,
que a Prefeitura publica em `.xlsx` e que **não entram no repositório** (18–27 MB, e o
repo será público). O que é versionado é a **referência de geocodificação**
(`radar/dados_geo/`, ~13 MB), que a carga consome sem precisar da internet.

### Opção A — uma planilha de verdade

De posse de um `GUIAS DE ITBI PAGAS ... .xlsx`:

```bash
# linha de comando
python manage.py carregar_itbi --arquivo "caminho/GUIAS DE ITBI PAGAS ... .xlsx"

# só um mês, para testar rápido
python manage.py carregar_itbi --arquivo "...xlsx" --abas JUL-2026 --limite 500

# sem resolver geo (feedback quase instantâneo)
python manage.py carregar_itbi --arquivo "...xlsx" --sem-geo --limite 500
```

`--limite` é só para desenvolvimento e **não pode** ser combinado com
`--substituir-mes` nem `--limpar`: apagaria o mês inteiro e reporia apenas as N
primeiras linhas.

Ou pelo admin: `/admin/` → **Cargas mensais → Carregar planilha** (upload de até
50 MB; roda em segundo plano, progresso na própria linha). Aceita abas de qualquer
ano e é idempotente por mês (`--substituir-mes`).

As duas rotas chamam a mesma função de carga, mas **só o upload pelo admin registra
uma linha em Cargas mensais** — pela linha de comando o progresso sai no terminal e
nada é gravado no histórico. Detalhes e todas as _flags_ em
[carga-itbi.md](carga-itbi.md).

### Opção B — a amostra de teste

Para só ver o sistema com algum dado, sem ter uma planilha:

```bash
python manage.py carregar_itbi --arquivo tests/dados/amostra_itbi.xlsx
```

São 12 linhas sintéticas (3 abas, incluindo `MAR-2025`), montadas para exercitar os
casos difíceis. O comando resolve a geo contra o `radar/dados_geo/` versionado, então
a maioria das linhas cai em `T1`/`T3` e uma fica em `--` de propósito. Some
`--sem-geo` para pular a geo por completo.

### Regenerar a referência geo

Só é preciso se `radar/dados_geo/` faltar ou desatualizar. Roda **offline**, precisa de
`shapely` (`pip install -r requirements-geo.txt`) e do cache do GeoSampa:

```bash
python scripts/prefetch_geo.py --cache <pasta-com-o-cache>
```

Ver [referencia-geo.md](referencia-geo.md).

---

## Variáveis de ambiente

Lidas via `python-decouple` a partir do `.env`.

| Variável                 | Descrição                                                             | Exemplo                                                    |
| ------------------------ | --------------------------------------------------------------------- | ---------------------------------------------------------- |
| `SECRET_KEY`             | Chave do Django (obrigatória)                                         | `python -c "import secrets; print(secrets.token_hex(50))"` |
| `DEBUG`                  | Modo de depuração                                                     | `True` / `False`                                           |
| `ALLOWED_HOSTS`          | Hosts permitidos, separados por vírgula                               | `localhost,127.0.0.1`                                      |
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` (local) ou `config.settings.production` |                                                            |
| `DB_PATH`                | Caminho do SQLite (produção)                                          | `/app/data/db.sqlite3`                                     |
| `CSRF_TRUSTED_ORIGINS`   | Origens confiáveis para CSRF (produção)                               | `https://radarsp.prapatrick.com`                           |

Em produção, essas variáveis vêm de _secrets_ do GitHub Actions, não de um `.env` no
repositório.

---

## Acessando o sistema

| Rota                                      | Descrição                                                               |
| ----------------------------------------- | ----------------------------------------------------------------------- |
| `http://localhost:8000/`                  | Página inicial (busca por região).                                      |
| `http://localhost:8000/buscar/?q=<termo>` | Busca — página "em breve" enquanto a fase 2 não fecha.                  |
| `http://localhost:8000/regiao/<slug>/`    | Página da região: valor típico (mediana de R$/m²), faixa de preços e confiança da amostra. `<slug>` validado contra as 96 regiões: inexistente dá 404, apelido redireciona (ex.: `vila-madalena` → `pinheiros`). |
| `http://localhost:8000/entrar/`           | Responde **404** hoje — placeholder, ainda sem autenticação de usuário. |
| `http://localhost:8000/admin/`            | Painel do Django. **Login protegido por `django-axes`.**                |

O admin tem: **Transações** (só-leitura; filtro por `ano_guia`/`mes_guia` para conferir
a contagem de cada mês) e **Cargas mensais** (histórico de cargas, com a quebra
lidas / gravadas / descartadas por mês).

Superusuário local:

```bash
python manage.py createsuperuser
```

---

## Manutenção do banco

O banco local é o `db.sqlite3` na raiz (`.gitignore`).

```bash
# recomeçar do zero
make reset-db          # rm db.sqlite3 && make migrate

# ou manualmente
rm db.sqlite3          # Windows: del db.sqlite3
python manage.py migrate
```

### Se a carga falhar com "no column named ..."

Sintoma de esquema defasado — acontece quando a `0001_initial` foi editada **depois**
de já ter sido aplicada em algum banco (foi o caso de produção uma vez). Como as
tabelas de `radar` costumam estar vazias:

```bash
python manage.py migrate radar zero
python manage.py migrate radar
```

Isso dropa `radar_transacao` e `radar_cargamensal` e recria com o esquema atual.
**Regra:** a `0001` não se edita mais; toda mudança de esquema é migration nova.

### Se a carga for interrompida no meio

Não há o que recuperar. Cada mês da guia é gravado numa transação só — o `delete` e
os `bulk_create` daquele mês são atômicos —, então uma interrupção (falta de memória,
reciclagem do worker, deploy) deixa o mês **como estava antes**, nunca pela metade.
Basta subir a planilha de novo. Se a interrupção tiver sido no upload pelo admin, a
linha em **Cargas mensais** aparece como `erro` explicando o que houve.
