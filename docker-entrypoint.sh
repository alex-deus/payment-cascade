#!/bin/sh

case "${1}" in
    "bash")
        shift
        exec sh -c "$*"
        ;;
    "wait")
        exec sh -c "while true; do sleep 20; done"
        ;;
    "debug")
        exec ./manage.py runserver 0.0.0.0:8000
        ;;
    "manage")
        shift
        exec ./manage.py "$@"
        ;;
    "run-web")
            exec gunicorn project.wsgi:application \
              --workers ${GUNICORN_WORKERS:-2} \
              --timeout ${GUNICORN_TIMEOUT:-120} \
              --log-level=${GUNICORN_LOG_LEVEL:-info} \
              --bind=${GUNICORN_BIND:-0.0.0.0:8000}
            ;;
    "run-beat")
        exec celery -A project beat -l ${CELERY_LOG_LEVE:-INFO} --scheduler django_celery_beat.schedulers:DatabaseScheduler
        ;;
    "run-worker")
        exec celery -A project worker -l ${CELERY_LOG_LEVE:-INFO} -P threads --concurrency=${CELERY_WORKER_CONCURRENCY:-4}
        ;;
    "run-flower")
        exec celery -A project flower -l INFO --url_prefix=flower
        ;;
esac
