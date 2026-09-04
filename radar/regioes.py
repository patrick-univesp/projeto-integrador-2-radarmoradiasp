"""Registro canônico dos 96 distritos administrativos do Município de São Paulo
(Lei Municipal 11.220/1992). Fato fixo — não muda. Arquivo versionado, não tabela:
ver a ADR em ``docs/local/arquitetura.md`` ("registro de regiões").

``distrito`` é a chave que já está gravada em ``Transacao.distrito`` — vem do
GeoSampa em caixa alta e sem acento (``tmp/ITBI/cache/distritos.geojson``,
``nm_distrito_municipal``). ``nome`` é curado à mão (fonte: IBGE/Wikipédia,
conferido contra a lei). ``codigo``/``sigla`` também vêm do GeoSampa
(``cd_distrito_municipal``/``sg_distrito_municipal``) — chaves estáveis para o
*choropleth* da fase 4, que não dependem de grafia.

``slug`` é **literal, escrito à mão** — não é calculado com ``slugify()`` nem em
runtime nem na importação. É contrato de URL (#09: "a URL da região pode ser
copiada e aberta em outra sessão"): se fosse derivado de ``slugify(nome)``, uma
troca de versão do Django que mudasse o comportamento da função mudaria o slug
de uma região já compartilhada, silenciosamente, em produção. Os valores abaixo
foram gerados com ``slugify()`` uma vez, na autoria, e conferidos — não pelo app.

Autovalidação (``tests/test_regioes.py``): ``normalizacao._basico(nome) == distrito``
para 95 dos 96 — a mesma transformação (NFKD + remove diacrítico + caixa alta) que o
GeoSampa já aplicou. A única exceção é ``SAO MIGUEL``: o nome oficial do distrito é
São Miguel **Paulista**, mas o GeoSampa abrevia a chave.
"""

from typing import NamedTuple


class Regiao(NamedTuple):
    codigo: str
    sigla: str
    distrito: str
    slug: str
    nome: str
    zona: str


