"""
主页 - 程序的主要入口界面
"""

import traceback
import time
import yaml
from pathlib import Path
import re

from noneprompt import (
    ListPrompt,
    Choice,
    CancelledError,
    InputPrompt,
)

from app.logic import Logic
from app.order import Order
from ..utils.log import logger
from ..client import Client
from .config_builder import ConfigBuilder
from app.utils import account_manager
from .config_executor import ConfigExecutor
from .push_screen import PushScreen
from .captcha_test_screen import CaptchaTestScreen
# from .captcha_screen import CaptchaScreen  # 已删除


class Main:
    def __init__(self):
        self.cookie: str = None
        self.api = Client()
        self.template_config = None  # 用于存储模板配置
        if not Path("config").exists():            
            Path("config").mkdir(parents=True, exist_ok=True)
        self.config_executor = ConfigExecutor(self.api)
            
    def run(self):
        while True:
            # 读取所有配置文件并按修改时间排序
            config_files = list(Path("config").glob("*.yml"))
            config_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 构建选择列表
            choices = []
            
            if config_files:
                for config_file in config_files:
                    try:
                        choices.append(Choice(config_file.stem, data=config_file))
                    except Exception:
                        choices.append(Choice(f"{config_file.stem} (配置文件损坏)", data=config_file))
            else:
                choices.append(Choice("暂无配置文件，请先生成配置", data="no_config"))
            
            choices.append(Choice("+ 新建配置", data="new"))
            choices.append(Choice("! 推送管理", data="push"))
            choices.append(Choice("# 过码测试", data="captcha_test"))
            choices.append(Choice("← 退出", data="exit"))
            
            _ = ListPrompt(
                "请选择操作:",
                choices=choices
            ).prompt()
            
            try:
                if _.data == "new":
                    self.build_config()
                elif _.data == "push":
                    PushScreen().run()
                elif _.data == "captcha_test":
                    CaptchaTestScreen().run()
                elif _.data == "exit":
                    break
                elif isinstance(_.data, Path):
                    self.config_executor.show_config_menu(_.data)
            except CancelledError:
                continue
            except KeyboardInterrupt:
                continue
            except Exception as e:
                logger.error(f'发生错误: {e}')
                logger.debug(f'发生错误: \n{traceback.format_exc()}')

    def build_config(self, existing_config_path=None):
        """构建新的配置文件或编辑现有配置文件"""
        builder = ConfigBuilder()
        builder.build_config(existing_config_path)
