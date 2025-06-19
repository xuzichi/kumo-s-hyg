from ..utils.log import logger
import re
from noneprompt import (
    ListPrompt,
    Choice,
    CancelledError,
    InputPrompt,
)

from app.utils.push_manager import push_manager, BarkConfig, NtfyConfig


class PushScreen:
    def __init__(self):
        self.manager = push_manager

    def run(self):
        while True:
            configs = self.manager.get_configs()
            choices = [Choice(f"【{c.provider.capitalize()}】{c.name}", data=c) for c in configs]
            choices.append(Choice("+ 新建配置", data="new"))
            choices.append(Choice("← 返回", data="back"))

            try:
                action = ListPrompt("请选择要操作的推送配置:", choices=choices).prompt()

                if action.data == "new":
                    self.create_new_config()
                elif action.data == "back":
                    break
                else:
                    # 操作已有配置
                    self.manage_config(action.data)
            except CancelledError:
                break

    def create_new_config(self):
        """创建新的推送配置"""
        try:
            provider_choices = [
                Choice("Bark", data="bark"),
                Choice("Ntfy", data="ntfy"),
                Choice("← 返回", data="back"),
            ]
            provider = ListPrompt("请选择推送服务:", choices=provider_choices).prompt()

            if provider.data == "back":
                return

            # 公共字段
            name = InputPrompt("请输入配置名称:", default_text=provider.data).prompt()

            if provider.data == "bark":
                url = InputPrompt("请输入 Bark URL (例如: https://api.day.app/your_key):").prompt()
                config = BarkConfig(name=name, url=url)
                self.manager.add_config(config)
                logger.success("Bark 配置已添加")
            elif provider.data == "ntfy":
                server_url = InputPrompt(
                    "请输入完整的 Ntfy URL (例如: https://ntfy.sh/yourtopic):"
                ).prompt()
                config = NtfyConfig(name=name, server_url=server_url)
                self.manager.add_config(config)
                logger.success("Ntfy 配置已添加")

        except CancelledError:
            pass

    def manage_config(self, config):
        """管理已有的推送配置"""
        while True:
            try:
                choices = [
                    Choice("I 编辑", data="edit"),
                    Choice("D 删除", data="delete"),
                    Choice("← 返回", data="back"),
                ]
                action = ListPrompt(f"管理推送配置 '{config.name}':", choices=choices).prompt()

                if action.data == "edit":
                    self.edit_config(config)
                elif action.data == "delete":
                    self.delete_config(config)
                    break  # 删除后返回上一级
                elif action.data == "back":
                    break
            except CancelledError:
                break

    def edit_config(self, config):
        """编辑推送配置"""
        try:
            new_name = InputPrompt("请输入新的配置名称:", default=config.name).prompt()
            
            if isinstance(config, BarkConfig):
                new_url = InputPrompt(
                    "请输入新的 Bark URL:", default=config.url
                ).prompt()
                config.name = new_name
                config.url = new_url
                self.manager.update_config(config)
                logger.success("Bark 配置已更新")
            elif isinstance(config, NtfyConfig):
                new_server_url = InputPrompt(
                    "请输入新的完整 Ntfy URL:", default=config.server_url
                ).prompt()
                config.name = new_name
                config.server_url = new_server_url
                self.manager.update_config(config)
                logger.success("Ntfy 配置已更新")
        except CancelledError:
            pass

    def delete_config(self, config):
        """删除推送配置"""
        try:
            confirm_choices = [
                Choice("确认删除", data="confirm"),
                Choice("取消", data="cancel"),
            ]
            confirm = ListPrompt(
                f"确认要删除推送配置 '{config.name}' 吗?", choices=confirm_choices
            ).prompt()
            if confirm.data == "confirm":
                self.manager.delete_config(config.config_id)
                logger.success(f"推送配置 '{config.name}' 已删除")
        except CancelledError:
            pass
