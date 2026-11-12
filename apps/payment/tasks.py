import logging
from datetime import timedelta
from inspect import iscoroutinefunction
from uuid import UUID

from asgiref.sync import async_to_sync
from celery import Task, shared_task
from django.db import connection, transaction
from django.db.models import Count, Exists, OuterRef
from django.utils import timezone

from apps.common.tasks import TracedTask
from apps.payment.models import Attempt, Config, Payment, Provider
from apps.payment.provider.base import PaymentStatus
from apps.users.models import User


__all__ = ["make_payment"]

logger = logging.getLogger("celery.tasks")


def schedule_payment(payment_id: str | UUID) -> None:
    def publish() -> None:
        try:
            make_payment.apply_async(args=[str(payment_id)], task_id=f"make_payment:{payment_id}")
        except Exception:
            # Периодическое восстановление повторит отправку после сбоя брокера.
            logger.exception("Unable to schedule payment %s", payment_id)

    transaction.on_commit(publish)


@shared_task(base=TracedTask, bind=True, ignore_result=True)
def resume_failed_payments(self: Task) -> None:
    attempts = Attempt.objects.filter(payment_id=OuterRef("pk"))
    payments = (
        Payment.objects.filter(status=Payment.STATUS.PENDING, funds_reserved=True)
        .annotate(
            has_failed=Exists(attempts.filter(status=Attempt.STATUS.FAILED)),
            has_unresolved=Exists(attempts.exclude(status=Attempt.STATUS.FAILED)),
        )
        .filter(has_failed=True, has_unresolved=False)
        .values_list("pk", flat=True)
    )
    for payment_id in payments.iterator():
        schedule_payment(payment_id)


@shared_task(
    base=TracedTask,
    bind=True,
    ignore_result=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=20,
    retry_jitter=True,
)
def make_payment(self: Task, payment_id: str | UUID) -> None:
    if connection.in_atomic_block:
        raise RuntimeError("make_payment must run outside an existing transaction")

    while True:
        with transaction.atomic():
            # Check payment exists
            payment = Payment.objects.select_for_update().filter(pk=payment_id).first()
            if not payment:
                return logger.warning(f"Payment {payment_id} was not found")

            # Check Payment status
            if payment.status not in [Payment.STATUS.CREATED, Payment.STATUS.PENDING]:
                return logger.info(f"{payment_id=} is already done")

            # Checking active attempts
            if payment.attempts.exclude(status=Attempt.STATUS.FAILED).exists():
                return logger.info(f"{payment_id=} is already been processing")

            if payment.amount <= 0:
                payment.status = Payment.STATUS.FAILED
                payment.save(update_fields=["status", "updated"])
                return logger.warning(f"{payment_id=} has an invalid amount")

            # Checking left attempts count
            ids = payment.attempts.values_list("provider_id", flat=True)
            provider: Provider = Provider.objects.filter(is_active=True).exclude(pk__in=ids).order_by("slug").first()
            if not provider:
                if payment.funds_reserved:
                    user = User.objects.select_for_update().get(pk=payment.user_id)
                    user.frozen_balance -= payment.amount
                    user.save(update_fields=["frozen_balance"])
                    payment.funds_reserved = False
                payment.status = Payment.STATUS.FAILED
                payment.save(update_fields=["status", "funds_reserved", "updated"])

                return logger.info(f"{payment_id=} is finished with status failed: no attempts left")

            if not payment.funds_reserved:
                user = User.objects.select_for_update().get(pk=payment.user_id)
                if user.balance - user.frozen_balance < payment.amount:
                    payment.status = Payment.STATUS.FAILED
                    payment.save(update_fields=["status", "updated"])
                    return logger.info(f"{payment_id=} has insufficient available funds")
                user.frozen_balance += payment.amount
                user.save(update_fields=["frozen_balance"])
                payment.funds_reserved = True

            # Set status to "Pending"
            attempt = Attempt.objects.create(payment=payment, provider=provider)
            payment.status = Payment.STATUS.PENDING
            payment.save(update_fields=["status", "funds_reserved", "updated"])

        try:
            create = provider.get_class().create
            result = async_to_sync(create)(payment) if iscoroutinefunction(create) else create(payment)
            if result["status"] not in [PaymentStatus.SUCCESS, PaymentStatus.FAILED, PaymentStatus.PENDING]:
                raise ValueError(f"Unsupported provider status: {result['status']}")

        except Exception:
            return logger.exception(f"{payment_id=} attempt {attempt.pk=} has an unknown outcome")

        if result["status"] == PaymentStatus.PENDING:
            return

        if finalize_attempt(payment_id, attempt.pk, result["status"]) is not False:
            return


