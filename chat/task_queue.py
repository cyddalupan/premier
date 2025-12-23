import queue
import threading
import logging
from django.db import close_old_connections

# Get an instance of a logger
logger = logging.getLogger('task_queue')

# The queue where tasks will be stored
task_queue = queue.Queue()

def worker():
    """
    The worker function that runs in a separate thread.
    It continuously gets tasks from the queue and executes them.
    """
    while True:
        # Get a task from the queue. `block=True` means it will wait until a task is available.
        func, args, kwargs = task_queue.get()
        try:
            # Ensure database connections are fresh for this thread
            close_old_connections()
            
            # Execute the function
            logger.info(f"Executing enqueued task: {func.__name__} with args: {args}, kwargs: {kwargs}")
            func(*args, **kwargs)
            logger.info(f"Successfully executed enqueued task: {func.__name__}")
        except Exception as e:
            # Log any exceptions that occur during task execution
            logger.error(f"Error executing enqueued task {func.__name__} with args {args}, kwargs {kwargs}: {e}", exc_info=True)
        finally:
            # Signal that the task is complete, even if it failed
            task_queue.task_done()

# Start the worker thread when the module is imported
# `daemon=True` ensures the thread will exit when the main program exits
worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()
logger.info("Task queue worker thread started.")

def enqueue_task(func, *args, **kwargs):
    """
    Adds a function and its arguments to the task queue for asynchronous execution.
    """
    task_queue.put((func, args, kwargs))
