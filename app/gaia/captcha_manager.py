"""
Gaia验证码管理器 - 负责协调不同的验证码处理器
"""
import json
import os
import time
from typing import Dict, Optional, Any, Type

import requests
from ..utils.log import logger

from .base import BaseCaptchaHandler
from .auto_handlers import GeetestHandler, ClickHandler
from .manual_handlers import (
    DirectHandler, ImageHandler, SmsHandler, 
    PhoneHandler, SmsOutgoingHandler, BiliwordHandler
)


class GaiaCaptchaManager:
    """Gaia风控验证码管理器 - 负责协调不同的验证码处理器"""
    
    def __init__(self, api_instance):
        """
        初始化验证码管理器
        
        Args:
            api_instance: API客户端实例，用于发送请求
        """
        self.api = api_instance
        self.max_retry_count = 3  # 最大重试次数
        
        # 初始化处理器映射
        self._handlers = {}
        self._init_handlers()
    
    def _init_handlers(self):
        """初始化所有验证码处理器"""
        # 自动处理器 - 常见的验证码类型
        self._handlers["geetest"] = GeetestHandler(self.api)
        self._handlers["click"] = ClickHandler(self.api)
        
        # 手动处理器 - 不常见的验证码类型
        self._handlers[""] = DirectHandler(self.api)  # 空类型，直接验证
        self._handlers["img"] = ImageHandler(self.api)
        self._handlers["sms"] = SmsHandler(self.api)
        self._handlers["phone"] = PhoneHandler(self.api)
        self._handlers["sms_mo"] = SmsOutgoingHandler(self.api)
        self._handlers["biliword"] = BiliwordHandler(self.api)
    
    def handle_validation(self, risk_params: Dict) -> bool:
        """
        处理Gaia验证码验证
        
        Args:
            risk_params: 风控参数，包含v_voucher等信息
            
        Returns:
            bool: 验证是否成功
        """
        try:
            # 1. 注册验证码
            register_result = self._register_gaia(risk_params)
            if not register_result:
                return False
                
            token = register_result.get("token")
            captcha_type = register_result.get("type", "")
            
            logger.info(f"收到验证码类型: {captcha_type}")
            
            # 2. 根据验证码类型处理
            return self._handle_with_retry(captcha_type, token, register_result)
        except Exception as e:
            logger.error(f"验证码处理失败: {str(e)}", exc_info=True)
            return False
    
    def _handle_with_retry(self, captcha_type: str, token: str, register_data: Dict) -> bool:
        """
        带重试的验证码处理
        
        Args:
            captcha_type: 验证码类型
            token: 验证码token
            register_data: 注册验证码时返回的数据
            
        Returns:
            bool: 验证是否成功
        """
        # 获取对应的处理器
        handler = self._handlers.get(captcha_type)
        if not handler:
            logger.warning(f"不支持的验证码类型: {captcha_type}")
            return False
        
        # 尝试处理验证码，最多重试max_retry_count次
        retry_count = 0
        while retry_count < self.max_retry_count:
            try:
                logger.info(f"尝试处理{captcha_type}验证码 (尝试 {retry_count + 1}/{self.max_retry_count})")
                result = handler.handle(token, register_data)
                if result:
                    return True
            except Exception as e:
                logger.error(f"验证码处理异常: {str(e)}", exc_info=True)
            
            retry_count += 1
            if retry_count < self.max_retry_count:
                logger.info(f"验证码处理失败，将在1秒后重试...")
                time.sleep(1)
        
        logger.error(f"验证码处理失败，已达到最大重试次数 ({self.max_retry_count})")
        return False
    
    def _register_gaia(self, risk_params: Dict) -> Optional[Dict]:
        """
        注册Gaia验证
        
        Args:
            risk_params: 风控参数，包含v_voucher等信息
            
        Returns:
            Optional[Dict]: 注册结果，如果失败则返回None
        """
        try:
            logger.info("开始注册Gaia验证")
            
            # 从risk_params中提取v_voucher值
            v_voucher = None
            if isinstance(risk_params, dict):
                if "v_voucher" in risk_params:
                    v_voucher = risk_params["v_voucher"]
                else:
                    # 尝试从嵌套字典中提取
                    for k, v in risk_params.items():
                        if isinstance(v, dict) and "v_voucher" in v:
                            v_voucher = v["v_voucher"]
                            break
            
            if not v_voucher and isinstance(risk_params, str):
                # 可能直接传入了v_voucher字符串
                v_voucher = risk_params
                
            if not v_voucher:
                logger.error("无法从风控参数中提取v_voucher值")
                return None
            
            # 从cookie中提取bili_jct值
            csrf = None
            if hasattr(self.api, 'headers') and self.api.headers.get('Cookie'):
                cookie_str = self.api.headers['Cookie']
                if 'bili_jct=' in cookie_str:
                    csrf_start = cookie_str.find('bili_jct=') + 9
                    csrf_end = cookie_str.find(';', csrf_start)
                    csrf = cookie_str[csrf_start:csrf_end] if csrf_end != -1 else cookie_str[csrf_start:]
            
            # 构造表单数据
            form_data = {
                "v_voucher": v_voucher
            }
            if csrf:
                form_data["csrf"] = csrf
                
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            logger.debug(f"注册Gaia验证: v_voucher={v_voucher[:20]}...")
            
            # 使用表单格式而不是JSON
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/register",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success("Gaia验证注册成功")
                return response.get("data", {})
            else:
                logger.error(f"Gaia验证注册失败: {response.get('message')} (错误码: {response.get('code')})")
                return None
                
        except Exception as e:
            logger.error(f"Gaia验证注册异常: {str(e)}", exc_info=True)
            return None 