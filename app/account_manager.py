#!/usr/bin/env python3
from __future__ import annotations
"""
账号管理模块 - 管理用户账号和虚拟设备
"""

import json
import time
import hashlib
import random
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, asdict, field
import traceback
import re
import string
from app.virtual_device import VirtualDevice, Account

# 避免运行时循环依赖，仅在类型检查时导入 Api
if TYPE_CHECKING:
    from app.client import Client

# 使用统一的日志封装
from .log import logger
from noneprompt import (
    ListPrompt,
    Choice,
    InputPrompt,
    CancelledError,
)


# 账号配置目录
ACCOUNT_DIR = Path("account")
ACCOUNT_DIR.mkdir(parents=True, exist_ok=True)


def create_account(api: Client) -> Optional[Account]:
    """创建新账号"""
    try:
        # 创建临时API客户端检查cookie有效性并获取用户信息

        user_info = api.my_info()
        
        if user_info.get("code") != 0:
            logger.error(f"创建账号失败: Cookie无效")
            return None
        
        # 从用户信息中提取用户ID和用户名
        user_data = user_info.get("data", {})
        user_id = str(user_data.get("profile", {}).get("mid", ""))
        username = user_data.get("profile", {}).get("name", "未知用户")
        
        if not user_id:
            logger.error("创建账号失败: 无法获取用户ID")
            return None
        
        # 生成虚拟设备
        device = api.device
        
        # 创建账号
        account = Account(
            user_id=user_id,
            username=username,
            cookie=api.cookie,
            device=device,
        )
        
        # 保存账号
        save_account(account)
        logger.info(
            f"创建账号成功: {username} (ID: {user_id}) | 虚拟设备: {device.device_name}")
        
        return account
    except Exception as e:
        logger.error(f"创建账号失败: {str(e)}")
        logger.debug(traceback.format_exc())
        return None


def _find_account_file_by_user_id(user_id: str) -> Optional[Path]:
    """遍历目录查找包含指定 *user_id* 的账户文件"""
    uid = str(user_id)
    for file in ACCOUNT_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if str(data.get("user_id")) == uid:
                return file
        except Exception:
            continue
    # 如果遍历完仍未找到，返回 None
    return None

def save_account(account: Account) -> bool:
    """保存账号到文件。如果已存在则覆盖，否则使用新命名规则保存。"""
    try:
        target_path = _find_account_file_by_user_id(str(account.user_id))
        def _sanitize_for_filename(text: str) -> str:
            """将文件名中不安全的字符替换为下划线"""
            return re.sub(r"[^A-Za-z0-9_\-]", "_", text)[:32] or "unknown"
        if target_path is None:
            # 构造新的文件名：用户名_设备名_随机ID.json
            safe_username = _sanitize_for_filename(account.username)
            safe_devname = _sanitize_for_filename(account.device.device_name)
            short_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            filename = f"{safe_username}_{safe_devname}_{short_id}.json"
            target_path = ACCOUNT_DIR / filename
        
        # 转换为字典
        account_dict = asdict(account)
        
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(account_dict, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"保存账号: {account.username} (ID: {account.user_id}) -> {target_path.name}")
        return True
    except Exception as e:
        logger.error(f"保存账号失败: {str(e)}")
        logger.debug(traceback.format_exc())
        return False

def get_account(user_id: str) -> Optional[Account]:
    """根据用户ID加载账号"""
    try:
        account_file = _find_account_file_by_user_id(str(user_id))
        if account_file is None:
            logger.warning(f"账号不存在: {user_id}")
            return None
        with open(account_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        device = VirtualDevice(**data.pop("device"))
        return Account(**data, device=device)
    except Exception as e:
        logger.error(f"加载账号失败: {str(e)}")
        logger.debug(traceback.format_exc())
        return None

def list_accounts() -> List[Dict]:
    """列出所有账号"""
    accounts = []
    try:
        # 扫描所有 .json 账号文件
        for account_file in ACCOUNT_DIR.glob("*.json"):
            try:
                with open(account_file, 'r', encoding='utf-8') as f:
                    account_data = json.load(f)
                
                # 提取简要信息
                accounts.append({
                    'user_id': account_data['user_id'],
                    'username': account_data['username'],
                    'created_time': account_data['created_time'],
                    'last_login': account_data['last_login'],
                    'device_name': account_data.get('device', {}).get('device_name', '')
                })
            except Exception as e:
                logger.warning(f"读取账号文件失败 {account_file}: {e}")
                continue
        
        # 按最后登录时间排序
        accounts.sort(key=lambda x: x['last_login'], reverse=True)
        return accounts
        
    except Exception as e:
        logger.error(f"扫描账号列表失败: {e}")
        return []

def delete_account(user_id: str) -> bool:
    """删除账号"""
    try:
        account_file = _find_account_file_by_user_id(str(user_id))
        if account_file and account_file.exists():
            account_file.unlink()
        logger.info(f"删除账号成功: {user_id}")
        return True
        logger.warning(f"账号不存在: {user_id}")
        return False
    except Exception as e:
        logger.error(f"删除账号失败: {str(e)}")
        return False
