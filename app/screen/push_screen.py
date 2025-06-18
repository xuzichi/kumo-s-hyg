from ..utils.log import logger
from noneprompt import (
    ListPrompt,
    Choice,
    CancelledError,
    InputPrompt,
)

from app.utils.push_manager import push_manager, PushplusConfig, BarkConfig


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
                    self.show_config_menu(action.data)

            except (CancelledError, KeyboardInterrupt):
                break

    def show_config_menu(self, config):
        action = ListPrompt(
            f"操作配置: 【{config.provider.capitalize()}】{config.name}",
            choices=[
                Choice("删除此配置", data="delete"),
                Choice("← 返回", data="back"),
            ],
        ).prompt()

        if action.data == "delete":
            self.manager.delete_config(config.config_id)

    def create_new_config(self):
        provider_action = ListPrompt(
            "请选择推送服务提供商:",
            choices=[
                Choice("Pushplus (微信推送)", data="pushplus"),
                Choice("Bark (iOS 推送)", data="bark"),
                Choice("← 返回", data="back"),
            ],
        ).prompt()

        provider = provider_action.data
        if provider == "back":
            return

        # 为新配置生成一个默认名称，如 "Bark", "Bark 2"
        all_configs = self.manager.get_configs()
        existing_names = {c.name for c in all_configs}
        base_name = provider.capitalize()
        default_name = base_name
        counter = 2
        while default_name in existing_names:
            default_name = f"{base_name} {counter}"
            counter += 1

        name = InputPrompt("请输入配置名称:", default_text=default_name).prompt() or default_name

        if provider == "pushplus":
            logger.warning("Pushplus 推送服务好像要实名认证懒得搞了, 有人测试好给我 pr 一下得了")
            return
            # while True:
            #     token = InputPrompt("请输入 Pushplus 的 Token:").prompt()
            #     if not token:
            #         print("Token 不能为空，请重新输入")
            #         continue
            #     break
            # config = PushplusConfig(name=name, token=token)
        elif provider == "bark":
            while True:
                url = InputPrompt("请输入 Bark 的 URL (例如: https://api.day.app/your_key):").prompt()
                if not url:
                    logger.warning("URL 不能为空，请重新输入")
                    continue
                # 自动清理 Bark URL 中的示例推送内容
                placeholder = "这里改成你自己的推送内容"
                if placeholder in url:
                    url = url.split(placeholder)[0].rstrip("/")
                break
            config = BarkConfig(name=name, url=url)
        else:
            return

        self.manager.save_config(config) 