#!/usr/bin/env python3
"""
虚拟设备配置管理模块 - 极简版
专注于抢票服务，支持多设备管理
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class VirtualDevice:
    """虚拟设备配置数据类"""
    device_id: str
    device_name: str
    model: str
    ios_version: str
    webkit_version: str
    canvas_fp: str
    webgl_fp: str
    audio_fp: str
    font_fp: str
    screen_fp: str
    resolution: str
    fe_sign: str
    created_time: int
    last_used: int


# 配置目录
CONFIG_DIR = Path("device_configs")
CONFIG_DIR.mkdir(exist_ok=True)


def get_current_device() -> Optional[VirtualDevice]:
    """获取当前使用的虚拟设备，不存在时自动创建"""
    # 查找默认设备标记文件
    default_files = list(CONFIG_DIR.glob("default_*.marker"))
    
    if default_files:
        # 解析默认设备ID
        default_file = default_files[0]  # 只应该有一个默认设备
        device_id = default_file.stem.replace("default_", "")
        
        # 加载设备配置
        device_file = CONFIG_DIR / f"{device_id}.json"
        if device_file.exists():
            try:
                with open(device_file, 'r', encoding='utf-8') as f:
                    device_data = json.load(f)
                
                # 更新最后使用时间
                device_data['last_used'] = int(time.time())
                device = VirtualDevice(**device_data)
                
                # 保存更新后的使用时间
                with open(device_file, 'w', encoding='utf-8') as f:
                    json.dump(asdict(device), f, indent=2, ensure_ascii=False)
                
                return device
            except Exception as e:
                logger.error(f"加载虚拟设备失败: {e}")
                # 删除损坏的标记文件
                default_file.unlink()
    
    # 没有默认设备，自动生成
    logger.debug("首次运行，自动生成虚拟设备...")
    return generate_virtual_device(set_as_default=True)


def generate_virtual_device(device_name: Optional[str] = None, set_as_default: bool = False) -> VirtualDevice:
    """生成新的虚拟设备配置"""
    from app.api import create_device_fingerprint_generator
    
    # 生成设备指纹
    fingerprint_generator = create_device_fingerprint_generator()
    device_info = fingerprint_generator()
    
    # 生成设备名称 - 格式：iPhone15_iOS18.1_KW9N
    if not device_name:
        device_name = f"{device_info['model']}_iOS{device_info['ios_version']}_{device_info['device_id'][:4]}"
    
    # 创建虚拟设备对象
    virtual_device = VirtualDevice(
        device_id=device_info['device_id'],
        device_name=device_name,
        model=device_info['model'],
        ios_version=device_info['ios_version'],
        webkit_version=device_info['webkit_version'],
        canvas_fp=device_info['canvas_fp'],
        webgl_fp=device_info['webgl_fp'],
        audio_fp=device_info['audio_fp'],
        font_fp=device_info['font_fp'],
        screen_fp=device_info['screen_fp'],
        resolution=device_info['resolution'],
        fe_sign=device_info['fe_sign'],
        created_time=int(time.time()),
        last_used=int(time.time())
    )
    
    # 保存设备配置文件
    device_file = CONFIG_DIR / f"{virtual_device.device_id}.json"
    with open(device_file, 'w', encoding='utf-8') as f:
        json.dump(asdict(virtual_device), f, indent=2, ensure_ascii=False)
    
    # 设置为默认设备
    if set_as_default:
        set_default_device(virtual_device.device_id)
    
    logger.debug(f"生成虚拟设备: {device_name} ({device_info['model']})")
    return virtual_device


def set_default_device(device_id: str) -> bool:
    """设置默认虚拟设备"""
    try:
        # 删除旧的默认设备标记
        for old_marker in CONFIG_DIR.glob("default_*.marker"):
            old_marker.unlink()
        
        # 创建新的默认设备标记文件
        marker_file = CONFIG_DIR / f"default_{device_id}.marker"
        marker_file.touch()
        
        logger.debug(f"设置默认设备: {device_id}")
        return True
        
    except Exception as e:
        logger.error(f"设置默认设备失败: {e}")
        return False


def list_devices() -> List[Dict]:
    """扫描文件夹获取所有虚拟设备列表"""
    devices = []
    try:
        # 扫描所有 .json 设备配置文件
        for device_file in CONFIG_DIR.glob("*.json"):
            try:
                with open(device_file, 'r', encoding='utf-8') as f:
                    device_data = json.load(f)
                
                devices.append({
                    'device_id': device_data['device_id'],
                    'device_name': device_data['device_name'],
                    'model': device_data['model'],
                    'ios_version': device_data['ios_version'],
                    'created_time': device_data['created_time'],
                    'last_used': device_data['last_used']
                })
            except Exception as e:
                logger.warning(f"读取设备文件失败 {device_file}: {e}")
                continue
        
        # 按最后使用时间排序
        devices.sort(key=lambda x: x['last_used'], reverse=True)
        return devices
        
    except Exception as e:
        logger.error(f"扫描设备列表失败: {e}")
        return []


def delete_device(device_id: str) -> bool:
    """删除虚拟设备"""
    try:
        # 删除设备配置文件
        device_file = CONFIG_DIR / f"{device_id}.json"
        if device_file.exists():
            device_file.unlink()
        
        # 删除默认设备标记（如果是默认设备）
        marker_file = CONFIG_DIR / f"default_{device_id}.marker"
        if marker_file.exists():
            marker_file.unlink()
        
        logger.debug(f"删除虚拟设备: {device_id}")
        return True
        
    except Exception as e:
        logger.error(f"删除虚拟设备失败: {e}")
        return False


def create_device_fingerprint_with_config() -> Dict:
    """基于配置文件创建设备指纹"""
    device = get_current_device()
    if not device:
        logger.error("未找到虚拟设备配置")
        return {}
    
    # 生成User-Agent
    ua = (f"Mozilla/5.0 (iPhone; CPU iPhone OS {device.ios_version.replace('.', '_')} like Mac OS X) "
          f"AppleWebKit/{device.webkit_version} (KHTML, like Gecko) Mobile/22F76 BiliApp/84800100 "
          f"os/ios model/{device.model} mobi_app/iphone build/84800100 osVer/{device.ios_version} "
          f"network/wifi channel/AppStore")
    
    return {
        'user_agent': ua,
        'device_id': device.device_id,
        'canvas_fp': device.canvas_fp,
        'webgl_fp': device.webgl_fp,
        'fe_sign': device.fe_sign,
        'brand': 'iPhone',
        'model': device.model,
        'ios_version': device.ios_version,
        'webkit_version': device.webkit_version,
        'audio_fp': device.audio_fp,
        'font_fp': device.font_fp,
        'screen_fp': device.screen_fp,
        'resolution': device.resolution
    }


 