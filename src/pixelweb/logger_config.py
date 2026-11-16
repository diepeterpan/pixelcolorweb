import os
import logging

class EndpointFilter(logging.Filter):
    """Filter out high-frequency polling/preview endpoints from uvicorn.access logs."""
    def __init__(self, filter_paths: list[str] = None):
        super().__init__()
        self.filter_paths = filter_paths or [
            "/api/status",
            "/api/text-message/preview"
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        # If any of the filtered paths are in the access log and request succeeded (200), silence it
        if any(f'"{method} {path}' in msg or f'{path} HTTP' in msg for path in self.filter_paths for method in ("GET", "POST")):
            if " 200 OK" in msg or " 304 Not Modified" in msg:
                return False
        return True

def setup_logging():
    # Support both LOG_LEVEL (DEBUG, INFO, WARNING, ERROR) and legacy DEBUG=1
    log_level_env = os.getenv("LOG_LEVEL", "").strip().upper()
    debug_mode = os.getenv("DEBUG", "").lower() in ("1", "true", "yes", "on")

    if log_level_env in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        root_level = getattr(logging, log_level_env)
        is_debug = root_level == logging.DEBUG
    elif debug_mode:
        root_level = logging.DEBUG
        is_debug = True
    else:
        root_level = logging.INFO
        is_debug = False

    logging.basicConfig(
        level=root_level,
        format="%(levelname)s:%(name)s:%(message)s"
    )

    if is_debug:
        logging.getLogger("pypixelcolor").setLevel(logging.DEBUG)
        logging.getLogger("pypixelcolor.commands.send_image").setLevel(logging.DEBUG)
        logging.getLogger("pypixelcolor.client").setLevel(logging.DEBUG)
        logging.getLogger("pypixelcolor.lib.transport").setLevel(logging.DEBUG)
        logging.getLogger("uvicorn.access").setLevel(logging.DEBUG)
        logging.getLogger("BLEWorker").setLevel(logging.DEBUG)
        logging.getLogger("Scheduler").setLevel(logging.DEBUG)
        logging.getLogger("TextMessageRenderer").setLevel(logging.DEBUG)
    else:
        # Silence routine pypixelcolor transport messages (e.g. 'Sending X KB', 'Command executed successfully')
        logging.getLogger("pypixelcolor").setLevel(logging.WARNING)
        logging.getLogger("pypixelcolor.commands.send_image").setLevel(logging.WARNING)
        logging.getLogger("pypixelcolor.client").setLevel(logging.WARNING)
        logging.getLogger("pypixelcolor.lib.transport").setLevel(logging.WARNING)

        # Apply endpoint filter to uvicorn.access so preview and status polling are silent
        access_logger = logging.getLogger("uvicorn.access")
        access_logger.addFilter(EndpointFilter())