_REGIOES = (
    Regiao("1", "ARA", "AGUA RASA", "agua-rasa", "Água Rasa", "Leste"),
    Regiao("2", "API", "ALTO DE PINHEIROS", "alto-de-pinheiros", "Alto de Pinheiros", "Oeste"),
    Regiao("3", "ANH", "ANHANGUERA", "anhanguera", "Anhanguera", "Norte"),
    Regiao("4", "ARI", "ARICANDUVA", "aricanduva", "Aricanduva", "Leste"),
    Regiao("5", "AAL", "ARTUR ALVIM", "artur-alvim", "Artur Alvim", "Leste"),
    Regiao("6", "BFU", "BARRA FUNDA", "barra-funda", "Barra Funda", "Oeste"),
    Regiao("7", "BVI", "BELA VISTA", "bela-vista", "Bela Vista", "Centro"),
    Regiao("8", "BEL", "BELEM", "belem", "Belém", "Leste"),
    Regiao("9", "BRE", "BOM RETIRO", "bom-retiro", "Bom Retiro", "Centro"),
    Regiao("10", "BRS", "BRAS", "bras", "Brás", "Leste"),
    Regiao("11", "BRL", "BRASILANDIA", "brasilandia", "Brasilândia", "Norte"),
    Regiao("12", "BUT", "BUTANTA", "butanta", "Butantã", "Oeste"),
    Regiao("13", "CAC", "CACHOEIRINHA", "cachoeirinha", "Cachoeirinha", "Norte"),
    Regiao("14", "CMB", "CAMBUCI", "cambuci", "Cambuci", "Centro"),
    Regiao("15", "CBE", "CAMPO BELO", "campo-belo", "Campo Belo", "Sul"),
    Regiao("16", "CGR", "CAMPO GRANDE", "campo-grande", "Campo Grande", "Sul"),
    Regiao("17", "CLM", "CAMPO LIMPO", "campo-limpo", "Campo Limpo", "Sul"),
    Regiao("18", "CNG", "CANGAIBA", "cangaiba", "Cangaíba", "Leste"),
    Regiao("19", "CRE", "CAPAO REDONDO", "capao-redondo", "Capão Redondo", "Sul"),
    Regiao("20", "CAR", "CARRAO", "carrao", "Carrão", "Leste"),
    Regiao("21", "CVE", "CASA VERDE", "casa-verde", "Casa Verde", "Norte"),
    Regiao("22", "CAD", "CIDADE ADEMAR", "cidade-ademar", "Cidade Ademar", "Sul"),
    Regiao("23", "CDU", "CIDADE DUTRA", "cidade-dutra", "Cidade Dutra", "Sul"),
    Regiao("24", "CLD", "CIDADE LIDER", "cidade-lider", "Cidade Líder", "Leste"),
    Regiao("25", "CTI", "CIDADE TIRADENTES", "cidade-tiradentes", "Cidade Tiradentes", "Leste"),
    Regiao("26", "CON", "CONSOLACAO", "consolacao", "Consolação", "Centro"),
    Regiao("27", "CUR", "CURSINO", "cursino", "Cursino", "Sul"),
    Regiao("28", "ERM", "ERMELINO MATARAZZO", "ermelino-matarazzo", "Ermelino Matarazzo", "Leste"),
    Regiao("29", "FRE", "FREGUESIA DO O", "freguesia-do-o", "Freguesia do Ó", "Norte"),
    Regiao("30", "GRA", "GRAJAU", "grajau", "Grajaú", "Sul"),
    Regiao("31", "GUA", "GUAIANASES", "guaianases", "Guaianases", "Leste"),
    Regiao("32", "MOE", "MOEMA", "moema", "Moema", "Sul"),
    Regiao("33", "IGU", "IGUATEMI", "iguatemi", "Iguatemi", "Leste"),
    Regiao("34", "IPI", "IPIRANGA", "ipiranga", "Ipiranga", "Sul"),
    Regiao("35", "IBI", "ITAIM BIBI", "itaim-bibi", "Itaim Bibi", "Oeste"),
    Regiao("36", "IPA", "ITAIM PAULISTA", "itaim-paulista", "Itaim Paulista", "Leste"),
    Regiao("37", "ITQ", "ITAQUERA", "itaquera", "Itaquera", "Leste"),
    Regiao("38", "JAB", "JABAQUARA", "jabaquara", "Jabaquara", "Sul"),
    Regiao("39", "JAC", "JACANA", "jacana", "Jaçanã", "Norte"),
    Regiao("40", "JAG", "JAGUARA", "jaguara", "Jaguara", "Oeste"),
    Regiao("41", "JRE", "JAGUARE", "jaguare", "Jaguaré", "Oeste"),
    Regiao("42", "JAR", "JARAGUA", "jaragua", "Jaraguá", "Norte"),
    Regiao("43", "JDA", "JARDIM ANGELA", "jardim-angela", "Jardim Ângela", "Sul"),
    Regiao("44", "JDH", "JARDIM HELENA", "jardim-helena", "Jardim Helena", "Leste"),
    Regiao("45", "JDP", "JARDIM PAULISTA", "jardim-paulista", "Jardim Paulista", "Oeste"),
    Regiao("46", "JDS", "JARDIM SAO LUIS", "jardim-sao-luis", "Jardim São Luís", "Sul"),
    Regiao("47", "JBO", "JOSE BONIFACIO", "jose-bonifacio", "José Bonifácio", "Leste"),
    Regiao("48", "LAP", "LAPA", "lapa", "Lapa", "Oeste"),
    Regiao("49", "LIB", "LIBERDADE", "liberdade", "Liberdade", "Centro"),
    Regiao("50", "LIM", "LIMAO", "limao", "Limão", "Norte"),
    Regiao("51", "MAN", "MANDAQUI", "mandaqui", "Mandaqui", "Norte"),
    Regiao("52", "MAR", "MARSILAC", "marsilac", "Marsilac", "Sul"),
    Regiao("53", "MOO", "MOOCA", "mooca", "Mooca", "Leste"),
    Regiao("54", "MOR", "MORUMBI", "morumbi", "Morumbi", "Oeste"),
    Regiao("55", "PLH", "PARELHEIROS", "parelheiros", "Parelheiros", "Sul"),
    Regiao("56", "PRI", "PARI", "pari", "Pari", "Leste"),
    Regiao("57", "PQC", "PARQUE DO CARMO", "parque-do-carmo", "Parque do Carmo", "Leste"),
    Regiao("58", "PDR", "PEDREIRA", "pedreira", "Pedreira", "Sul"),
    Regiao("59", "PEN", "PENHA", "penha", "Penha", "Leste"),
    Regiao("60", "PRD", "PERDIZES", "perdizes", "Perdizes", "Oeste"),
    Regiao("61", "PRS", "PERUS", "perus", "Perus", "Norte"),
    Regiao("62", "PIN", "PINHEIROS", "pinheiros", "Pinheiros", "Oeste"),
    Regiao("63", "PIR", "PIRITUBA", "pirituba", "Pirituba", "Norte"),
    Regiao("64", "PRA", "PONTE RASA", "ponte-rasa", "Ponte Rasa", "Leste"),
    Regiao("65", "RTA", "RAPOSO TAVARES", "raposo-tavares", "Raposo Tavares", "Oeste"),
    Regiao("66", "REP", "REPUBLICA", "republica", "República", "Centro"),
    Regiao("67", "RPE", "RIO PEQUENO", "rio-pequeno", "Rio Pequeno", "Oeste"),
    Regiao("68", "SAC", "SACOMA", "sacoma", "Sacomã", "Sul"),
    Regiao("69", "SCE", "SANTA CECILIA", "santa-cecilia", "Santa Cecília", "Centro"),
    Regiao("70", "STN", "SANTANA", "santana", "Santana", "Norte"),
    Regiao("71", "SAM", "SANTO AMARO", "santo-amaro", "Santo Amaro", "Sul"),
    Regiao("72", "SLU", "SAO LUCAS", "sao-lucas", "São Lucas", "Leste"),
    Regiao("73", "SMT", "SAO MATEUS", "sao-mateus", "São Mateus", "Leste"),
    # Exceção documentada no docstring do módulo: nome oficial "São Miguel
    # Paulista", chave do dado "SAO MIGUEL" — o GeoSampa abrevia.
    Regiao("74", "SMI", "SAO MIGUEL", "sao-miguel-paulista", "São Miguel Paulista", "Leste"),
    Regiao("75", "SRA", "SAO RAFAEL", "sao-rafael", "São Rafael", "Leste"),
    Regiao("76", "SAP", "SAPOPEMBA", "sapopemba", "Sapopemba", "Leste"),
    Regiao("77", "SAU", "SAUDE", "saude", "Saúde", "Sul"),
    Regiao("78", "SEE", "SE", "se", "Sé", "Centro"),
    Regiao("79", "SOC", "SOCORRO", "socorro", "Socorro", "Sul"),
    Regiao("80", "TAT", "TATUAPE", "tatuape", "Tatuapé", "Leste"),
    Regiao("81", "TRE", "TREMEMBE", "tremembe", "Tremembé", "Norte"),
    Regiao("82", "TUC", "TUCURUVI", "tucuruvi", "Tucuruvi", "Norte"),
    Regiao("83", "VAN", "VILA ANDRADE", "vila-andrade", "Vila Andrade", "Sul"),
    Regiao("84", "VCR", "VILA CURUCA", "vila-curuca", "Vila Curuçá", "Leste"),
    Regiao("85", "VFO", "VILA FORMOSA", "vila-formosa", "Vila Formosa", "Leste"),
    Regiao("86", "VGL", "VILA GUILHERME", "vila-guilherme", "Vila Guilherme", "Norte"),
    Regiao("87", "VJA", "VILA JACUI", "vila-jacui", "Vila Jacuí", "Leste"),
    Regiao("88", "VLE", "VILA LEOPOLDINA", "vila-leopoldina", "Vila Leopoldina", "Oeste"),
    Regiao("89", "VMR", "VILA MARIA", "vila-maria", "Vila Maria", "Norte"),
    Regiao("90", "VMN", "VILA MARIANA", "vila-mariana", "Vila Mariana", "Sul"),
    Regiao("91", "VMT", "VILA MATILDE", "vila-matilde", "Vila Matilde", "Leste"),
    Regiao("92", "VMD", "VILA MEDEIROS", "vila-medeiros", "Vila Medeiros", "Norte"),
    Regiao("93", "VPR", "VILA PRUDENTE", "vila-prudente", "Vila Prudente", "Leste"),
    Regiao("94", "VSO", "VILA SONIA", "vila-sonia", "Vila Sônia", "Oeste"),
    Regiao("95", "SDO", "SAO DOMINGOS", "sao-domingos", "São Domingos", "Norte"),
    Regiao("96", "LAJ", "LAJEADO", "lajeado", "Lajeado", "Leste"),
)

