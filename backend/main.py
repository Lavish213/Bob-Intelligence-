from __future__ import annotations
from loguru import logger
from backend.worker.loop import run_loop

if __name__ == "__main__":
    logger.info("bob_intelligence starting")
    run_loop()
