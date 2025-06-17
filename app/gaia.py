import json
import base64
import time
import random
from typing import Optional, Dict, Any
from .log import logger
import requests


try:
    import bili_ticket_gt_python
    GEETEST_AVAILABLE = True
except ImportError:
    GEETEST_AVAILABLE = False
    logger.warning("bili_ticket_gt_python 库未安装，本地滑块验证将无法使用")


class GaiaHandler:
    """Gaia风控处理器 - 轻量级实现"""
    
    def __init__(self, api_instance):
        self.api = api_instance
        self.click = None
        self._click_initialized = False
    
    def _init_click_handler(self):
        """延迟初始化本地滑块处理器"""
        if self._click_initialized:
            return
        
        self._click_initialized = True
        if GEETEST_AVAILABLE:
            try:
                self.click = bili_ticket_gt_python.ClickPy()
            except Exception as e:
                self.click = None
        else:
            logger.warning("bili_ticket_gt_python 库未安装，本地滑块验证将无法使用")
            self.click = None
        
    def handle_gaia_validation(self, risk_params: Dict) -> bool:
        """处理Gaia验证码验证"""
        try:
            # 1. 注册验证码
            register_result = self._register_gaia(risk_params)
            if not register_result:
                return False
                
            token = register_result.get("token")
            captcha_type = register_result.get("type", "")
            
            # 2. 根据验证码类型处理
            match captcha_type:
                # 直接验证
                case "":
                    return self._validate_direct(token)
                # 本地滑块验证码
                case "geetest":
                    return self._handle_geetest(token, register_result)
                # 图片验证码
                case "img":
                    return self._handle_image_captcha(token)
                # 短信验证码
                case "sms":
                    return self._handle_sms_captcha(token)
                # 手机号验证
                case "phone":
                    return self._handle_phone_validation(token, register_result)
                # 不支持的验证码类型
                case _:
                    logger.warning(f"不支持的验证码类型: {captcha_type}")
                    return False

                
        except Exception as e:
            logger.error(f"验证码处理失败: {e}")
            return False
    
    def _register_gaia(self, risk_params: Dict) -> Optional[Dict]:
        """注册Gaia验证"""
        try:
            response = self.api._make_api_call(
                'POST',
                "https://api.bilibili.com/x/gaia-vgate/v1/register",
                self.api.headers,
                json_data=risk_params
            )
            
            if response.get("code") == 0:
                logger.debug("Gaia验证注册成功")
                return response.get("data", {})
            else:
                logger.error(f"Gaia验证注册失败: {response.get('message')}")
                return None
                
        except Exception as e:
            logger.error(f"Gaia验证注册异常: {e}")
            return None
    
    def _validate_direct(self, token: str) -> bool:
        """直接验证（无需额外操作）"""
        try:
            response = self.api._make_api_call(
                'POST',
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                self.api.headers,
                json_data={"token": token}
            )
            
            if response.get("code") == 0:
                logger.success("直接验证成功")
                return True
            else:
                logger.error(f"直接验证失败: {response.get('message')}")
                return False
                
        except Exception as e:
            logger.error(f"直接验证异常: {e}")
            return False
    
    def _handle_geetest(self, token: str, register_data: Dict) -> bool:
        """处理本地滑块验证码（使用bili_ticket_gt_python库）"""
        try:
            gt = register_data.get("geetest", {}).get("gt")
            challenge = register_data.get("geetest", {}).get("challenge")
            
            if not gt or not challenge:
                logger.error("本地滑块验证码参数不完整")
                return False
            
            logger.warning("检测到本地滑块验证码")
            logger.debug(f"GAIA GeeTest: {gt} {challenge}")
            
            # 延迟初始化滑块处理器
            self._init_click_handler()
            
            # 检查是否有滑块处理器
            if not self.click:
                logger.error("验证码系统未初始化，无法处理本地滑块")
                return False
            
            logger.info("正在运行本地滑块自动解决器...")
            
            # 使用bili_ticket_gt_python库自动处理滑块
            validate = self.click.simple_match_retry(gt, challenge)
            seccode = f"{validate}|jordan"
            
            logger.debug(f"GAIA Validate: {validate}")
            logger.debug(f"GAIA Seccode: {seccode}")
            
            # 获取csrf token
            csrf = None
            if hasattr(self.api, 'headers') and self.api.headers.get('Cookie'):
                cookie_str = self.api.headers['Cookie']
                if 'bili_jct=' in cookie_str:
                    csrf_start = cookie_str.find('bili_jct=') + 9
                    csrf_end = cookie_str.find(';', csrf_start)
                    csrf = cookie_str[csrf_start:csrf_end] if csrf_end != -1 else cookie_str[csrf_start:]
            
            response = self.api._make_api_call(
                'POST',
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                self.api.headers,
                json_data={
                    "token": token,
                    "csrf": csrf,
                    "challenge": challenge,
                    "validate": validate,
                    "seccode": seccode
                }
            )
            
            if response.get("code") == 0:
                logger.success("本地滑块验证通过！")
                logger.debug(f"GAIA Validate: {response['data']['msg']}")
                return True
            else:
                logger.error(f"验证码提交失败: {response.get('message')}")
                return False
                
        except Exception as e:
            logger.error(f"本地滑块处理异常: {e}")
            return False
    
    def _handle_image_captcha(self, token: str) -> bool:
        """处理图片验证码"""
        return False
    
    def _handle_sms_captcha(self, token: str) -> bool:
        """处理短信验证码"""
        return False
    
    def _handle_phone_validation(self, token: str, register_data: Dict) -> bool:
        """处理手机号验证"""
        return False
    

