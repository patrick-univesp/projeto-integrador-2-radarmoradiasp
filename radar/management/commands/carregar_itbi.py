"""Carrega a planilha de guias de ITBI pagas no banco.

Lê o ``.xlsx`` em streaming (sem ``pandas``), minera cada linha com
``radar/carga/`` e resolve ``lat``/``lon``/``distrito`` por *lookup* na referência
versionada (``radar/carga/geo_ref.py``, sem ``shapely``). Grava em blocos com
``bulk_create``. Detalhe: ``docs/carga-itbi.md``.
"""

import re
import resource
import time
import unicodedata
from decimal import Decimal

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from radar.carga import coercao, geo_ref, mineracao
from radar.carga.normalizacao import normalizar_bairro, normalizar_logradouro
from radar.models import Transacao
from radar.regioes import slug_de_distrito

# Posições canônicas das 28 colunas. Cada linha da planilha é reordenada para
# esta ordem a partir do cabeçalho da aba (ver ``_mapa_de_colunas``), então o
# resto da carga não depende da ordem em que a planilha traz as colunas.
(C_SQL, C_LOGR, C_NUM, C_COMPL, C_BAIRRO, C_REF, C_CEP, C_NATUREZA,
 C_VALOR, C_DATA, C_VVR, C_PROP, C_VVRP, C_BASE, C_TIPOFIN, C_VALFIN,
 C_CARTORIO, C_MATRIC, C_SITSQL, C_ATERR, C_TESTADA, C_FRACAO, C_ACONSTR,
 C_USOCOD, C_USODESC, C_PADRCOD, C_PADRDESC, C_ACC) = range(28)

# Cabeçalho aceito em cada posição canônica, já passado por ``_chave``. Mais de um
# nome é variação vista de verdade: o valor ganhou "(declarado pelo contribuinte)"
# em 2025, e a aba FEV-2026 escreve "pardão".
CABECALHOS = (
    ("N DO CADASTRO SQL",),
    ("NOME DO LOGRADOURO",),
    ("NUMERO",),
    ("COMPLEMENTO",),
    ("BAIRRO",),
    ("REFERENCIA",),
    ("CEP",),
    ("NATUREZA DE TRANSACAO",),
    ("VALOR DE TRANSACAO DECLARADO PELO CONTRIBUINTE", "VALOR DE TRANSACAO"),
    ("DATA DE TRANSACAO",),
    ("VALOR VENAL DE REFERENCIA",),
    ("PROPORCAO TRANSMITIDA",),
    ("VALOR VENAL DE REFERENCIA PROPORCIONAL",),
    ("BASE DE CALCULO ADOTADA",),
    ("TIPO DE FINANCIAMENTO",),
    ("VALOR FINANCIADO",),
    ("CARTORIO DE REGISTRO",),
    ("MATRICULA DO IMOVEL",),
    ("SITUACAO DO SQL",),
    ("AREA DO TERRENO M2",),
    ("TESTADA M",),
    ("FRACAO IDEAL",),
    ("AREA CONSTRUIDA M2",),
    ("USO IPTU",),
    ("DESCRICAO DO USO IPTU",),
    ("PADRAO IPTU",),
    ("DESCRICAO DO PADRAO IPTU", "DESCRICAO DO PARDAO IPTU"),
    ("ACC IPTU",),
)

# As colunas que a carga grava ou usa para derivar campo. Faltando uma delas, a aba
# é recusada antes de qualquer gravação; as outras podem faltar e viram None.
OBRIGATORIAS = frozenset({
    C_SQL, C_LOGR, C_NUM, C_COMPL, C_BAIRRO, C_CEP, C_NATUREZA, C_VALOR, C_DATA,
    C_PROP, C_VVRP, C_BASE, C_TIPOFIN, C_VALFIN, C_CARTORIO, C_MATRIC, C_SITSQL,
    C_ACONSTR, C_USOCOD,
})

_POR_CABECALHO = {nome: pos for pos, nomes in enumerate(CABECALHOS) for nome in nomes}
_ORDEM_PADRAO = tuple(range(len(CABECALHOS)))


def _chave(texto):
    """``'N° do Cadastro (SQL)'`` → ``'N DO CADASTRO SQL'``: sem acento, maiúsculo,
    só letras e dígitos separados por um espaço."""
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", sem_acento.upper()).split())


