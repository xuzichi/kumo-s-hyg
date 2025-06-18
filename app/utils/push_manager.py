import json
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional, Union

import requests

from app.utils.log import logger

PUSH_CONFIG_DIR = Path("push_config")
PUSH_CONFIG_DIR.mkdir(exist_ok=True)


@dataclass
class PushConfig:
    """推送配置基类"""

    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Unnamed"
    provider: str = "base"


@dataclass
class PushplusConfig(PushConfig):
    """Pushplus 配置"""

    token: str = ""
    provider: str = "pushplus"


@dataclass
class BarkConfig(PushConfig):
    """Bark 配置"""

    url: str = ""  # e.g., https://api.day.app/your_key
    provider: str = "bark"


PushConfigType = Union[PushplusConfig, BarkConfig]


class PushManager:
    """推送管理器"""

    def get_configs(self) -> List[PushConfigType]:
        """获取所有推送配置"""
        configs = []
        for f in PUSH_CONFIG_DIR.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    provider = data.get("provider")
                    if provider == "pushplus":
                        configs.append(PushplusConfig(**data))
                    elif provider == "bark":
                        configs.append(BarkConfig(**data))
            except Exception as e:
                logger.error(f"加载推送配置失败: {f.name}, {e}")
        return configs

    def save_config(self, config: PushConfigType) -> None:
        """保存推送配置"""
        # 使用 config_id 确保文件名唯一
        filename = f"{config.config_id}.json"
        filepath = PUSH_CONFIG_DIR / filename
        try:
            with open(filepath, "w", encoding="utf-8") as fp:
                json.dump(asdict(config), fp, ensure_ascii=False, indent=4)
            logger.success(f"推送配置已保存: {config.name}")
        except Exception as e:
            logger.error(f"保存推送配置失败: {config.name}, {e}")

    def delete_config(self, config_id: str) -> bool:
        """通过 ID 删除配置"""
        filepath = PUSH_CONFIG_DIR / f"{config_id}.json"
        if filepath.exists():
            try:
                filepath.unlink()
                logger.success(f"推送配置已删除: {config_id}")
                return True
            except Exception as e:
                logger.error(f"删除推送配置失败: {config_id}, {e}")
                return False
        logger.warning(f"未找到要删除的推送配置: {config_id}")
        return False

    def send(self, title: str, content: str, configs: Optional[List[PushConfigType]] = None):
        """发送通知到所有已配置的推送通道"""
        if configs is None:
            configs = self.get_configs()

        if not configs:
            logger.debug("没有可用的推送配置，跳过通知。")
            return

        for config in configs:
            try:
                if isinstance(config, PushplusConfig):
                    self._send_pushplus(config, title, content)
                elif isinstance(config, BarkConfig):
                    self._send_bark(config, title, content)
            except Exception as e:
                logger.error(f"发送通知到 {config.name} ({config.provider}) 失败: {e}")

    def _send_pushplus(self, config: PushplusConfig, title: str, content: str):
        """发送到 Pushplus"""
        if not config.token:
            return
        url = "http://www.pushplus.plus/send"
        payload = {"token": config.token, "title": title, "content": content, "template": "html"}
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()
        if result.get("code") == 200:
            logger.info(f"Pushplus 推送成功: {config.name}")
        else:
            logger.error(f"Pushplus 推送失败: {config.name}, {result.get('msg')}")

    def _send_bark(self, config: BarkConfig, title: str, content: str):
        """发送到 Bark"""
        if not config.url:
            return
        # Bark URL 格式: https://api.day.app/your_key/
        url = f"{config.url.rstrip('/')}/{requests.utils.quote(title)}/{requests.utils.quote(content)}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            logger.info(f"Bark 推送成功: {config.name}")
        else:
            logger.error(f"Bark 推送失败: {config.name}, {response.text}")

# 全局推送管理器实例
push_manager = PushManager() 