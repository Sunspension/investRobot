import logging
import sys


class LoggerFactory:
    @staticmethod
    def create_logger(name: str, level=logging.INFO):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')

        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