POR_SLUG = {r.slug: r for r in _REGIOES}
POR_DISTRITO = {r.distrito: r for r in _REGIOES}

# assert some em bytecode otimizado (-O) — este invariante tem que valer sempre.
if len(POR_SLUG) != 96 or len(POR_DISTRITO) != 96 or len(_REGIOES) != 96:
    raise ValueError("slug ou distrito duplicado no registro de regiões")

# Apelidos de busca: nomes populares que não são distrito oficial, slug -> slug
# canônico. Registrado em #06 (nota da "nuvem de regiões" removida): Vila
# Madalena fica dentro de Pinheiros.
APELIDOS = {
    "vila-madalena": "pinheiros",
}


def slug_de_distrito(distrito: str) -> str:
    """``Transacao.distrito`` (caixa alta, sem acento) → slug da região, por
    *lookup* em dicionário. ``""`` se o distrito não está no registro — grava
    vazio, não falha a carga (``carregar_itbi.py``, contador ``sem_regiao``)."""
    r = POR_DISTRITO.get(distrito or "")
    return r.slug if r else ""


def buscar(termo: str) -> Regiao | None:
    """Resolve um termo de busca (nome da região ou apelido) para a ``Regiao``
    canônica. Não faz correspondência parcial — isso é trabalho do autocomplete
    (#06), que casa sobre ``bairro_norm``/``distrito``, não sobre este registro.

    ``slugify()`` aqui só normaliza o termo digitado — diferente dos slugs do
    registro (congelados), não é contrato de URL."""
    from django.utils.text import slugify

    slug = slugify(termo or "")
    slug = APELIDOS.get(slug, slug)
    return POR_SLUG.get(slug)
