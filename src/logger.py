from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, ClassVar


class LoggerSingletonMeta(type):
    _instance: ClassVar[Logger]

    def __call__(cls, *args: Any, **kwargs: Any) -> Logger:
        if not hasattr(cls, "_instance"):
            LoggerSingletonMeta._instance = super().__call__(*args, **kwargs)
        return cls._instance


# pylint: disable=too-few-public-methods
class Logger(metaclass=LoggerSingletonMeta):
    def __init__(self) -> None:
        log_dir = Path(__file__).parent.joinpath("logs/")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir.joinpath("app.log")

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s|%(pathname)s:%(lineno)d|%(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Create a file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        # Create a console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)

        # Add handlers to the logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    @classmethod
    def get_logger(cls) -> logging.Logger:
        if cls._instance is None:
            cls()
        return cls._instance.logger
