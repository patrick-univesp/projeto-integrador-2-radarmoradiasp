from pathlib import Path

from django.apps import AppConfig
from django.conf import settings


class RadarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "radar"

    def ready(self):
        Path(settings.FILE_UPLOAD_TEMP_DIR).mkdir(parents=True, exist_ok=True)
