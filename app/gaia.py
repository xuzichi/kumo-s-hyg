"""
Gaia风控处理模块 - 主入口
"""
from .gaia.captcha_manager import GaiaCaptchaManager, check_models_directory

# 导出GaiaCaptchaManager类和check_models_directory函数
__all__ = ["GaiaCaptchaManager", "check_models_directory"]

import json
import base64
import time
import random
import re
import os
import shutil
from typing import Optional, Dict, Any, Tuple

from .utils.log import logger
import requests


try:
    import bili_ticket_gt_python
    GEETEST_AVAILABLE = True
except ImportError:
    GEETEST_AVAILABLE = False
    logger.warning("bili_ticket_gt_python 库未安装，本地滑块验证将无法使用")


# 检查项目根目录的models文件夹
def check_models_directory():
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))
    # 检查models文件夹是否存在
    if not os.path.exists(models_dir):
        logger.warning(f"模型目录不存在, 正在下载模型文件")
        gaia_handler = GaiaCaptchaManager(None)
        # 初始化验证码处理器
        gaia_handler._init_click_handler()
        gaia_handler._init_slide_handler()
    

class GaiaCaptchaManager:
    """Gaia风控处理器 - 轻量级实现"""
    
    def __init__(self, api_instance):
        self.api = api_instance
        self.click = None
        self.slide = None
        self._click_initialized = False
        self._slide_initialized = False
        self.max_retry_count = 3  # 最大重试次数
        self.models_loaded = False
        self.models_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))
    
    def _init_click_handler(self):
        """延迟初始化本地点选处理器"""
        if self._click_initialized:
            return
        
        self._click_initialized = True
        if GEETEST_AVAILABLE:
            try:
                self.click = bili_ticket_gt_python.ClickPy()
                logger.success("点选验证码处理器初始化成功")
            except Exception as e:
                logger.error(f"点选验证码处理器初始化失败: {str(e)}", exc_info=True)
                self.click = None
        else:
            logger.warning("bili_ticket_gt_python 库未安装，本地点选验证将无法使用")
            self.click = None
            
    def _init_slide_handler(self):
        """延迟初始化本地滑块处理器"""
        if self._slide_initialized:
            return
        
        self._slide_initialized = True
        if GEETEST_AVAILABLE:
            try:
                self.slide = bili_ticket_gt_python.SlidePy()
                logger.success("滑块验证码处理器初始化成功")
            except Exception as e:
                logger.error(f"滑块验证码处理器初始化失败: {str(e)}", exc_info=True)
                self.slide = None
        else:
            logger.warning("bili_ticket_gt_python 库未安装，本地滑块验证将无法使用")
            self.slide = None
    
        
    def handle_gaia_validation(self, risk_params: Dict) -> bool:
        """处理Gaia验证码验证"""
        try:
            # 1. 注册验证码
            register_result = self._register_gaia(risk_params)
            if not register_result:
                return False
                
            token = register_result.get("token")
            captcha_type = register_result.get("type", "")
            
            logger.info(f"收到验证码类型: {captcha_type}")
            
            # 2. 根据验证码类型处理
            match captcha_type:
                # 直接验证
                case "":
                    return self._validate_direct(token)
                # 本地滑块验证码
                case "geetest":
                    return self._handle_geetest_with_retry(token, register_result)
                # 图片验证码
                case "img":
                    return self._handle_image_captcha_with_retry(token, register_result)
                # 短信验证码
                case "sms":
                    return self._handle_sms_captcha(token)
                # 手机号验证
                case "phone":
                    return self._handle_phone_validation(token, register_result)
                # 短信外发验证码
                case "sms_mo":
                    return self._handle_sms_mo_validation(token, register_result)
                # B站词验证码
                case "biliword":
                    return self._handle_biliword(token, register_result)
                # 不支持的验证码类型
                case _:
                    logger.warning(f"不支持的验证码类型: {captcha_type}")
                    return False
        except Exception as e:
            logger.error(f"验证码处理失败: {str(e)}", exc_info=True)
            return False
    
    def _register_gaia(self, risk_params: Dict) -> Optional[Dict]:
        """注册Gaia验证"""
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
    
    def _validate_direct(self, token: str) -> bool:
        """直接验证（无需额外操作）"""
        try:
            logger.info("执行直接验证")
            
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
                logger.success("直接验证成功")
                return True
            else:
                logger.error(f"直接验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"直接验证异常: {str(e)}", exc_info=True)
            return False

    def _refresh_challenge(self, gt: str, challenge: str) -> str:
        """刷新challenge，处理验证码过期情况"""
        try:
            logger.info("尝试刷新验证码challenge")
            url = "http://api.geevisit.com/refresh.php"
            params = {"gt": gt, "challenge": challenge, "callback": f"geetest_{int(time.time()*1000)}"}
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            # 解析回调格式的响应
            match = re.match(r"geetest_\d+\((.*)\)", response.text)
            if match is None:
                logger.error("刷新challenge失败: 响应格式不正确")
                return challenge
                
            res_json = json.loads(match.group(1))
            if res_json.get("status") == "success":
                new_challenge = res_json.get("data", {}).get("challenge")
                if new_challenge:
                    logger.success(f"成功刷新challenge: {new_challenge[:10]}...")
                    return new_challenge
            
            logger.warning(f"刷新challenge失败, 继续使用原challenge: {challenge[:10]}...")
            return challenge
        except Exception as e:
            logger.error(f"刷新challenge异常: {str(e)}", exc_info=True)
            return challenge
    
    def _handle_geetest_with_retry(self, token: str, register_data: Dict) -> bool:
        """处理滑块验证码，包含重试机制"""
        for retry in range(self.max_retry_count):
            try:
                logger.info(f"处理滑块验证码 (尝试 {retry+1}/{self.max_retry_count})")
                if self._handle_geetest(token, register_data):
                    return True
                
                # 如果失败，刷新challenge后重试
                gt = register_data.get("geetest", {}).get("gt")
                challenge = register_data.get("geetest", {}).get("challenge")
                if gt and challenge:
                    register_data["geetest"]["challenge"] = self._refresh_challenge(gt, challenge)
                
            except Exception as e:
                logger.error(f"滑块验证码处理失败 (尝试 {retry+1}/{self.max_retry_count}): {str(e)}", exc_info=True)
                # 添加短暂延迟后重试
                # time.sleep(1)
        
        logger.error(f"滑块验证码处理失败，已达到最大重试次数 {self.max_retry_count}")
        return False
        
    def _handle_image_captcha_with_retry(self, token: str, register_data: Dict) -> bool:
        """处理图片验证码，包含重试机制"""
        for retry in range(self.max_retry_count):
            try:
                logger.info(f"处理图片点选验证码 (尝试 {retry+1}/{self.max_retry_count})")
                if self._handle_image_captcha(token, register_data):
                    return True
                
                # 如果失败，刷新challenge后重试
                gt = register_data.get("geetest", {}).get("gt")
                challenge = register_data.get("geetest", {}).get("challenge")
                if gt and challenge:
                    register_data["geetest"]["challenge"] = self._refresh_challenge(gt, challenge)
                
            except Exception as e:
                logger.error(f"图片验证码处理失败 (尝试 {retry+1}/{self.max_retry_count}): {str(e)}", exc_info=True)
                # 添加短暂延迟后重试
                # time.sleep(1)
        
        logger.error(f"图片验证码处理失败，已达到最大重试次数 {self.max_retry_count}")
        return False
    
    def _handle_geetest(self, token: str, register_data: Dict) -> bool:
        """处理本地滑块验证码（使用bili_ticket_gt_python库）"""
        start_time = time.time()
        try:
            gt = register_data.get("geetest", {}).get("gt")
            challenge = register_data.get("geetest", {}).get("challenge")
            
            if not gt or not challenge:
                logger.error("本地滑块验证码参数不完整")
                return False
            
            logger.warning(f"检测到滑块验证码: GT={gt[:10]}..., Challenge={challenge[:10]}...")
            
            # 获取验证码类型
            try:
                # 延迟初始化滑块处理器
                self._init_slide_handler()
                
                # 检查是否有滑块处理器
                if not self.slide:
                    logger.error("验证码系统未初始化，无法处理滑块验证码")
                    return False
                
                # 获取验证码类型
                _type = self.slide.get_type(gt, challenge)
                logger.info(f"验证码实际类型: {_type}")
                
                if _type != "slide":
                    logger.warning(f"预期的滑块验证码，但检测到类型为: {_type}")
                    # 如果实际是点选验证码，调用点选处理逻辑
                    if _type == "click":
                        self._init_click_handler()
                        if not self.click:
                            logger.error("验证码系统未初始化，无法处理点选验证码")
                            return False
                        return self._handle_click_captcha(token, register_data)
            except Exception as e:
                logger.warning(f"验证码类型识别失败，将继续尝试滑块验证: {str(e)}")
            
            logger.info("正在运行滑块验证码自动解决器...")
            
            # 使用bili_ticket_gt_python库自动处理滑块
            validate = self.slide.simple_match_retry(gt, challenge)
            seccode = f"{validate}|jordan"
            
            logger.debug(f"生成的验证数据: validate={validate[:10]}...")
            
            # 获取csrf token
            csrf = None
            if hasattr(self.api, 'headers') and self.api.headers.get('Cookie'):
                cookie_str = self.api.headers['Cookie']
                if 'bili_jct=' in cookie_str:
                    csrf_start = cookie_str.find('bili_jct=') + 9
                    csrf_end = cookie_str.find(';', csrf_start)
                    csrf = cookie_str[csrf_start:csrf_end] if csrf_end != -1 else cookie_str[csrf_start:]
            
            # # 计算处理耗时
            # processing_time = time.time() - start_time
            # # 如果处理时间太短，适当增加延迟使验证更真实
            # if processing_time < 2:
            #     logger.debug(f"验证处理时间较短({processing_time:.2f}秒)，添加延迟使其更加真实")
            #     time.sleep(2 - processing_time)
                
            logger.info(f"提交滑块验证结果 (处理耗时: {time.time() - start_time:.2f}秒)")
            
            # 构造表单数据
            form_data = {
                "token": token,
                "challenge": challenge,
                "validate": validate,
                "seccode": seccode
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
                logger.success(f"滑块验证通过！(总耗时: {time.time() - start_time:.2f}秒)")
                logger.debug(f"验证响应: {response.get('data', {}).get('msg', '无响应消息')}")
                return True
            else:
                logger.error(f"验证码提交失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"滑块验证码处理异常 (耗时: {time.time() - start_time:.2f}秒): {str(e)}", exc_info=True)
            return False
            
    def _handle_click_captcha(self, token: str, register_data: Dict) -> bool:
        """处理本地点选验证码（使用bili_ticket_gt_python库）"""
        start_time = time.time()
        try:
            gt = register_data.get("geetest", {}).get("gt")
            challenge = register_data.get("geetest", {}).get("challenge")
            
            if not gt or not challenge:
                logger.error("本地点选验证码参数不完整")
                return False
            
            logger.warning(f"检测到点选验证码: GT={gt[:10]}..., Challenge={challenge[:10]}...")
            
            # 延迟初始化点选处理器
            self._init_click_handler()
            
            # 检查是否有点选处理器
            if not self.click:
                logger.error("验证码系统未初始化，无法处理点选验证码")
                return False
            
            logger.info("正在运行点选验证码自动解决器...")
            
            # 使用bili_ticket_gt_python库自动处理点选
            validate = self.click.simple_match_retry(gt, challenge)
            seccode = f"{validate}|jordan"
            
            logger.debug(f"生成的验证数据: validate={validate[:10]}...")
            
            # 获取csrf token
            csrf = None
            if hasattr(self.api, 'headers') and self.api.headers.get('Cookie'):
                cookie_str = self.api.headers['Cookie']
                if 'bili_jct=' in cookie_str:
                    csrf_start = cookie_str.find('bili_jct=') + 9
                    csrf_end = cookie_str.find(';', csrf_start)
                    csrf = cookie_str[csrf_start:csrf_end] if csrf_end != -1 else cookie_str[csrf_start:]
            
            # # 计算处理耗时
            # processing_time = time.time() - start_time
            # # 如果处理时间太短，适当增加延迟使验证更真实
            # if processing_time < 2:
            #     logger.debug(f"验证处理时间较短({processing_time:.2f}秒)，添加延迟使其更加真实")
            #     time.sleep(2 - processing_time)
                
            logger.info(f"提交点选验证结果 (处理耗时: {time.time() - start_time:.2f}秒)")
            
            # 构造表单数据
            form_data = {
                "token": token,
                "challenge": challenge,
                "validate": validate,
                "seccode": seccode
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
                logger.success(f"点选验证通过！(总耗时: {time.time() - start_time:.2f}秒)")
                logger.debug(f"验证响应: {response.get('data', {}).get('msg', '无响应消息')}")
                return True
            else:
                logger.error(f"验证码提交失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"点选验证码处理异常 (耗时: {time.time() - start_time:.2f}秒): {str(e)}", exc_info=True)
            return False
    
    def _handle_image_captcha(self, token: str, register_data: Dict) -> bool:
        """处理图片验证码"""
        try:
            logger.info("处理图片验证码...")
            
            # 获取csrf token
            csrf = None
            if hasattr(self.api, 'headers') and self.api.headers.get('Cookie'):
                cookie_str = self.api.headers['Cookie']
                if 'bili_jct=' in cookie_str:
                    csrf_start = cookie_str.find('bili_jct=') + 9
                    csrf_end = cookie_str.find(';', csrf_start)
                    csrf = cookie_str[csrf_start:csrf_end] if csrf_end != -1 else cookie_str[csrf_start:]
            
            if not csrf:
                logger.error("无法获取CSRF令牌，图片验证码处理失败")
                return False
                
            # 获取图片验证码
            logger.info("正在获取图片验证码...")
            headers = self.api.headers.copy()
            img_url = f"https://api.bilibili.com/x/gaia-vgate/v1/img?csrf={csrf}&token={token}"
            
            img_response = requests.get(img_url, headers=headers)
            if img_response.status_code != 200:
                logger.error(f"获取图片验证码失败: HTTP {img_response.status_code}")
                return False
                
            img_data = img_response.json()
            if img_data.get("code") != 0:
                logger.error(f"获取图片验证码失败: {img_data.get('message')}")
                return False
                
            # 获取base64编码的图片
            img_base64 = img_data.get("data", {}).get("img")
            if not img_base64:
                logger.error("图片验证码数据为空")
                return False
                
            # 保存图片到临时文件并显示
            import tempfile
            import base64
            import os
            import webbrowser
            from PIL import Image
            import io
            
            # 解码base64图片
            img_bytes = base64.b64decode(img_base64)
            img = Image.open(io.BytesIO(img_bytes))
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                img.save(temp_file.name)
                temp_file_path = temp_file.name
            
            # 尝试显示图片
            try:
                # 尝试使用PIL显示
                img.show()
                logger.info(f"已显示验证码图片，请查看弹出窗口")
            except:
                try:
                    # 尝试使用webbrowser打开
                    webbrowser.open(f"file://{temp_file_path}")
                    logger.info(f"已在浏览器中打开验证码图片")
                except:
                    logger.warning(f"无法自动显示验证码图片，请手动打开: {temp_file_path}")
            
            # 提示用户输入验证码
            from getpass import getpass
            print("请查看弹出的验证码图片，然后在下方输入验证码:")
            verify_code = input("验证码: ").strip()
            
            # 删除临时文件
            try:
                os.unlink(temp_file_path)
            except:
                pass
                
            if not verify_code:
                logger.error("验证码输入为空")
                return False
                
            # 提交验证码
            logger.info(f"正在提交图片验证码: {verify_code}")
            
            # 构造表单数据
            form_data = {
                "token": token,
                "csrf": csrf,
                "code": verify_code
            }
            
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success(f"图片验证码验证通过！")
                logger.debug(f"验证响应: {response.get('data', {}).get('msg', '无响应消息')}")
                return True
            else:
                logger.error(f"图片验证码验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"图片验证码处理异常: {str(e)}", exc_info=True)
            return False
    
    def _handle_sms_captcha(self, token: str) -> bool:
        """处理短信验证码"""
        try:
            logger.info("处理短信验证码...")
            
            # 获取csrf token
            csrf = None
            if hasattr(self.api, 'headers') and self.api.headers.get('Cookie'):
                cookie_str = self.api.headers['Cookie']
                if 'bili_jct=' in cookie_str:
                    csrf_start = cookie_str.find('bili_jct=') + 9
                    csrf_end = cookie_str.find(';', csrf_start)
                    csrf = cookie_str[csrf_start:csrf_end] if csrf_end != -1 else cookie_str[csrf_start:]
            
            if not csrf:
                logger.error("无法获取CSRF令牌，短信验证码处理失败")
                return False
            
            # 请求发送短信验证码
            logger.info("正在请求发送短信验证码...")
            
            # 构造表单数据
            form_data = {
                "token": token,
                "csrf": csrf
            }
            
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/sendMsg",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") != 0:
                logger.error(f"请求发送短信验证码失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
            logger.success("短信验证码已发送，请查看手机")
            logger.debug(f"发送响应: {response.get('data', {}).get('msg', '无响应消息')}")
            
            # 提示用户输入验证码
            print("请查看手机短信，然后在下方输入收到的验证码:")
            verify_code = input("短信验证码: ").strip()
                
            if not verify_code:
                logger.error("验证码输入为空")
                return False
                
            # 提交验证码
            logger.info(f"正在提交短信验证码: {verify_code}")
            
            # 构造表单数据
            form_data = {
                "token": token,
                "csrf": csrf,
                "code": verify_code
            }
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success(f"短信验证码验证通过！")
                logger.debug(f"验证响应: {response.get('data', {}).get('msg', '无响应消息')}")
                return True
            else:
                logger.error(f"短信验证码验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"短信验证码处理异常: {str(e)}", exc_info=True)
            return False
    
    def _handle_phone_validation(self, token: str, register_data: Dict) -> bool:
        """处理手机号验证"""
        try:
            logger.info("处理手机号验证...")
            
            # 获取csrf token
            csrf = None
            if hasattr(self.api, 'headers') and self.api.headers.get('Cookie'):
                cookie_str = self.api.headers['Cookie']
                if 'bili_jct=' in cookie_str:
                    csrf_start = cookie_str.find('bili_jct=') + 9
                    csrf_end = cookie_str.find(';', csrf_start)
                    csrf = cookie_str[csrf_start:csrf_end] if csrf_end != -1 else cookie_str[csrf_start:]
            
            if not csrf:
                logger.error("无法获取CSRF令牌，手机号验证失败")
                return False
                
            # 获取手机号信息
            phone_info = register_data.get("phone", {})
            tel = phone_info.get("tel", "")  # 部分手机号
            tel_len = phone_info.get("telLen", 0)  # 手机号长度
            
            if not tel or not tel_len:
                logger.error("手机号验证信息不完整")
                return False
                
            logger.info(f"需要验证手机号: {tel}，总长度: {tel_len}")
            
            # 提示用户输入完整手机号
            print(f"请输入完整的手机号（已知前缀: {tel}，总长度: {tel_len}）:")
            complete_tel = input("完整手机号: ").strip()
            
            # 验证输入的手机号长度
            if len(complete_tel) != tel_len:
                logger.error(f"输入的手机号长度不正确，应为 {tel_len} 位")
                return False
                
            # 验证输入的手机号是否与前缀匹配
            if not complete_tel.startswith(tel):
                logger.warning(f"输入的手机号 {complete_tel} 与前缀 {tel} 不匹配，但仍将尝试验证")
                
            # 提交手机号验证
            logger.info(f"正在提交手机号验证: {complete_tel}")
            
            # 构造表单数据
            form_data = {
                "token": token,
                "csrf": csrf,
                "code": complete_tel
            }
            
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success(f"手机号验证通过！")
                logger.debug(f"验证响应: {response.get('data', {}).get('msg', '无响应消息')}")
                
                # 保存手机号到配置（如果有必要）
                if hasattr(self.api, 'device') and hasattr(self.api.device, 'phone'):
                    self.api.device.phone = complete_tel
                    logger.info(f"已保存手机号到设备配置")
                
                return True
            else:
                logger.error(f"手机号验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"手机号验证处理异常: {str(e)}", exc_info=True)
            return False
    
    def _handle_sms_mo_validation(self, token: str, register_data: Dict) -> bool:
        """处理短信外发验证码"""
        try:
            logger.info("处理短信外发验证码...")
            
            # 获取csrf token
            csrf = None
            if hasattr(self.api, 'headers') and self.api.headers.get('Cookie'):
                cookie_str = self.api.headers['Cookie']
                if 'bili_jct=' in cookie_str:
                    csrf_start = cookie_str.find('bili_jct=') + 9
                    csrf_end = cookie_str.find(';', csrf_start)
                    csrf = cookie_str[csrf_start:csrf_end] if csrf_end != -1 else cookie_str[csrf_start:]
            
            if not csrf:
                logger.error("无法获取CSRF令牌，短信外发验证码处理失败")
                return False
            
            # 获取短信外发验证码信息
            sms_mo_info = register_data.get("sms_mo", {})
            sms_mo_tel = sms_mo_info.get("sms_mo_tel", "")  # 接收短信的手机号
            tel = sms_mo_info.get("tel", "")  # 用户手机号前缀
            content = sms_mo_info.get("content", "")  # 短信内容
            
            if not sms_mo_tel or not content:
                logger.error("短信外发验证码信息不完整")
                return False
                
            # 显示短信外发验证码信息
            print("\n==== 短信外发验证码 ====")
            print(f"请向手机号 {sms_mo_tel} 发送以下内容的短信:")
            print(f"短信内容: {content}")
            print("=======================\n")
            
            logger.info(f"请向手机号 {sms_mo_tel} 发送内容为 '{content}' 的短信")
            
            # 确认是否已发送
            confirm = input("是否已发送短信？(y/n): ").strip().lower()
            if confirm != 'y':
                logger.warning("用户取消短信外发验证")
                return False
            
            # 提交短信外发验证码
            logger.info("正在提交短信外发验证确认...")
            
            # 构造表单数据
            form_data = {
                "token": token,
                "csrf": csrf,
                "content": content
            }
            
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success(f"短信外发验证通过！")
                logger.debug(f"验证响应: {response.get('data', {}).get('msg', '无响应消息')}")
                return True
            else:
                logger.error(f"短信外发验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"短信外发验证码处理异常: {str(e)}", exc_info=True)
            return False
    
    def _handle_biliword(self, token: str, register_data: Dict) -> bool:
        """处理B站词验证码"""
        try:
            logger.info("处理B站词验证码...")
            
            # 获取csrf token
            csrf = None
            if hasattr(self.api, 'headers') and self.api.headers.get('Cookie'):
                cookie_str = self.api.headers['Cookie']
                if 'bili_jct=' in cookie_str:
                    csrf_start = cookie_str.find('bili_jct=') + 9
                    csrf_end = cookie_str.find(';', csrf_start)
                    csrf = cookie_str[csrf_start:csrf_end] if csrf_end != -1 else cookie_str[csrf_start:]
            
            if not csrf:
                logger.error("无法获取CSRF令牌，B站词验证码处理失败")
                return False
            
            # 获取B站词验证码信息
            biliword_info = register_data.get("biliword", {})
            biliword_text = biliword_info.get("biliword_text", "")  # 验证码文本
            
            if not biliword_text:
                logger.error("B站词验证码信息不完整")
                return False
                
            # 显示B站词验证码信息
            print("\n==== B站词验证码 ====")
            print(f"请输入以下B站词验证码:")
            print(f"验证码文本: {biliword_text}")
            print("=======================\n")
            
            logger.info(f"请输入B站词验证码: {biliword_text}")
            
            # 提示用户输入验证码
            print("请输入验证码:")
            verify_code = input("验证码: ").strip()
            
            if not verify_code:
                logger.error("验证码输入为空")
                return False
                
            # 提交B站词验证码
            logger.info(f"正在提交B站词验证码: {verify_code}")
            
            # 构造表单数据
            form_data = {
                "token": token,
                "csrf": csrf,
                "code": verify_code
            }
            
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success(f"B站词验证通过！")
                logger.debug(f"验证响应: {response.get('data', {}).get('msg', '无响应消息')}")
                return True
            else:
                logger.error(f"B站词验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"B站词验证码处理异常: {str(e)}", exc_info=True)
            return False
    

