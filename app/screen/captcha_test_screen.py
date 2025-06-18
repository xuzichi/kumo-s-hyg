"""
验证码测试屏幕 - 用于测试验证码过码功能
"""

import traceback
import time
import requests
from typing import Optional

from noneprompt import (
    ListPrompt,
    Choice,
    CancelledError,
    InputPrompt,
    ConfirmPrompt
)

from ..utils.log import logger
from ..client import Client


class CaptchaTestScreen:
    def __init__(self):
        self.client = Client()
        
    def run(self):
        """运行验证码测试界面"""
        while True:
            try:
                _ = ListPrompt(
                    "验证码过码测试:",
                    choices=[
                        Choice("A 自动测试 (使用bili_ticket_gt_python)", data="auto"),
                        Choice("M 手动测试 (已弃用)", data="manual"),
                        Choice("← 返回", data="back"),
                    ],
                ).prompt()
            except CancelledError:
                break

            if _.data == "back":
                break
            elif _.data == "auto":
                self._auto_test()
            elif _.data == "manual":
                self._manual_test()

    def _auto_test(self):
        """自动测试验证码过码"""
        logger.info("开始自动验证码测试...")
        
        # 检查是否有验证码处理器
        if not self.client.click:
            logger.error("bili_ticket_gt_python 未安装或初始化失败")
            logger.info("请安装依赖: pip install bili_ticket_gt_python")
            return
            
        try:
            # 获取测试用的GT和Challenge
            gt, challenge = self._get_geetest_params()
            if not gt or not challenge:
                logger.error("无法获取测试用的GT和Challenge参数")
                return
                
            logger.info(f"测试参数:")
            logger.info(f"GT: {gt}")
            logger.info(f"Challenge: {challenge}")
            
            # 开始自动过码
            logger.info("正在尝试自动过码...")
            start_time = time.time()
            
            try:
                validate = self.client.click.simple_match_retry(gt, challenge)
                end_time = time.time()
                
                if validate:
                    logger.success(f"自动过码成功!")
                    logger.success(f"耗时: {end_time - start_time:.2f}秒")
                    logger.success(f"Validate: {validate}")
                    
                else:
                    logger.error("❌ 自动过码失败 - 返回结果为空")
                    
            except Exception as e:
                end_time = time.time()
                logger.error(f"❌ 自动过码失败")
                logger.error(f"耗时: {end_time - start_time:.2f}秒")
                logger.error(f"错误: {e}")
                
        except Exception as e:
            logger.error(f"自动测试过程中发生异常: {e}")
            logger.debug(traceback.format_exc())

    def _manual_test(self):
        """手动测试验证码过码"""
        logger.info("开始手动验证码测试...")
        
        try:
            # 自动获取验证码参数
            logger.info("正在获取验证码参数...")
            gt, challenge = self._get_geetest_params()
            
            if not gt or not challenge:
                logger.error("无法获取验证码参数，请检查网络连接")
                return
                
            logger.info(f"GT: {gt}")
            logger.info(f"Challenge: {challenge}")
            logger.info("请打开以下网站进行手动验证:")
            logger.info("https://kuresaru.github.io/geetest-validator/")
                
        except CancelledError:
            logger.info("用户取消了手动测试")
        except Exception as e:
            logger.error(f"手动测试过程中发生异常: {e}")
            logger.debug(traceback.format_exc())

    def _get_geetest_params(self) -> tuple[Optional[str], Optional[str]]:
        """获取极验验证码的GT和Challenge参数"""
        try:
            session = requests.Session()
            resp = session.get(
                'https://passport.bilibili.com/x/passport-login/captcha?source=main_web',
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://passport.bilibili.com/login",
                },
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    captcha_data = data.get("data", {})
                    geetest_data = captcha_data.get("geetest", {})
                    return geetest_data.get("gt"), geetest_data.get("challenge")
                    
        except Exception as e:
            logger.debug(f"获取验证码参数失败: {e}")
            
        return None, None

            
            