def _parece_linha_de_dados(linha):
    """A linha é uma transação na ordem padrão? Confere três colunas de tipo
    inconfundível: SQL na A, natureza "N." na H e data na J."""
    return (
        len(linha) >= len(CABECALHOS)
        and bool(coercao.para_sql(linha[C_SQL]))
        and bool(re.match(r"\s*\d+\s*\.", str(linha[C_NATUREZA] or "")))
        and coercao.para_data(linha[C_DATA]) is not None
    )


def _eh_linha_de_cabecalho(linha):
    """Cabeçalho repetido no meio da aba (JAN e OUT-2024 o têm perto do fim, sinal de
    planilha montada colando pedaços). O SQL numérico é o caso comum e sai cedo."""
    sql = linha[C_SQL] if linha else None
    if not isinstance(sql, str) or sql.strip().isdigit():
        return False
    return sum(1 for c in linha if c is not None and _chave(c) in _POR_CABECALHO) >= 10


def _mapa_de_colunas(cabecalho, aba):
    """Para cada posição canônica, o índice da coluna na aba (``None`` se faltar).
    Devolve também os cabeçalhos ignorados, para o resumo, e se a aba não tem
    cabeçalho: quando a primeira linha já é uma transação na ordem padrão (JAN e
    OUT-2024), ela é lida como dado, e a ordem é a padrão."""
    if not any(c is not None and _chave(c) in _POR_CABECALHO for c in cabecalho):
        if _parece_linha_de_dados(cabecalho):
            return _ORDEM_PADRAO, [], True
        raise CommandError(f"aba {aba}: a primeira linha não é cabeçalho nem uma transação reconhecível")

    indices = [None] * len(CABECALHOS)
    ignoradas, repetidas = [], set()
    for i, celula in enumerate(cabecalho):
        if celula is None or not str(celula).strip():
            continue
        pos = _POR_CABECALHO.get(_chave(celula))
        if pos is None:
            ignoradas.append(str(celula).strip())
        elif pos in repetidas or indices[pos] is not None:
            # Repetida numa coluna que a carga grava: não há como saber qual vale.
            # Numa que ela não usa (NOV-2023 traz "ACC (IPTU)" duas vezes no lugar
            # da descrição do padrão), basta ignorar as duas.
            if pos in OBRIGATORIAS:
                raise CommandError(f"aba {aba}: a coluna {celula!r} aparece duas vezes")
            if pos not in repetidas:
                repetidas.add(pos)
                indices[pos] = None
                ignoradas.append(f"{str(celula).strip()} (repetida)")
        else:
            indices[pos] = i
    faltando = [CABECALHOS[pos][0] for pos in sorted(OBRIGATORIAS) if indices[pos] is None]
    if faltando:
        raise CommandError(f"aba {aba}: faltam as colunas {', '.join(faltando)}")
    return tuple(indices), ignoradas, False


def _reordenar(bruta, indices):
    if indices == _ORDEM_PADRAO:
        return bruta[:len(indices)]
    n = len(bruta)
    return tuple(bruta[i] if i is not None and i < n else None for i in indices)


BLOCOS_PADRAO = 2000


def _dec(x, *, obrigatorio=True):
    """``float`` → ``Decimal`` com 2 casas. ``None`` vira ``0.00`` num campo
    obrigatório (fica marcado por ``qualidade``) e ``None`` num anulável."""
    if x is None:
        return Decimal("0.00") if obrigatorio else None
    return Decimal(f"{float(x):.2f}")


