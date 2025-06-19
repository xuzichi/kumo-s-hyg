import json
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional, Union, Dict

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
class BarkConfig(PushConfig):
    """Bark 配置"""
    url: str = ""  # e.g., https://api.day.app/your_key
    provider: str = "bark"


@dataclass
class NtfyConfig(PushConfig):
    """Ntfy 配置"""
    server_url: str = ""  # 完整URL，例如：https://ntfy.sh/yourtopic
    provider: str = "ntfy"


PushConfigType = Union[BarkConfig, NtfyConfig]


class PushManager:
    """推送管理器"""

    def __init__(self):
        self.configs: List[PushConfigType] = []
        self._load_configs()

    def _load_configs(self):
        """加载所有配置"""
        self.configs = []
        for config_file in PUSH_CONFIG_DIR.glob("*.json"):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    provider = data.get("provider", "")
                    if provider == "bark":
                        self.configs.append(BarkConfig(**data))
                    elif provider == "ntfy":
                        self.configs.append(NtfyConfig(**data))
            except Exception as e:
                logger.error(f"加载配置失败: {config_file} {e}")

    def get_configs(self) -> List[PushConfigType]:
        """获取所有配置"""
        return self.configs

    def get_config(self, config_id: str) -> Optional[PushConfigType]:
        """根据ID获取配置"""
        for config in self.configs:
            if config.config_id == config_id:
                return config
        return None

    def add_config(self, config: PushConfigType) -> bool:
        """添加配置"""
        try:
            self.configs.append(config)
            config_file = PUSH_CONFIG_DIR / f"{config.config_id}.json"
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(asdict(config), f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"添加配置失败: {e}")
            return False

    def update_config(self, config: PushConfigType) -> bool:
        """更新配置"""
        try:
            for i, c in enumerate(self.configs):
                if c.config_id == config.config_id:
                    self.configs[i] = config
                    config_file = PUSH_CONFIG_DIR / f"{config.config_id}.json"
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(asdict(config), f, ensure_ascii=False, indent=4)
                    return True
            return False
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False

    def delete_config(self, config_id: str) -> bool:
        """删除配置"""
        try:
            for i, c in enumerate(self.configs):
                if c.config_id == config_id:
                    self.configs.pop(i)
                    config_file = PUSH_CONFIG_DIR / f"{config_id}.json"
                    config_file.unlink(missing_ok=True)
                    return True
            return False
        except Exception as e:
            logger.error(f"删除配置失败: {e}")
            return False

    def push(self, title: str, content: str, config_id: Optional[str] = None) -> Dict[str, Dict]:
        """推送消息
        
        Args:
            title: 标题
            content: 内容
            config_id: 配置ID，为None则推送到所有配置
            
        Returns:
            Dict: 包含推送结果的字典，格式为 {config_name: {"success": bool, "message": str}}
        """
        results = {}
        
        if config_id:
            # 推送到指定配置
            config = self.get_config(config_id)
            if config:
                results[config.name] = self._send_push(config, title, content)
        else:
            # 推送到所有配置
            for config in self.configs:
                results[config.name] = self._send_push(config, title, content)
                
        return results
    
    def _send_push(self, config: PushConfigType, title: str, content: str) -> Dict:
        """发送推送"""
        try:
            # Bark推送
            if config.provider == "bark":
                if not config.url:
                    return {"success": False, "message": "Bark URL为空"}
                
                url = config.url.rstrip("/") + "/"
                params = {"title": title, "body": content, "sound": "default"}
                response = requests.post(url, params=params, timeout=10)
                
                if response.status_code != 200:
                    return {"success": False, "message": f"HTTP错误: {response.status_code}"}
                return {"success": True, "message": response.text}
                
            # Ntfy推送
            elif config.provider == "ntfy":
                if not config.server_url:
                    return {"success": False, "message": "Ntfy服务器URL为空"}

                # 使用 GET + 查询参数发布消息，避免非 ASCII 头字段导致的编码错误
                publish_url = config.server_url.rstrip("/") + "/publish"
                params = {
                    "message": content,
                    "title": title,
                }
                response = requests.get(publish_url, params=params, timeout=10)

                if response.status_code not in (200, 201, 202, 204):
                    return {"success": False, "message": f"HTTP错误: {response.status_code}"}
                return {"success": True, "message": response.text}
                
            # 其他类型
            else:
                return {"success": False, "message": f"不支持的推送服务: {config.provider}"}
                
        except Exception as e:
            logger.error(f"推送到 {config.name} ({config.provider}) 失败: {e}")
            return {"success": False, "message": str(e)}


push_manager = PushManager() 