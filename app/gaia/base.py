"""
验证码处理器基础类和接口定义
"""
from typing import Dict, Optional, Any
import os
import shutil
from ..utils.log import logger


class BaseCaptchaHandler:
    """验证码处理器基类"""
    
    def __init__(self, api_instance):
        """
        初始化验证码处理器
        
        Args:
            api_instance: API客户端实例，用于发送请求
        """
        self.api = api_instance
    
    def handle(self, token: str, register_data: Dict) -> bool:
        """
        处理验证码的通用接口
        
        Args:
            token: 验证码token
            register_data: 注册验证码时返回的数据
            
        Returns:
            bool: 验证是否成功
        """
        raise NotImplementedError("子类必须实现handle方法")
    
    def get_csrf(self) -> Optional[str]:
        """
        从cookie中提取bili_jct值
        
        Returns:
            str: CSRF令牌，如果不存在则返回None
        """
        csrf = None
        if hasattr(self.api, 'headers') and self.api.headers.get('Cookie'):
            cookie_str = self.api.headers['Cookie']
            if 'bili_jct=' in cookie_str:
                csrf_start = cookie_str.find('bili_jct=') + 9
                csrf_end = cookie_str.find(';', csrf_start)
                csrf = cookie_str[csrf_start:csrf_end] if csrf_end != -1 else cookie_str[csrf_start:]
        return csrf 