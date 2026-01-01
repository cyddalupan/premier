from django_q.tasks import async_task
import logging

logger = logging.getLogger('task_queue')

def enqueue_task(func, *args, **kwargs):
    """
    Adds a function and its arguments to the Django Q task queue for asynchronous execution.
    """
    logger.info(f"Enqueuing task: {func.__name__} with args: {args}, kwargs: {kwargs}")
    async_task(func, *args, **kwargs)