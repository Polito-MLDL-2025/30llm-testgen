import logging
import multiprocessing
import sys
import time
import queue as queue_module
from importlib.metadata import metadata

from llm30.pipeline.QAagent.utils.logging import setup_logger, ensure_stream_handler


class QAagentProcessHandler:
    def __init__(self, problem,
                 dataset,
                 model,
                 code_architect_prompt,
                 test_generator_prompt,
                 log_folder,
                 logger,
                 timeout_seconds=180,
                 max_attempts=3,
                 run_qaagent_function=None,
                 ):
        self.problem = problem
        self.dataset = dataset
        self.model = model
        self.code_architect_prompt = code_architect_prompt
        self.test_generator_prompt = test_generator_prompt
        self.log_folder = log_folder
        self.logger = logger
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        if run_qaagent_function is None:
            raise "run_qaagent_function must be provided"
        self.run_qaagent_function = run_qaagent_function

    def run(self, metadata=None):
        return self._run_qaagent_with_timeout(
            self.problem,
            self.dataset,
            self.model,
            self.code_architect_prompt,
            self.test_generator_prompt,
            self.log_folder,
            self.logger,
            self.timeout_seconds,
            self.max_attempts,
            metadata
        )

    def _qaagent_worker(
            self,
            result_queue,
            output_queue,
            problem,
            dataset,
            model,
            code_architect_prompt,
            test_generator_prompt,
            log_folder,
            metadata
    ):
        class QueueWriter:
            def __init__(self, queue):
                self.queue = queue

            def write(self, data):
                if data:
                    self.queue.put(data)

            def flush(self):
                return None

        sys.stdout = QueueWriter(output_queue)
        sys.stderr = QueueWriter(output_queue)

        logger = setup_logger(log_folder)
        ensure_stream_handler(logger)
        try:
            result = self.run_qaagent_function(
                problem,
                dataset,
                model,
                code_architect_prompt,
                test_generator_prompt,
                log_folder,
                logger,
                metadata
            )
            result_queue.put(("ok", result))
        except Exception as exc:
            logger.exception("Worker error for problem %s: %s", problem.get("task_id"), exc)
            result_queue.put(("error", str(exc)))

    def _run_qaagent_with_timeout(
            self,
            problem,
            dataset,
            model,
            code_architect_prompt,
            test_generator_prompt,
            log_folder,
            logger,
            timeout_seconds=180,
            max_attempts=3,
            metadata=None
    ):
        problem_id = problem.get("task_id")
        ctx = multiprocessing.get_context("spawn")
        for attempt in range(1, max_attempts + 1):
            result_queue = ctx.Queue()
            output_queue = ctx.Queue()
            process = ctx.Process(
                target=self._qaagent_worker,
                args=(
                    result_queue,
                    output_queue,
                    problem,
                    dataset,
                    model,
                    code_architect_prompt,
                    test_generator_prompt,
                    log_folder,
                    metadata
                ),
            )
            process.start()

            last_output = time.monotonic()
            while True:
                try:
                    chunk = output_queue.get(timeout=1)
                except queue_module.Empty:
                    chunk = None

                if chunk:
                    last_output = time.monotonic()
                    print(chunk, end="", flush=True)

                if not process.is_alive():
                    process.join()
                    while True:
                        try:
                            chunk = output_queue.get_nowait()
                        except queue_module.Empty:
                            break
                        if chunk:
                            print(chunk, end="", flush=True)
                    try:
                        status, payload = result_queue.get_nowait()
                    except queue_module.Empty:
                        logger.warning(
                            "Problem %s finished without result (attempt %s/%s). Retrying.",
                            problem_id,
                            attempt,
                            max_attempts,
                        )
                        break
                    if status == "ok":
                        return payload
                    logger.error(
                        "Problem %s failed (attempt %s/%s): %s",
                        problem_id,
                        attempt,
                        max_attempts,
                        payload,
                    )
                    break

                if time.monotonic() - last_output > timeout_seconds:
                    logger.warning(
                        "Problem %s had no output for %ss (attempt %s/%s). Restarting.",
                        problem_id,
                        timeout_seconds,
                        attempt,
                        max_attempts,
                    )
                    process.terminate()
                    process.join(timeout=10)
                    if process.is_alive():
                        process.kill()
                        process.join(timeout=5)
                    break

        logger.error("Problem %s failed after %s attempts.", problem_id, max_attempts)
        return None
