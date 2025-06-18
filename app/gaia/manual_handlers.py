"""
手动验证码处理器 - 处理需要用户交互的验证码类型
"""
import time
import base64
import tempfile
import os
import io
import requests
from typing import Dict, Optional

from PIL import Image
import webbrowser

from ..utils.log import logger
from .base import BaseCaptchaHandler


class DirectHandler(BaseCaptchaHandler):
    """直接验证处理器"""
    
    def handle(self, token: str, register_data: Dict) -> bool:
        try:
            logger.info("执行直接验证")
            
            csrf = self.get_csrf()
            if not csrf:
                logger.error("无法获取CSRF令牌，直接验证失败")
                return False
            
            # 构造表单数据
            form_data = {
                "token": token
            }
            if csrf:
                form_data["csrf"] = csrf
                
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success("直接验证通过！")
                logger.debug(f"验证响应: {response.get('data', {}).get('msg', '无响应消息')}")
                return True
            else:
                logger.error(f"直接验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"直接验证异常: {str(e)}", exc_info=True)
            return False


class ImageHandler(BaseCaptchaHandler):
    """图片验证码处理器"""
    
    def handle(self, token: str, register_data: Dict) -> bool:
        """处理图片验证码"""
        try:
            logger.info("处理图片验证码...")
            
            # 提取验证码数据
            img_data = register_data.get("img", {})
            img_base64 = img_data.get("img", "")
            
            if not img_base64:
                logger.error("图片验证码数据不完整")
                return False
                
            # 保存验证码图片到临时文件
            try:
                img_data_binary = base64.b64decode(img_base64)
                
                # 创建临时文件
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                    temp_file.write(img_data_binary)
                    temp_file_path = temp_file.name
                    
                # 显示验证码图片
                logger.info(f"验证码图片已保存到: {temp_file_path}")
                
                # 尝试打开图片
                try:
                    img = Image.open(temp_file_path)
                    img.show()
                except Exception as e:
                    logger.warning(f"无法自动打开图片: {str(e)}")
                    # 尝试使用浏览器打开
                    try:
                        webbrowser.open(f"file://{temp_file_path}")
                    except Exception as e2:
                        logger.warning(f"无法使用浏览器打开图片: {str(e2)}")
                        logger.info(f"请手动打开图片文件: {temp_file_path}")
                
                # 等待用户输入验证码
                captcha_input = input("请输入图片验证码: ").strip()
                
                # 清理临时文件
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                
                if not captcha_input:
                    logger.error("验证码输入为空")
                    return False
                
                # 从cookie中提取bili_jct值
                csrf = self.get_csrf()
                if not csrf:
                    logger.error("无法获取CSRF令牌，图片验证码处理失败")
                    return False
                
                # 构造表单数据
                form_data = {
                    "token": token,
                    "img": captcha_input
                }
                if csrf:
                    form_data["csrf"] = csrf
                    
                # 使用requests直接调用，确保使用表单格式
                headers = self.api.headers.copy()
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                
                response = requests.post(
                    "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                    data=form_data,
                    headers=headers
                ).json()
                
                if response.get("code") == 0:
                    logger.success("图片验证码验证成功")
                    return True
                else:
                    logger.error(f"图片验证码验证失败: {response.get('message')} (错误码: {response.get('code')})")
                    return False
                    
            except Exception as e:
                logger.error(f"图片验证码处理异常: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"图片验证码处理异常: {str(e)}")
            return False


class SmsHandler(BaseCaptchaHandler):
    """短信验证码处理器"""
    
    def handle(self, token: str, register_data: Dict) -> bool:
        """处理短信验证码"""
        try:
            logger.info("处理短信验证码")
            
            # 从cookie中提取bili_jct值
            csrf = self.get_csrf()
            if not csrf:
                logger.error("无法获取CSRF令牌，短信验证码处理失败")
                return False
            
            # 1. 请求发送短信验证码
            form_data = {
                "token": token
            }
            if csrf:
                form_data["csrf"] = csrf
                
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/sms/send",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") != 0:
                logger.error(f"短信验证码发送失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
            logger.success("短信验证码已发送，请查收")
            
            # 2. 等待用户输入短信验证码
            sms_code = input("请输入收到的短信验证码: ").strip()
            
            if not sms_code:
                logger.error("短信验证码输入为空")
                return False
                
            # 3. 提交短信验证码
            form_data = {
                "token": token,
                "sms": sms_code
            }
            if csrf:
                form_data["csrf"] = csrf
                
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success("短信验证码验证成功")
                return True
            else:
                logger.error(f"短信验证码验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"短信验证码处理异常: {str(e)}")
            return False


class PhoneHandler(BaseCaptchaHandler):
    """手机号验证处理器"""
    
    def handle(self, token: str, register_data: Dict) -> bool:
        """处理手机号验证"""
        try:
            logger.info("处理手机号验证")
            
            # 提取验证码数据
            phone_data = register_data.get("phone", {})
            phone_masked = phone_data.get("phone", "")
            
            logger.info(f"需要验证的手机号: {phone_masked}")
            
            # 等待用户输入完整手机号
            phone_input = input("请输入完整的手机号: ").strip()
            
            if not phone_input:
                logger.error("手机号输入为空")
                return False
                
            # 从cookie中提取bili_jct值
            csrf = self.get_csrf()
            if not csrf:
                logger.error("无法获取CSRF令牌，手机号验证失败")
                return False
            
            # 构造表单数据
            form_data = {
                "token": token,
                "phone": phone_input
            }
            if csrf:
                form_data["csrf"] = csrf
                
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success("手机号验证成功")
                return True
            else:
                logger.error(f"手机号验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"手机号验证异常: {str(e)}")
            return False


class SmsOutgoingHandler(BaseCaptchaHandler):
    """短信外发验证码处理器"""
    
    def handle(self, token: str, register_data: Dict) -> bool:
        """处理短信外发验证码"""
        try:
            logger.info("处理短信外发验证码")
            
            # 提取验证码数据
            sms_mo_data = register_data.get("sms_mo", {})
            phone = sms_mo_data.get("phone", "")
            content = sms_mo_data.get("content", "")
            
            if not phone or not content:
                logger.error("短信外发验证码数据不完整")
                return False
                
            logger.info(f"请向号码 {phone} 发送短信，内容为: {content}")
            
            input("发送完成后按回车键继续...")
            
            # 从cookie中提取bili_jct值
            csrf = self.get_csrf()
            if not csrf:
                logger.error("无法获取CSRF令牌，短信外发验证码处理失败")
                return False
            
            # 构造表单数据
            form_data = {
                "token": token
            }
            if csrf:
                form_data["csrf"] = csrf
                
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success("短信外发验证码验证成功")
                return True
            else:
                logger.error(f"短信外发验证码验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"短信外发验证码处理异常: {str(e)}")
            return False


class BiliwordHandler(BaseCaptchaHandler):
    """B站词验证码处理器"""
    
    def handle(self, token: str, register_data: Dict) -> bool:
        """处理B站词验证码"""
        try:
            logger.info("处理B站词验证码")
            
            # 提取验证码数据
            biliword_data = register_data.get("biliword", {})
            word = biliword_data.get("word", "")
            
            if not word:
                logger.error("B站词验证码数据不完整")
                return False
                
            logger.info(f"B站词验证码: {word}")
            
            # 等待用户输入验证码
            word_input = input("请输入上面显示的B站词验证码: ").strip()
            
            if not word_input:
                logger.error("B站词验证码输入为空")
                return False
                
            # 从cookie中提取bili_jct值
            csrf = self.get_csrf()
            if not csrf:
                logger.error("无法获取CSRF令牌，B站词验证码处理失败")
                return False
            
            # 构造表单数据
            form_data = {
                "token": token,
                "biliword": word_input
            }
            if csrf:
                form_data["csrf"] = csrf
                
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success("B站词验证码验证成功")
                return True
            else:
                logger.error(f"B站词验证码验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"B站词验证码处理异常: {str(e)}")
            return False 