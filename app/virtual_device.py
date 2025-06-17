#!/usr/bin/env python3
from __future__ import annotations
"""
账号管理模块 - 管理用户账号和虚拟设备
"""

import json
import time
import hashlib
import random
from dataclasses import dataclass, asdict, field

# 新增依赖，用于拉取最新 B 站 iOS 版本
import requests

# 项目内部日志
from .log import logger


@dataclass
class VirtualDevice:
    """虚拟设备数据类"""
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
    user_agent: str
    bili_app_version: str = "8.48.0"  # 新增: BiliApp 版本号, 默认 8.48.0
    bili_app_build: str = "84800100"    # 新增: BiliApp build 码, 默认 84800100
    created_time: int = field(default_factory=lambda: int(time.time()))


@dataclass
class Account:
    """账号数据类"""
    user_id: str
    username: str
    cookie: str
    device: VirtualDevice
    created_time: int = field(default_factory=lambda: int(time.time()))
    last_login: int = field(default_factory=lambda: int(time.time()))


def create_virtual_device() -> VirtualDevice:
    """生成新的虚拟设备"""
    IPHONE_MODELS = [
        'iPhone10,3', 'iPhone10,6',  # iPhone X
        'iPhone11,2', 'iPhone11,4', 'iPhone11,6', 'iPhone11,8',  # iPhone XS/XS Max/XR
        'iPhone12,1', 'iPhone12,3', 'iPhone12,5', 'iPhone12,8',  # iPhone 11/11 Pro/11 Pro Max/SE 2nd
        'iPhone13,1', 'iPhone13,2', 'iPhone13,3', 'iPhone13,4',  # iPhone 12 mini/12/12 Pro/12 Pro Max
        'iPhone14,2', 'iPhone14,3', 'iPhone14,4', 'iPhone14,5', 'iPhone14,6', 'iPhone14,7', 'iPhone14,8',  # iPhone 13系列/SE 3rd/iPhone 14系列
        'iPhone15,2', 'iPhone15,3', 'iPhone15,4', 'iPhone15,5',  # iPhone 14 Pro/14 Pro Max/15/15 Plus
        'iPhone16,1', 'iPhone16,2',  # iPhone 15 Pro/15 Pro Max
        'iPhone17,1', 'iPhone17,2', 'iPhone17,3', 'iPhone17,4', 'iPhone17,5'   # iPhone 16系列/16e
    ]
    
    IOS_FONTS = [
        "PingFang SC", "Helvetica Neue", "Arial", "Times New Roman",
        "Courier New", "Verdana", "Georgia", "Trebuchet MS"
    ]
    
    IOS_GPU_INFO = [
        "Apple GPU", "Apple A15 Bionic GPU", "Apple A16 Bionic GPU", 
        "Apple A17 Pro GPU", "Apple M1 GPU"
    ]
    
    WEBGL_EXTENSIONS = [
        "WEBKIT_WEBGL_compressed_texture_s3tc", "WEBKIT_WEBGL_depth_texture",
        "OES_texture_float", "OES_texture_half_float", 
        "OES_standard_derivatives", "EXT_texture_filter_anisotropic"
    ]
    
    SCREEN_RESOLUTIONS = {
        'iPhone10,3': (1125, 2436),  # iPhone X
        'iPhone11,2': (1125, 2436),  # iPhone XS
        'iPhone12,1': (828, 1792),   # iPhone 11
        'iPhone13,2': (1170, 2532),  # iPhone 12
        'iPhone14,2': (1170, 2532),  # iPhone 13
        'iPhone15,2': (1179, 2556),  # iPhone 14 Pro
    }
    
    # 设备状态
    device_model = random.choice(IPHONE_MODELS)
    fingerprint_cache = {
        'device_id': None,
        'canvas_fp': None, 
        'webgl_fp': None
    }
    
    def generate_device_id():
        """生成设备ID指纹"""
        if fingerprint_cache['device_id']:
            return fingerprint_cache['device_id']
            
        # iOS版本和种子组件
        version = f"18.{random.randint(0,5)}.{random.randint(0,3)}"
        seed_components = [
            device_model,
            version.replace('.', ''),
            str(int(time.time() * 1000))[-8:],  # 时间戳后8位
            str(random.randint(100000, 999999))  # 随机因子
        ]
        
        # SHA256哈希生成16位大写十六进制
        seed_string = ''.join(seed_components)
        hash_obj = hashlib.sha256(seed_string.encode('utf-8'))
        fingerprint_cache['device_id'] = hash_obj.hexdigest()[:16].upper()
        return fingerprint_cache['device_id']

    def generate_canvas_fingerprint():
        """生成Canvas指纹"""
        if fingerprint_cache['canvas_fp']:
            return fingerprint_cache['canvas_fp']
            
        # Canvas绘制内容
        canvas_texts = [
            "BzqvpbVhJ9J8fCqFzq&'*bvJ4DsJBQ\"LVQ*qzKE",
            f"iPhone,{device_model}",
            "😊🍎🌟",
            "hello world 123",
        ]
        
        # 模拟字体渲染差异
        fonts = ["Arial", "Helvetica", "Times", "Courier"]
        canvas_data = ""
        for text in canvas_texts:
            for font in fonts:
                render_seed = f"{font}:{text}:{device_model}"
                canvas_data += hashlib.md5(render_seed.encode()).hexdigest()[:4]
        
        fingerprint_cache['canvas_fp'] = hashlib.sha256(canvas_data.encode()).hexdigest()[:32]
        return fingerprint_cache['canvas_fp']
    
    def generate_webgl_fingerprint():
        """生成WebGL指纹"""
        if fingerprint_cache['webgl_fp']:
            return fingerprint_cache['webgl_fp']
            
        # WebGL设备信息
        webgl_data = {
            "gpu": random.choice(IOS_GPU_INFO),
            "extensions": sorted(WEBGL_EXTENSIONS),
            "shader_precision": "mediump",
            "max_texture_size": 4096,
            "device_model": device_model
        }
        
        webgl_string = json.dumps(webgl_data, sort_keys=True)
        fingerprint_cache['webgl_fp'] = hashlib.sha256(webgl_string.encode()).hexdigest()[:32]
        return fingerprint_cache['webgl_fp']
    
    def generate_additional_fingerprints():
        """生成附加指纹 - 音频、字体、屏幕等"""
        # 音频指纹
        audio_fp = hashlib.md5(f"AudioContext:{device_model}:{time.time()}".encode()).hexdigest()[:16]
        
        # 字体指纹
        font_string = "|".join(sorted(IOS_FONTS))
        font_fp = hashlib.md5(font_string.encode()).hexdigest()[:16]
        
        # 屏幕指纹
        resolution = SCREEN_RESOLUTIONS.get(device_model, (1170, 2532))
        screen_fp = hashlib.md5(f"{resolution[0]}x{resolution[1]}:{device_model}".encode()).hexdigest()[:16]
        
        return {
            'audio_fp': audio_fp,
            'font_fp': font_fp,
            'screen_fp': screen_fp,
            'resolution': f"{resolution[0]}x{resolution[1]}"
        }
        
    def generate_version_info():
        """生成版本信息 - iOS和WebKit版本协调"""
        # iOS版本生成
        major_versions = [17, 18]
        major = random.choice(major_versions)
        minor = random.randint(0, 6) if major == 17 else random.randint(0, 2)
        patch = random.randint(0, 3)
        ios_version = f"{major}.{minor}.{patch}"
        
        # WebKit版本（与iOS版本相关）
        webkit_base = 605 if major == 17 else 618
        webkit_version = f"{webkit_base + random.randint(0, 15)}.1.{random.randint(10, 99)}"
        
        return ios_version, webkit_version
    
    # -----------------------------
    #  拉取 BiliApp 最新版本号 (iOS)
    # -----------------------------
    def fetch_latest_ios_biliapp_version() -> tuple[str, str]:
        """访问官方接口获取最新 iOS 端 BiliApp build 与版本号。

        Returns
        -------
        (build, version_name)
            build 如 "84800100"，version_name 如 "8.48.0"。
            若获取失败则返回默认值 ("84800100", "8.48.0")。
        """
        try:
            resp = requests.get(
                "https://app.bilibili.com/x/v2/version",
                params={"mobi_app": "iphone"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            resp.raise_for_status()
            data_json = resp.json()
            build = str(data_json["data"][0]["build"])
            version_name = str(data_json["data"][0]["version"])
            return build, version_name
        except Exception as e:
            logger.warning(f"获取最新 iOS 端 BiliApp 版本失败: {e}; 使用默认 8.48.0")
            return "84800100", "8.48.0"
    
    # 生成所有指纹信息
    ios_version, webkit_version = generate_version_info()
    additional_fps = generate_additional_fingerprints()
    device_id = generate_device_id()
    
    # 最新 BiliApp 版本
    bili_build, bili_version = fetch_latest_ios_biliapp_version()
    
    # 生成User-Agent，动态填入版本信息
    ua = (
        f"Mozilla/5.0 (iPhone; CPU iPhone OS {ios_version.replace('.', '_')} like Mac OS X) "
        f"AppleWebKit/{webkit_version} (KHTML, like Gecko) Mobile/22F76 "
        f"BiliApp/{bili_build} os/ios model/{device_model} mobi_app/iphone build/{bili_build} "
        f"osVer/{ios_version} network/wifi channel/AppStore"
    )
    
    # 生成设备名称 - 格式：iPhone15_iOS18.1_KW9N
    device_name = f"{device_model}_iOS{ios_version}_{device_id[:4]}"
    
    return VirtualDevice(
        device_id=device_id,
        device_name=device_name,
        model=device_model,
        ios_version=ios_version,
        webkit_version=webkit_version,
        canvas_fp=generate_canvas_fingerprint(),
        webgl_fp=generate_webgl_fingerprint(),
        audio_fp=additional_fps['audio_fp'],
        font_fp=additional_fps['font_fp'],
        screen_fp=additional_fps['screen_fp'],
        resolution=additional_fps['resolution'],
        fe_sign=hashlib.sha256(f"{device_model}:{ios_version}:{time.time()}".encode()).hexdigest()[:32],
        user_agent=ua,
        bili_app_version=bili_version,
        bili_app_build=bili_build
    )
