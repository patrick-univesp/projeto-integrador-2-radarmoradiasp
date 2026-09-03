from django.contrib import admin

# Nada registrado ainda — sem Transacao (issue #01), o admin só mostra Users e
# Groups. Estes três textos são a única personalização de conteúdo, e custam
# zero risco: são strings, não template.
admin.site.site_header = "Radar da Moradia SP · administração"
admin.site.site_title = "Radar da Moradia SP"
admin.site.index_title = "Painel"
