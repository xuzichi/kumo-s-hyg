
from noneprompt import CancelledError
from .log import logger
from app.screen import Main

from .api import Api
import json

try:
    Main().run()
except CancelledError:
    logger.info("program exit.")
except KeyboardInterrupt:
    logger.info("program exit.")
except Exception as e:
    logger.error(f"程序发生异常：{e}")
    
    
