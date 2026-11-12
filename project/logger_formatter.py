import logging

from django.conf import settings
from django.utils import timezone
from json_log_formatter import VerboseJSONFormatter


class JSONFormatter(VerboseJSONFormatter):
    def json_record(self, message: str, extra: dict, record: logging.LogRecord) -> dict:
        if "request" in extra:
            del extra["request"]

        extra["branch"] = settings.BRANCH
        extra["commit"] = settings.COMMIT

        extra["hostname"] = settings.HOSTNAME

        extra["level"] = record.levelname
        extra["name"] = record.name

        extra["message"] = message

        if "time" not in extra:
            extra["time"] = timezone.now()

        if record.exc_info:
            extra["exc_info"] = self.formatException(record.exc_info)

        return extra
