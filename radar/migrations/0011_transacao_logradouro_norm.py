# Campo da busca por rua. O SQL é escrito à mão: para adicionar uma coluna, o Django
# recria a tabela inteira no SQLite, com os doze índices, e o deploy só espera 60 s a
# aplicação responder depois do migrate. ADD COLUMN com DEFAULT não reescreve nada.
#
# As linhas que já estavam na base ficam com o campo vazio: reescrever ~366 mil linhas
# levaria perto de um minuto na VM. A carga grava o campo, então recarregar a base
# preenche tudo.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("radar", "0010_transacao_vvr_proporcional"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE radar_transacao "
                    "ADD COLUMN logradouro_norm varchar(150) NOT NULL DEFAULT ''",
                    "ALTER TABLE radar_transacao DROP COLUMN logradouro_norm",
                ),
                migrations.RunSQL(
                    'CREATE INDEX "radar_transacao_logradouro_norm_105ffa86" '
                    'ON "radar_transacao" ("logradouro_norm")',
                    'DROP INDEX "radar_transacao_logradouro_norm_105ffa86"',
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="transacao",
                    name="logradouro_norm",
                    field=models.CharField(blank=True, db_index=True, max_length=150),
                ),
            ],
        ),
    ]