def finalize_attempt(payment_id: str | UUID, attempt_id: str | UUID, status: PaymentStatus) -> bool | None:
    """Закрывает попытку по итоговому статусу провайдера и проводит деньги.

    Возвращает:
        True  - платёж успешно завершён;
        False - попытка закрыта как неуспешная, платёж можно отправлять следующему провайдеру;
        None  - ничего не изменено (платёж или попытка уже закрыты).
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        attempt = Attempt.objects.select_for_update().get(pk=attempt_id)
        if (
            payment.status not in [Payment.STATUS.PENDING, Payment.STATUS.TIMED_OUT]
            or attempt.status not in [Attempt.STATUS.PENDING, Attempt.STATUS.TIMED_OUT]
            or not payment.funds_reserved
        ):
            return None

        # Update attempt status
        if status == PaymentStatus.SUCCESS:
            attempt.status = Attempt.STATUS.SUCCEED
        else:
            attempt.status = Attempt.STATUS.FAILED
        attempt.save(update_fields=["status", "updated"])

        if status == PaymentStatus.SUCCESS:
            user = User.objects.select_for_update().get(pk=payment.user_id)
            user.balance -= payment.amount
            user.frozen_balance -= payment.amount
            user.save(update_fields=["balance", "frozen_balance"])
            payment.funds_reserved = False
            payment.status = Payment.STATUS.SUCCEED
            payment.save(update_fields=["status", "funds_reserved", "updated"])
            logger.info(f"{payment_id=} is finished with status")

            return True

        if payment.status == Payment.STATUS.TIMED_OUT:
            user = User.objects.select_for_update().get(pk=payment.user_id)
            user.frozen_balance -= payment.amount
            user.save(update_fields=["frozen_balance"])
            payment.funds_reserved = False
            payment.status = Payment.STATUS.FAILED
            payment.save(update_fields=["status", "funds_reserved", "updated"])

            return None

        return False


@shared_task(base=TracedTask, bind=True, ignore_result=True)
def deactivate_providers(self: Task) -> None:
    config: Config = Config.get_solo()
    since = timezone.now() - timedelta(hours=1)

    ids = (
        Attempt.objects.filter(status=Attempt.STATUS.FAILED, created__gte=since)
        .values("provider_id")
        .annotate(failed_count=Count("pk"))
        .filter(failed_count__gt=config.max_count_of_failed_attempts)
        .values("provider_id")
        .distinct()
    )
    updated = Provider.objects.filter(is_active=True, pk__in=ids).update(is_active=False)
    if updated:
        logger.warning(
            f"Deactivated {ids=} provider(s): more than {config.max_count_of_failed_attempts} failed attempts per hour"
        )


@shared_task(base=TracedTask, bind=True, ignore_result=True)
def mark_stale_attempts_as_timed_out(self: Task) -> None:
    config: Config = Config.get_solo()
    since = timezone.now() - timedelta(minutes=config.attempt_timeout_minutes)

    Attempt.objects.filter(status=Attempt.STATUS.PENDING, created__lt=since).update(status=Attempt.STATUS.TIMED_OUT)


@shared_task(base=TracedTask, bind=True, ignore_result=True)
def mark_stale_payments_as_timed_out(self: Task) -> None:
    config: Config = Config.get_solo()
    since = timezone.now() - timedelta(minutes=config.payment_timeout_minutes)
    statuses = [Payment.STATUS.CREATED, Payment.STATUS.PENDING]

    ids = Payment.objects.filter(status__in=statuses, created__lt=since).values_list("pk", flat=True)
    for payment_id in ids.iterator():
        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .filter(pk=payment_id, status__in=statuses, created__lt=since)
                .first()
            )
            if not payment:
                continue
            if payment.funds_reserved and not payment.attempts.exclude(status=Attempt.STATUS.FAILED).exists():
                user = User.objects.select_for_update().get(pk=payment.user_id)
                user.frozen_balance -= payment.amount
                user.save(update_fields=["frozen_balance"])
                payment.funds_reserved = False
            payment.status = Payment.STATUS.TIMED_OUT
            payment.save(update_fields=["status", "funds_reserved", "updated"])
