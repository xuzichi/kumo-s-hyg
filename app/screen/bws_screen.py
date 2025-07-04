"""
验证码测试屏幕 - 用于测试验证码过码功能
"""

import traceback
import time
import requests
from typing import Optional
import io

from noneprompt import (
    ListPrompt,
    Choice,
    CancelledError,
    InputPrompt,
    ConfirmPrompt
)

from ..utils.log import logger
from ..client import Client
from ..utils.file_utils import file_utils
from ..utils.push_manager import push_manager
from ..screen.push_screen import PushScreen

class BwsScreen:
    def __init__(self):
        self.client = Client()
        
    def run(self):
        while True:
            try:
                _ = ListPrompt(
                    "BWS功能:",
                    choices=[
                        Choice("S 查询项目", data="Search"),
                        Choice("! 开始预约", data="Book"),
                        Choice("← 返回", data="back"),
                    ],
                ).prompt()
            except CancelledError:
                break

            if _.data == "back":
                break
            elif _.data == "Search":
                self._bws_search()
            elif _.data == "Book":
                self._bws_book()
    def _bws_search():
        """
        进行BWS预约查询
        """
        self.client
        return

    def _bws_book():

        return