def _linha_para_transacao(bruta, indices, ano_guia, mes_guia):
    sql = coercao.para_sql(bruta[C_SQL])
    if not sql:
        return None

    prop = coercao.para_numero(bruta[C_PROP])
    vvrp = coercao.para_numero(bruta[C_VVRP])
    valor = coercao.para_numero(bruta[C_VALOR])
    base = coercao.para_numero(bruta[C_BASE])
    valfin = coercao.para_numero(bruta[C_VALFIN])
    area = coercao.para_numero(bruta[C_ACONSTR])
    uso_cod = coercao.para_numero(bruta[C_USOCOD])
    data = coercao.para_data(bruta[C_DATA])
    natureza = coercao.para_texto(bruta[C_NATUREZA])
    tipofin = coercao.para_texto(bruta[C_TIPOFIN])
    cartorio = coercao.para_texto(bruta[C_CARTORIO])
    matricula = coercao.para_texto(bruta[C_MATRIC])
    situacao_sql = coercao.para_texto(bruta[C_SITSQL])
    logr = coercao.para_texto(bruta[C_LOGR])
    bairro = coercao.para_texto(bruta[C_BAIRRO])

    lon, lat, nivel, distrito, _sub, _reg = geo_ref.resolver(sql, logr, bruta[C_NUM], indices)
    distrito = (distrito or "")[:60]

    deslocada = mineracao.linha_deslocada(bruta[C_SITSQL], bruta[C_TIPOFIN])
    inconsistente = mineracao.valor_inconsistente(base, valor, vvrp)
    irrisorio = mineracao.valor_irrisorio(valor)
    financiamento_ruim = mineracao.financiamento_incompativel(valor, valfin)
    data_ruim = mineracao.data_implausivel(data)
    sql_ruim = mineracao.situacao_sql_invalida(situacao_sql)

    return Transacao(
        sql=sql,
        logradouro=logr[:150],
        logradouro_norm=normalizar_logradouro(logr)[:150],
        numero=coercao.para_numero_porta(bruta[C_NUM])[:10],
        complemento=coercao.para_texto(bruta[C_COMPL])[:40],
        bairro=bairro[:120],
        bairro_norm=normalizar_bairro(bairro)[:120],
        cep=coercao.para_cep(bruta[C_CEP]),
        distrito=distrito,
        distrito_slug=slug_de_distrito(distrito),
        lat=lat,
        lon=lon,
        geo_nivel=nivel,
        valor_transacao=_dec(valor),
        base_calculo=_dec(base),
        vvr_proporcional=_dec(vvrp, obrigatorio=False),
        valor_financiado=_dec(valfin, obrigatorio=False),
        natureza=natureza[:120],
        tipo_financiamento=tipofin[:80],
        cartorio=cartorio[:60],
        matricula=matricula[:30],
        situacao_sql=situacao_sql[:30],
        data_transacao=data,
        ano_transacao=mineracao.ano_transacao(data),
        area_construida=_dec(area, obrigatorio=False),
        uso_grupo=mineracao.grupo_de_uso(uso_cod)[:40],
        rs_m2_construido=_dec(mineracao.rs_m2_construido(base, area, prop), obrigatorio=False),
        qualidade=mineracao.qualidade(deslocada, inconsistente, irrisorio, financiamento_ruim,
                                      data_ruim, sql_ruim),
        flag_cadastro_defasado=mineracao.cadastro_defasado(natureza, tipofin, prop, uso_cod),
        ano_guia=ano_guia,
        mes_guia=mes_guia,
    )


def _abas_mensais(wb):
    return [a for a in wb.sheetnames if len(a) == 8 and a[3] == "-" and a[:3].isalpha()]


def _pico_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


_CONTADORES = ("lidas", "gravadas", "descartadas", "ruins", "sem_geo", "sem_regiao")


def _zero():
    return dict.fromkeys(_CONTADORES, 0)


def _ler_aba(pagina, indices, primeira_linha, limite, cont, m):
    """Passe 1 de um mês: agrupa as linhas cruas por setor fiscal, para o passe 2
    carregar a referência geo de **um setor por vez** (~poucos MB) em vez da cidade
    inteira (~450 MB). O buffer é de um mês só (~22 MB), então a memória não cresce
    com o número de abas da planilha.
    """
    por_setor: dict[str, list] = {}
    n = 0
    for bruta in pagina.iter_rows(min_row=primeira_linha, values_only=True):
        bruta = _reordenar(bruta, indices)
        if bruta[C_SQL] is None or _eh_linha_de_cabecalho(bruta):
            continue
        if limite and n >= limite:
            break
        n += 1
        cont["lidas"] += 1
        m["lidas"] += 1
        sql = coercao.para_sql(bruta[C_SQL])
        if not sql:
            cont["descartadas"] += 1
            m["descartadas"] += 1
            continue
        por_setor.setdefault(sql[:3], []).append(bruta)
    return por_setor


