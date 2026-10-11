from __future__ import annotations
import argparse
import signal
from threading import Event
from loguru import logger
from backend.config import settings, validate_settings
from backend.worker.loop import run_loop, run_once


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    validate_settings(settings())
    if args.once:
        result = run_once()
        return 1 if result['errors'] else 0
    stopped = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    logger.info('bob_intelligence starting')
    run_loop(stopped)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
