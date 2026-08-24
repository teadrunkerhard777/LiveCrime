import fcntl
import tempfile
from contextlib import contextmanager
from pathlib import Path


class AlreadyRunningError(RuntimeError):
    """Сообщает, что другой процесс LiveCrime уже выполняется."""


@contextmanager
def single_instance_lock():
    """Не позволяет двум процессам публиковать одну выборку одновременно."""

    # Блокировка лежит во временной системной папке и не попадает в Git.
    lock_path = Path(tempfile.gettempdir()) / "livecrime-autoposter.lock"
    lock_file = lock_path.open("a+", encoding="utf-8")

    try:
        # Неблокирующий режим сразу обнаруживает уже активный процесс.
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        lock_file.close()
        raise AlreadyRunningError from error

    try:
        yield
    finally:
        # ОС также освободит lock при аварийном завершении процесса.
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
