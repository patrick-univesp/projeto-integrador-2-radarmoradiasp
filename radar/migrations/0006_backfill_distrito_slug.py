# Backfill de distrito_slug — não gerada automaticamente. NÃO importa radar.regioes
# de propósito: uma migration reproduz a história do banco mesmo que o registro
# mude depois, então os 96 pares vêm congelados aqui (copiados de radar/regioes.py
# em 04/09/2026). UPDATE por igualdade de distrito, não um laço por linha.

from django.db import migrations

PARES_DISTRITO_SLUG = (
    ("AGUA RASA", "agua-rasa"),
    ("ALTO DE PINHEIROS", "alto-de-pinheiros"),
    ("ANHANGUERA", "anhanguera"),
    ("ARICANDUVA", "aricanduva"),
    ("ARTUR ALVIM", "artur-alvim"),
    ("BARRA FUNDA", "barra-funda"),
    ("BELA VISTA", "bela-vista"),
    ("BELEM", "belem"),
    ("BOM RETIRO", "bom-retiro"),
    ("BRAS", "bras"),
    ("BRASILANDIA", "brasilandia"),
    ("BUTANTA", "butanta"),
    ("CACHOEIRINHA", "cachoeirinha"),
    ("CAMBUCI", "cambuci"),
    ("CAMPO BELO", "campo-belo"),
    ("CAMPO GRANDE", "campo-grande"),
    ("CAMPO LIMPO", "campo-limpo"),
    ("CANGAIBA", "cangaiba"),
    ("CAPAO REDONDO", "capao-redondo"),
    ("CARRAO", "carrao"),
    ("CASA VERDE", "casa-verde"),
    ("CIDADE ADEMAR", "cidade-ademar"),
    ("CIDADE DUTRA", "cidade-dutra"),
    ("CIDADE LIDER", "cidade-lider"),
    ("CIDADE TIRADENTES", "cidade-tiradentes"),
    ("CONSOLACAO", "consolacao"),
    ("CURSINO", "cursino"),
    ("ERMELINO MATARAZZO", "ermelino-matarazzo"),
    ("FREGUESIA DO O", "freguesia-do-o"),
    ("GRAJAU", "grajau"),
    ("GUAIANASES", "guaianases"),
    ("MOEMA", "moema"),
    ("IGUATEMI", "iguatemi"),
    ("IPIRANGA", "ipiranga"),
    ("ITAIM BIBI", "itaim-bibi"),
    ("ITAIM PAULISTA", "itaim-paulista"),
    ("ITAQUERA", "itaquera"),
    ("JABAQUARA", "jabaquara"),
    ("JACANA", "jacana"),
    ("JAGUARA", "jaguara"),
    ("JAGUARE", "jaguare"),
    ("JARAGUA", "jaragua"),
    ("JARDIM ANGELA", "jardim-angela"),
    ("JARDIM HELENA", "jardim-helena"),
    ("JARDIM PAULISTA", "jardim-paulista"),
    ("JARDIM SAO LUIS", "jardim-sao-luis"),
    ("JOSE BONIFACIO", "jose-bonifacio"),
    ("LAPA", "lapa"),
    ("LIBERDADE", "liberdade"),
    ("LIMAO", "limao"),
    ("MANDAQUI", "mandaqui"),
    ("MARSILAC", "marsilac"),
    ("MOOCA", "mooca"),
    ("MORUMBI", "morumbi"),
    ("PARELHEIROS", "parelheiros"),
    ("PARI", "pari"),
    ("PARQUE DO CARMO", "parque-do-carmo"),
    ("PEDREIRA", "pedreira"),
    ("PENHA", "penha"),
    ("PERDIZES", "perdizes"),
    ("PERUS", "perus"),
    ("PINHEIROS", "pinheiros"),
    ("PIRITUBA", "pirituba"),
    ("PONTE RASA", "ponte-rasa"),
    ("RAPOSO TAVARES", "raposo-tavares"),
    ("REPUBLICA", "republica"),
    ("RIO PEQUENO", "rio-pequeno"),
    ("SACOMA", "sacoma"),
    ("SANTA CECILIA", "santa-cecilia"),
    ("SANTANA", "santana"),
    ("SANTO AMARO", "santo-amaro"),
    ("SAO LUCAS", "sao-lucas"),
    ("SAO MATEUS", "sao-mateus"),
    ("SAO MIGUEL", "sao-miguel-paulista"),
    ("SAO RAFAEL", "sao-rafael"),
    ("SAPOPEMBA", "sapopemba"),
    ("SAUDE", "saude"),
    ("SE", "se"),
    ("SOCORRO", "socorro"),
    ("TATUAPE", "tatuape"),
    ("TREMEMBE", "tremembe"),
    ("TUCURUVI", "tucuruvi"),
    ("VILA ANDRADE", "vila-andrade"),
    ("VILA CURUCA", "vila-curuca"),
    ("VILA FORMOSA", "vila-formosa"),
    ("VILA GUILHERME", "vila-guilherme"),
    ("VILA JACUI", "vila-jacui"),
    ("VILA LEOPOLDINA", "vila-leopoldina"),
    ("VILA MARIA", "vila-maria"),
    ("VILA MARIANA", "vila-mariana"),
    ("VILA MATILDE", "vila-matilde"),
    ("VILA MEDEIROS", "vila-medeiros"),
    ("VILA PRUDENTE", "vila-prudente"),
    ("VILA SONIA", "vila-sonia"),
    ("SAO DOMINGOS", "sao-domingos"),
    ("LAJEADO", "lajeado"),
)


def preencher_slug(apps, schema_editor):
    Transacao = apps.get_model("radar", "Transacao")
    for distrito, slug in PARES_DISTRITO_SLUG:
        Transacao.objects.filter(distrito=distrito).update(distrito_slug=slug)


def esvaziar_slug(apps, schema_editor):
    Transacao = apps.get_model("radar", "Transacao")
    Transacao.objects.update(distrito_slug="")


class Migration(migrations.Migration):
    dependencies = [
        ("radar", "0005_distrito_slug"),
    ]

    operations = [
        migrations.RunPython(preencher_slug, esvaziar_slug),
    ]
