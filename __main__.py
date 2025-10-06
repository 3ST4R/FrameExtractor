import os, argparse, sys, io, contextlib
from loguru import logger

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt6.QtWidgets import QApplication
from FrameExtractor import __appname__
from FrameExtractor import __version__
from FrameExtractor.app import MainWindow
from FrameExtractor.utils import newIcon

class _LoggerIO(io.StringIO):
    def write(self, message: str) -> int:
        if stripped_message := message.strip():
            logger.debug(stripped_message)
        return len(message)

    def flush(self) -> None:
        pass

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    @property
    def closed(self) -> bool:
        return False

def _setup_loguru(logger_level: str) -> None:
    try:
        logger.remove(handler_id=0)
    except ValueError:
        pass

    if sys.stderr:
        logger.add(sys.stderr, level=logger_level)

    log_file = "frame_extractor.log"
    logger.add(
        log_file,
        colorize=False,
        level="DEBUG",
        rotation="10 MB",
        retention="1 year",
        compression="gz",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", "-V", action="store_true", help="show version")
    parser.add_argument(
        "--logger-level",
        default="debug",
        choices=["debug", "info", "warning", "fatal", "error"],
        help="logger level",
    )
    args = parser.parse_args()

    if args.version:
        print(f"{__appname__} {__version__}")
        sys.exit(0)
        
    _setup_loguru(logger_level=args.logger_level.upper())
    logger.info(f"Starting {__appname__} {__version__}")
    
    app = QApplication(sys.argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("icon"))
    
    window = MainWindow()
    
    with contextlib.redirect_stderr(new_target=_LoggerIO()):
        window.show()
        window.raise_()
        sys.exit(app.exec())
        
if __name__ == "__main__":
    main()