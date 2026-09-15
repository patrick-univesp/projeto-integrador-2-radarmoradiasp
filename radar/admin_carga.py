"""Glue entre a tela de admin e a função ``carregar`` do comando: recebe o upload
do ``.xlsx``, grava um ``CargaMensal`` e roda a carga numa ``thread``. Sem
Celery/Redis — ver ``docs/carga-itbi.md``.
"""

import datetime as dt
import logging
import threading
import time
import uuid
from pathlib import Path

from django import forms
from django.conf import settings
from django.core.files.move import file_move_safe
from django.db import connection
from django.utils import timezone

from radar.management.commands.carregar_itbi import carregar
from radar.models import CargaMensal

logger = logging.getLogger(__name__)

TAMANHO_MAX_MB = 50
# Linha em RODANDO mais velha que isto = thread/processo morto; não bloqueia nova carga.
RODANDO_EXPIRA = dt.timedelta(hours=2)

INTERROMPIDA = (
    "Carga interrompida: o processo morreu antes de terminar (reciclagem do worker, "
    "deploy ou falta de memória). Nenhum mês fica meio carregado — cada mês é gravado "
    "numa transação só —, então é seguro subir a planilha de novo."
)


class FormularioCarga(forms.Form):
    arquivo = forms.FileField(label="Planilha (.xlsx)")
    abas = forms.CharField(
        label="Abas", required=False,
        help_text="separadas por vírgula, ex.: JUL-2026 (vazio = todas)",
    )
    substituir_mes = forms.BooleanField(
        label="Substituir os meses já carregados", required=False, initial=True,
        help_text="apaga as linhas de cada mês da planilha antes de reinserir",
    )

    def clean_arquivo(self):
        f = self.cleaned_data["arquivo"]
        if not f.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Precisa ser um arquivo .xlsx.")
        if f.size > TAMANHO_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(
                f"Arquivo de {f.size / 1e6:.0f} MB; o limite é {TAMANHO_MAX_MB} MB."
            )
        return f


def reconciliar_orfas() -> int:
    """Marca como ``erro`` as cargas presas em ``pendente``/``rodando``.

    A thread é ``daemon``: reciclagem do worker, deploy ou OOM matam a carga sem
    passar pelo ``except``, e a linha diria "rodando" para sempre.
    """
    limite = timezone.now() - RODANDO_EXPIRA
    return CargaMensal.objects.filter(
        status__in=[CargaMensal.PENDENTE, CargaMensal.RODANDO], iniciado_em__lt=limite
    ).update(status=CargaMensal.ERRO, erro_msg=INTERROMPIDA, terminado_em=timezone.now())


def carga_em_andamento() -> bool:
    reconciliar_orfas()
    return CargaMensal.objects.filter(
        status__in=[CargaMensal.PENDENTE, CargaMensal.RODANDO]
    ).exists()


def _abas_lista(texto: str):
    return [a.strip() for a in texto.split(",") if a.strip()] or None


def _apagar_sobras(pasta: Path):
    """Apaga arquivos esquecidos na pasta de upload: a planilha de uma carga cujo
    processo morreu antes do ``finally``, ou o temporário de um upload interrompido.
    Só os velhos — o upload da requisição atual acabou de ser gravado ali."""
    limite = time.time() - RODANDO_EXPIRA.total_seconds()
    for arq in pasta.iterdir():
        if arq.is_file() and arq.stat().st_mtime < limite:
            arq.unlink(missing_ok=True)


def _guardar_upload(arquivo) -> Path:
    """Deixa a planilha em ``FILE_UPLOAD_TEMP_DIR`` com nome próprio, para a thread
    ler depois que a requisição terminar.

    Upload grande já chegou em disco nessa mesma pasta: é só renomear, sem segunda
    cópia. Antes, a cópia ia para o ``/tmp`` e o arquivo ocupava o dobro — num tmpfs
    de 64 MB, uma planilha de 45 MB dava ``No space left on device`` e erro 500.
    """
    pasta = Path(settings.FILE_UPLOAD_TEMP_DIR)
    pasta.mkdir(parents=True, exist_ok=True)
    _apagar_sobras(pasta)
    destino = pasta / f"carga-{uuid.uuid4().hex}.xlsx"
    if hasattr(arquivo, "temporary_file_path"):
        file_move_safe(arquivo.temporary_file_path(), str(destino))
    else:
        with destino.open("wb") as fh:
            for pedaco in arquivo.chunks():
                fh.write(pedaco)
    return destino


def iniciar_carga(arquivo, abas: str, substituir_mes: bool, usuario) -> CargaMensal:
    """Guarda o upload, cria o ``CargaMensal`` e dispara a thread. Volta na hora —
    o progresso é lido da linha."""
    caminho = _guardar_upload(arquivo)

    carga = CargaMensal.objects.create(
        arquivo_nome=arquivo.name, abas=abas, substituir_mes=substituir_mes,
        criado_por=usuario if usuario and usuario.is_authenticated else None,
    )
    threading.Thread(
        target=_rodar, args=(carga.pk, str(caminho), _abas_lista(abas), substituir_mes),
        daemon=True,
    ).start()
    return carga


def _rodar(carga_pk, caminho, abas, substituir_mes):
    CargaMensal.objects.filter(pk=carga_pk).update(status=CargaMensal.RODANDO)

    def progresso(ev):
        CargaMensal.objects.filter(pk=carga_pk).update(
            linhas_gravadas=ev.get("gravadas", 0),
            qualidade_ruim=ev.get("ruins", 0),
            sem_geo=ev.get("sem_geo", 0),
        )

    try:
        r = carregar(caminho, abas, substituir_mes=substituir_mes, progresso=progresso)
        t = r["total"]
        CargaMensal.objects.filter(pk=carga_pk).update(
            status=CargaMensal.CONCLUIDO, terminado_em=timezone.now(),
            linhas_lidas=t["lidas"], linhas_gravadas=t["gravadas"],
            linhas_descartadas=t["descartadas"], sem_geo=t["sem_geo"],
            qualidade_ruim=t["ruins"], pico_mb=r["pico_mb"], por_mes=r["por_mes"],
        )
    except Exception as e:  # noqa: BLE001 — qualquer falha vira status de erro na linha
        # A linha guarda só a mensagem; o traceback vai para o stdout do container.
        logger.exception("carga %s falhou: %s", carga_pk, e)
        CargaMensal.objects.filter(pk=carga_pk).update(
            status=CargaMensal.ERRO, erro_msg=str(e)[:2000], terminado_em=timezone.now(),
        )
    finally:
        Path(caminho).unlink(missing_ok=True)
        if threading.current_thread() is not threading.main_thread():
            connection.close()  # a thread abriu a própria conexão
