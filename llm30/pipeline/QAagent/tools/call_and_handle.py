import os
import time
import logging
import threading
import random
from contextlib import contextmanager

try:
    import fcntl
except ImportError:  # pragma: no cover - non-posix fallback
    fcntl = None

try:
    import httpx
except ImportError:
    httpx = None

try:
    from openai import OpenAI, APITimeoutError
except ImportError:  # pragma: no cover - older openai versions
    from openai import OpenAI
    APITimeoutError = None
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

client = OpenAI(base_url=os.getenv("OPENAI_URL_BASE"), api_key=os.getenv("OPENAI_API_KEY"))

CALL_POOL_SIZE_ENV = "OPENAI_MAX_CONCURRENT_REQUESTS"
CALL_POOL_DIR_ENV = "OPENAI_CALL_POOL_DIR"
CALL_POOL_WAIT_SECONDS_ENV = "OPENAI_CALL_POOL_WAIT_SECONDS"

DEFAULT_CALL_POOL_SIZE = 4
DEFAULT_CALL_POOL_DIR = "/tmp/llm30_openai_call_pool"
DEFAULT_CALL_POOL_WAIT_SECONDS = 0.5

_call_pool_config_lock = threading.Lock()
_call_pool_size = None
_call_pool_dir = None
_call_pool_wait_seconds = None

_thread_pool_lock = threading.Lock()
_thread_pool_size = None
_thread_pool = None


def _read_positive_int_env(env_name: str, default: int) -> int:
    raw_value = os.getenv(env_name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        parsed_value = int(raw_value)
        if parsed_value <= 0:
            raise ValueError
        return parsed_value
    except ValueError:
        logger.warning(
            "Invalid value for %s=%r. Using default %s.",
            env_name,
            raw_value,
            default,
        )
        return default


def _read_positive_float_env(env_name: str, default: float) -> float:
    raw_value = os.getenv(env_name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        parsed_value = float(raw_value)
        if parsed_value <= 0:
            raise ValueError
        return parsed_value
    except ValueError:
        logger.warning(
            "Invalid value for %s=%r. Using default %.2f.",
            env_name,
            raw_value,
            default,
        )
        return default


def _get_call_pool_config():
    global _call_pool_size, _call_pool_dir, _call_pool_wait_seconds
    if _call_pool_size is not None:
        return _call_pool_size, _call_pool_dir, _call_pool_wait_seconds

    with _call_pool_config_lock:
        if _call_pool_size is None:
            _call_pool_size = _read_positive_int_env(CALL_POOL_SIZE_ENV, DEFAULT_CALL_POOL_SIZE)
            _call_pool_dir = os.getenv(CALL_POOL_DIR_ENV, DEFAULT_CALL_POOL_DIR)
            _call_pool_wait_seconds = _read_positive_float_env(
                CALL_POOL_WAIT_SECONDS_ENV,
                DEFAULT_CALL_POOL_WAIT_SECONDS,
            )
            logger.info(
                "OpenAI call pool configured: size=%s, dir=%s, wait=%.2fs",
                _call_pool_size,
                _call_pool_dir,
                _call_pool_wait_seconds,
            )

    return _call_pool_size, _call_pool_dir, _call_pool_wait_seconds


def _get_thread_pool(pool_size: int):
    global _thread_pool, _thread_pool_size
    with _thread_pool_lock:
        if _thread_pool is None or _thread_pool_size != pool_size:
            _thread_pool = threading.BoundedSemaphore(pool_size)
            _thread_pool_size = pool_size
    return _thread_pool


@contextmanager
def _acquire_thread_slot(pool_size: int):
    thread_pool = _get_thread_pool(pool_size)
    thread_pool.acquire()
    try:
        yield
    finally:
        thread_pool.release()


def _try_lock_slot(slot_path: str):
    slot_file = open(slot_path, "a+")
    try:
        fcntl.flock(slot_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return slot_file
    except BlockingIOError:
        slot_file.close()
        return None


@contextmanager
def _acquire_call_slot():
    pool_size, pool_dir, wait_seconds = _get_call_pool_config()

    if fcntl is None:
        with _acquire_thread_slot(pool_size):
            yield
        return

    try:
        os.makedirs(pool_dir, exist_ok=True)
    except OSError as exc:
        logger.warning(
            "Could not create call pool directory %s (%s). Falling back to in-process pool.",
            pool_dir,
            exc,
        )
        with _acquire_thread_slot(pool_size):
            yield
        return

    slot_file = None
    waiting_logged = False

    while slot_file is None:
        for slot_index in range(pool_size):
            slot_path = os.path.join(pool_dir, f"slot_{slot_index}.lock")
            slot_file = _try_lock_slot(slot_path)
            if slot_file is not None:
                logger.info("Acquired API call slot %s/%s", slot_index + 1, pool_size)
                break

        if slot_file is None:
            if not waiting_logged:
                # logger.info(
                #     "All API call slots are busy (size=%s). Waiting for a free slot.",
                #     pool_size,
                # )
                print(f"All API call slots are busy (pool_size={pool_size}). Waiting for a free slot.",)
                waiting_logged = True
            time.sleep(wait_seconds)

    try:
        yield
    finally:
        fcntl.flock(slot_file.fileno(), fcntl.LOCK_UN)
        slot_file.close()


def _is_timeout_error(exc: Exception) -> bool:
    if APITimeoutError and isinstance(exc, APITimeoutError):
        return True
    if httpx is not None and isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, TimeoutError):
        return True
    message = str(exc).lower()
    return "timed out" in message or "timeout" in message


def call_and_handle(messages, model, temperature=0, top_p=1.0, timeout=180):
    """
    Call the OpenAI API and handle the response.

    Args:
        messages: List of message dictionaries
        model: The model to use for generation
        temperature: Sampling temperature (default: 0)
        top_p: Nucleus sampling parameter (default: 1.0)
        timeout: Request timeout in seconds (default: 180)

    Returns:
        tuple: (completion, input_token_count, output_token_count)

    Raises:
        OpenAI API exceptions on failure
    """
    logger.debug("Calling model: %s", model)

    completion = None
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            pre_call_delay = random.uniform(0.1, 1.5)
            # logger.info("Sleeping %.3fs before API call (attempt %s/%s).", pre_call_delay, attempt, max_attempts)
            print("Sleeping {:.3f}s before API call (attempt {}/{}).".format(pre_call_delay, attempt, max_attempts))
            time.sleep(pre_call_delay)
            with _acquire_call_slot():
                completion = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    timeout=timeout*attempt,
                    top_p=top_p,
                )
            break
        except Exception as exc:
            if _is_timeout_error(exc) and attempt < max_attempts:
                logger.warning(
                    "Request timed out (attempt %s/%s). Retrying in 60 seconds.",
                    attempt,
                    max_attempts,
                )
                time.sleep(60)
                continue
            raise

    if completion is None:
        raise RuntimeError("OpenAI completion failed after retries.")

    input_token_count = completion.usage.prompt_tokens
    output_token_count = completion.usage.completion_tokens

    logger.debug(
        "API call successful. Tokens - Input: %s, Output: %s, Total: %s",
        input_token_count,
        output_token_count,
        completion.usage.total_tokens,
    )

    response_preview = (completion.choices[0].message.content or "")[:100]
    logger.debug("Response preview: %s...", response_preview)

    return completion, input_token_count, output_token_count
