# Структура проект

```
project
│   ├── celery.py
│   ├── fixtures
│   ├── locale
│   ├── logger_formatter.py
│   ├── middlewares.py
│   ├── redis_client.py
│   ├── sentry.py
│   ├── settings.py
│   ├── templates
│   ├── urls.py
│   └── wsgi.py
├── apps
│   ├── api/             # API на Django REST Framework
│   │   ├── apps.py
│   │   ├── base_test.py
│   │   ├── docs/        # Схема и документация API
│   │   │   ├── schema.py
│   │   │   ├── tests.py
│   │   │   ├── urls.py
│   │   │   └── views.py
│   │   ├── payment/     # API платежей и провайдеров
│   │   │   ├── filters.py
│   │   │   ├── serializers.py
│   │   │   ├── tests/
│   │   │   │   └── payment/
│   │   │   ├── urls.py
│   │   │   └── views.py
│   │   ├── user/        # API пользователей
│   │   │   ├── serializers.py
│   │   │   ├── tests/
│   │   │   │   └── profile/
│   │   │   ├── urls.py
│   │   │   └── views.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── common/          # Общие утилиты
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── base_test.py
│   │   ├── management/
│   │   │   └── commands/
│   │   ├── tasks.py
│   │   ├── utils.py
│   │   └── views.py
│   ├── payment/         # Django приложение с платежами: Config, Provider, Payment, Attempt
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── migrations/
│   │   ├── models.py
│   │   ├── provider/    # Интерфейс и реализации провайдеров
│   │   │   ├── base.py
│   │   │   ├── provider_a.py
│   │   │   ├── provider_b.py
│   │   │   └── provider_c.py
│   │   ├── tasks.py     # Celery-задачи платежей
│   │   └── tests/
│   │       ├── tasks/
│   │       │   ├── make_payment/
│   │       │   │   ├── test_make_payment.py
│   │       │   │   └── test_make_payment_concyrency.py
│   │       │   ├── test_deactivate_providers.py
│   │       │   └── test_mark_stale_attempts_as_timed_out.py
│   │       └── test_admin.py
│   └── users/           # модель для пользователей
├── .docker/             # Docker файл
├── .pre-commit-config.yaml
├── .env                 # Локальные переменны
├── pyproject.toml
└── manage.py
```