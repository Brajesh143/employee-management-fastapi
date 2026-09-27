import logging
import time

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger("agent")


class AgentLoggingCallback(BaseCallbackHandler):

    def __init__(self):
        self.started_at = {}

    def on_llm_start(
        self,
        serialized,
        prompts,
        run_id,
        **kwargs,
    ):
        self.started_at[str(run_id)] = time.perf_counter()

        logger.info(
            "LLM_STARTED | run_id=%s",
            run_id,
        )

    def on_llm_end(self, response, run_id, **kwargs):
        start = self.started_at.pop(str(run_id), None)

        duration = (
            time.perf_counter() - start
            if start is not None else None
        )

        logger.info(
            "LLM_COMPLETED | run_id=%s | duration=%.2fs",
            run_id,
            duration or 0,
        )

    def on_llm_error(self, error, run_id, **kwargs):
        self.started_at.pop(str(run_id), None)

        logger.exception(
            "LLM_ERROR | run_id=%s | error=%s",
            run_id,
            error,
        )

    def on_tool_start(
        self,
        serialized,
        input_str,
        run_id,
        **kwargs,
    ):
        self.started_at[str(run_id)] = time.perf_counter()

        tool_name = serialized.get("name", "unknown")

        logger.info(
            "TOOL_STARTED | tool=%s | run_id=%s",
            tool_name,
            run_id,
        )

    def on_tool_end(self, output, run_id, **kwargs):
        start = self.started_at.pop(str(run_id), None)

        duration = (
            time.perf_counter() - start
            if start is not None else None
        )

        logger.info(
            "TOOL_COMPLETED | run_id=%s | duration=%.2fs",
            run_id,
            duration or 0,
        )

    def on_tool_error(self, error, run_id, **kwargs):
        self.started_at.pop(str(run_id), None)

        logger.error(
            "TOOL_ERROR | run_id=%s | error=%s",
            run_id,
            error,
        )

    def on_chain_error(self, error, run_id, **kwargs):
        logger.error(
            "CHAIN_ERROR | run_id=%s | error=%s",
            run_id,
            error,
        )