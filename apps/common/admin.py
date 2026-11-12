from django.db.models import JSONField
from jsoneditor.forms import JSONEditor


__all__ = ["JSONFieldAdminMixin"]


class JSONFieldAdminMixin:
    EDITOR_MON_HEIGHT = 550

    formfield_overrides = {
        JSONField: {
            "widget": JSONEditor(
                attrs={"style": f"min-height: {EDITOR_MON_HEIGHT}px; height: {EDITOR_MON_HEIGHT}px"},
                init_options={"mode": "code", "modes": ["code", "tree"]},
            )
        },
    }
