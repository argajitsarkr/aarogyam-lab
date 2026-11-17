from celery import shared_task

from .services import generate_candidates


@shared_task
def generate_retest_candidates_task():
    return generate_candidates()