def _gravar_mes(por_setor, ano_guia, mes_guia, cont, m, *, blocos, sem_geo,
                base_dir_geo, dry_run, substituir_mes):
    """Passe 2 de um mês: constrói as ``Transacao`` setor a setor e grava.

    O ``delete`` do mês e todos os ``bulk_create`` dele são a mesma transação: ou o
    mês é substituído por inteiro, ou o banco fica como estava. Morrer no meio custa
    re-executar o mês, nunca dado pela metade.

    **A construção fica fora da transação de propósito:** ``transaction_mode`` é
    ``IMMEDIATE``, o lock vem no ``BEGIN``, e minerar custa ~80% do tempo do mês —
    dentro da transação, isso seguraria o lock ~20 s e a sessão do admin tomaria
    ``database is locked``.
    """
    objetos = []
    for setor in sorted(por_setor):
        indices = ({}, {}, {}, {}) if sem_geo else geo_ref.indices_de_setor(setor, base_dir_geo)
        for bruta in por_setor.pop(setor):  # drena o buffer cru enquanto constrói
            obj = _linha_para_transacao(bruta, indices, ano_guia, mes_guia)
            cont["gravadas"] += 1
            m["gravadas"] += 1
            if obj.qualidade:
                cont["ruins"] += 1
                m["ruins"] += 1
            if obj.geo_nivel == "--":
                cont["sem_geo"] += 1
                m["sem_geo"] += 1
            elif not obj.distrito_slug:
                # distrito resolvido mas ausente do registro (radar/regioes.py) —
                # não devia acontecer; sinal de a referência geo ter mudado.
                cont["sem_regiao"] += 1
                m["sem_regiao"] += 1
            objetos.append(obj)

    if dry_run:
        return
    if substituir_mes and not objetos:
        return  # aba vazia não apaga o mês que já está no banco

    with transaction.atomic():
        if substituir_mes:
            Transacao.objects.filter(ano_guia=ano_guia, mes_guia=mes_guia).delete()
        for i in range(0, len(objetos), blocos):
            Transacao.objects.bulk_create(objetos[i:i + blocos], batch_size=blocos)


def carregar(arquivo, abas=None, *, blocos=BLOCOS_PADRAO, limite=None, substituir_mes=False,
             limpar=False, dry_run=False, sem_geo=False, base_dir_geo=None, progresso=None):
    """Carga completa, **uma aba (um mês da guia) por vez**.

    Cada aba é lida, minerada e gravada antes de a próxima começar, e o mês
    inteiro entra numa transação só (ver ``_gravar_mes``). Duas consequências:
    a memória é O(linhas de um mês), independente de quantos anos a planilha
    tenha; e um mês nunca fica meio carregado.

    Aceita abas de qualquer ano (``JAN-2025``, ``MAR-2024``…). ``progresso(dict)``
    roda ao fim de cada mês — os contadores só andam depois do *commit*, então
    nunca mostram linha que ainda pode sumir num *rollback*. Devolve o resumo;
    ``resumo["por_mes"]`` tem a quebra por mês da guia, para reconciliar com a
    planilha. É esta função que a tela de admin reusa.
    """
    if limite and (substituir_mes or limpar):
        # Apagaria o mês inteiro e reporia só N linhas — perda de dados, não atalho.
        raise CommandError("--limite não pode ser usado com --substituir-mes nem --limpar")
    if limpar and substituir_mes:
        raise CommandError("--limpar e --substituir-mes são exclusivos: --limpar já apaga tudo")

    t0 = time.monotonic()
    wb = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
    try:
        disponiveis = _abas_mensais(wb)
        alvo = [a for a in disponiveis if a in abas] if abas else disponiveis
        if abas and not alvo:
            raise CommandError(f"nenhuma das abas {abas} existe em {arquivo} (tem: {disponiveis})")

        # Todas as abas são conferidas antes de a primeira ser gravada: uma aba com
        # coluna faltando no fim da planilha não pode deixar as anteriores já gravadas.
        mapas, colunas_ignoradas, sem_cabecalho = {}, {}, []
        for aba in alvo:
            cabecalho = next(wb[aba].iter_rows(min_row=1, max_row=1, values_only=True), ())
            mapas[aba], ignoradas, sem = _mapa_de_colunas(cabecalho, aba)
            if ignoradas:
                colunas_ignoradas[aba] = ignoradas
            if sem:
                sem_cabecalho.append(aba)

        cont = _zero()
        por_mes: dict[str, dict] = {}
        setores = set()

        if limpar and not dry_run:
            Transacao.objects.all().delete()

        for aba in alvo:
            ano_guia, mes_guia = int(aba[4:]), coercao.mes_guia(aba)
            m = por_mes.setdefault(f"{ano_guia}-{mes_guia:02d}", _zero())

            primeira_linha = 1 if aba in sem_cabecalho else 2
            por_setor = _ler_aba(wb[aba], mapas[aba], primeira_linha, limite, cont, m)
            setores.update(por_setor)
            _gravar_mes(
                por_setor, ano_guia, mes_guia, cont, m,
                blocos=blocos, sem_geo=sem_geo, base_dir_geo=base_dir_geo,
                dry_run=dry_run, substituir_mes=substituir_mes,
            )
            if progresso:
                progresso(dict(cont))
    finally:
        wb.close()

    if not dry_run:
        # Sem isto, o otimizador do SQLite decide o plano de consulta às cegas
        # (não existe `sqlite_stat1` recém-criado): pra uma região sem nenhuma
        # transação, ele escolhe o índice de `qualidade` (que cobre ~99% da
        # tabela) em vez do índice de `distrito_slug` — achado real, ~230ms por
        # página contra ~15ms depois do fix. Custa <200ms mesmo com a base
        # inteira; roda de novo a cada carga porque a distribuição muda.
        with connection.cursor() as cur:
            cur.execute("ANALYZE radar_transacao")

    resumo = {"total": cont, "por_mes": por_mes, "setores": len(setores),
              "colunas_ignoradas": colunas_ignoradas, "abas_sem_cabecalho": sem_cabecalho,
              "segundos": round(time.monotonic() - t0, 1), "pico_mb": round(_pico_mb())}
    if progresso:
        progresso({"fim": True, **cont})
    return resumo


