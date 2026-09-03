"""Grafias de bairro que a normalização automática não junta sozinha.

Chave: a grafia já passada por ``normalizacao._basico`` (sem acento, caixa alta,
sem pontuação, abreviações expandidas). Valor: a forma canônica.

Cresce à mão. Candidatos: ``python scripts/analisar_bairros.py <planilha.xlsx>``.
Pares abaixo confirmados na extração de 27/08/2026.
"""

GRAFIAS = {
    "VLFORMOSA": "VILA FORMOSA",
    "JDPAULISTA": "JARDIM PAULISTA",
    "ITAIMBIBI": "ITAIM BIBI",
    "CASAVERDE": "CASA VERDE",
    "VLESPERANCA": "VILA ESPERANCA",
    "JDMIRIAM": "JARDIM MIRIAM",
    "VLMONUMENTO": "VILA MONUMENTO",
    "JDBONFIGLIOLI": "JARDIM BONFIGLIOLI",
    "JARDIMJAPAO": "JARDIM JAPAO",
}
