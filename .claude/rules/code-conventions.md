# Соглашения по коду

## Общие правила
- Язык кода — английский, язык комментариев — русский
- Максимальная длина строки — 120 символов
- Типизация обязательна: аннотации типов во всех публичных функциях и методах
- Импорты: стандартная библиотека → сторонние пакеты → Django-пакеты → внутренние модули
- отделяй return отдельной строкой от блока кода кроме случаем, когда return идет после блока "if"

## Views
- Реализовывать на DRF: `ModelViewSet` или `APIView`
- Располагать в `apps/api/<app_name>/views.py`

## Serializers
- Реализовывать на DRF: `ModelSerializer` или `Serializer`
- Располагать в `apps/api/<app_name>/serializers.py`

## URLs
- Располагать в `apps/api/<app_name>/urls.py`
- Подключать в `apps/api/urls.py`: `path("<path>/", include(("apps.api.<app_name>.urls", "apps.api"), namespace="<app_name>")),`

## Модели
- Всегда добавлять поле `id = models.UUIDField(default=uuid4, editable=False, primary_key=True)`
- Всегда определять `__str__` (использовать `return truncatechars(self.<field>, 32)`)
- Всегда указывать `app_label`, `verbose_name` и `verbose_name_plural` в `Meta`
- Использовать `TextChoices` / `IntegerChoices` вместо строк/чисел напрямую
- Для `ForeignKey`: `<field> = models.ForeignKey("<app_label>.<model_name>", models.<...>, ...)`
- Для дата-времени создания/обновления наследоваться от `CreatedUpdatedBaseModel`, `CreatedBaseModel` из `apps/common/models.py`
- Для `FileField` / `ImageField` использовать `fields.<FileField|ImageField>(upload_to=<method>, max_length=1024)` из `apps.common.fields`

## Celery
- Задачи должны быть идемпотентны
- Располагать в `apps/<app_label>/tasks.py`
- Использовать `task_id` для дедупликации повторных запусков
- Retry-политика: максимум 3 попытки с экспоненциальной задержкой
- Долгие задачи (>30 сек) — выделять в отдельную очередь `heavy`

# База данных
- Только ORM — никакого сырого SQL
- `select_related` / `prefetch_related` прописывать явно, избегать N+1
- `update_fields` обязателен при вызове `.save()` в hotpath
- Транзакции оборачивать в `transaction.atomic()` там, где важна целостность

# Тесты
- разделяй код тест кейсов на три блока: подготовка, тестирование, проверка результата
- в одном тесте тестируй только один кейс (test_case_a, test_cace_b, ...)