class Command(BaseCommand):
    help = "Carrega a planilha de guias de ITBI pagas no banco."

    def add_arguments(self, parser):
        parser.add_argument("--arquivo", required=True)
        parser.add_argument("--abas", help="lista separada por vírgula (padrão: todas)")
        parser.add_argument("--blocos", type=int, default=BLOCOS_PADRAO)
        parser.add_argument("--limite", type=int, help="só as N primeiras linhas por aba")
        parser.add_argument("--limpar", action="store_true", help="apaga tudo antes")
        parser.add_argument("--substituir-mes", action="store_true",
                            help="apaga as linhas do mes_guia+ano de cada aba antes de inserir")
        parser.add_argument("--sem-geo", action="store_true",
                            help="não resolve lat/lon/distrito (tudo '--') — feedback rápido")
        parser.add_argument("--dry-run", action="store_true", help="parseia e valida sem gravar")

    def handle(self, *_args, **o):
        abas = [a.strip() for a in o["abas"].split(",")] if o["abas"] else None

        def progresso(ev):
            if not ev.get("fim"):
                self.stdout.write(
                    f"  {ev['gravadas']} gravadas ({ev['ruins']} qualidade!=0, "
                    f"{ev['sem_geo']} sem geo)", ending="\r"
                )

        try:
            r = carregar(
                o["arquivo"], abas, blocos=o["blocos"], limite=o["limite"],
                substituir_mes=o["substituir_mes"], limpar=o["limpar"],
                dry_run=o["dry_run"], sem_geo=o["sem_geo"], progresso=progresso,
            )
        except FileNotFoundError as e:
            raise CommandError(str(e)) from e

        self.stdout.write(
            "\npor mês da guia (lidas / gravadas / descartadas / qual!=0 / sem geo / sem região):"
        )
        for chave, m in sorted(r["por_mes"].items()):
            self.stdout.write(
                f"  {chave}: {m['lidas']} / {m['gravadas']} / {m['descartadas']} / "
                f"{m['ruins']} / {m['sem_geo']} / {m['sem_regiao']}"
            )

        for aba, nomes in sorted(r["colunas_ignoradas"].items()):
            self.stdout.write(self.style.WARNING(f"  {aba}: colunas ignoradas: {', '.join(nomes)}"))
        for aba in r["abas_sem_cabecalho"]:
            self.stdout.write(self.style.WARNING(f"  {aba}: sem cabeçalho, lida na ordem padrão"))

        t = r["total"]
        self.stdout.write(self.style.SUCCESS(
            f"\n{t['lidas']} lidas · {t['gravadas']} gravadas · {t['descartadas']} sem SQL · "
            f"{t['ruins']} qualidade!=0 · {t['sem_geo']} sem geo · {t['sem_regiao']} sem região\n"
            f"{r['segundos']}s · pico de memória {r['pico_mb']} MB"
            + ("  (dry-run: nada gravado)" if o["dry_run"] else "")
        ))
