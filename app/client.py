import base64
import json
from pathlib import Path
import time
import ssl
import threading
import traceback
from urllib.parse import urlencode
import curl_cffi.requests
from typing import Optional, List, Dict, TYPE_CHECKING
from dataclasses import dataclass
import random
import hashlib
import uuid
import struct
import re
import urllib.parse
import hmac
import io, base64

from app.utils.virtual_device import create_virtual_device

from .utils.log import logger
from .utils.file_utils import file_utils
from noneprompt import CancelledError, InputPrompt, ConfirmPrompt
from .api import API
import yaml

if TYPE_CHECKING:
    from .utils.account_manager import VirtualDevice


class Client:
    """对外暴露的客户端入口.

    兼容设计: 为了支持 `client.api.xxx` 的调用方式, 这里提供一个 `api` 属性指向 API 实例。
    这样既能保持方法路径层级清晰, 又不必大幅改动现有实现。
    """

    def __init__(self) -> None:
        # self.gaia_handler = GaiaCaptchaManager(self)  # 已删除，直接使用 handle_gaia 函数
        self.cookie = None
        self.device = None
        self.buvid: str | None = None  # buvid1
        
        # 添加WBI相关字段
        self.wbi_img_key = None
        self.wbi_sub_key = None
        self.bili_ticket_last_refresh = 0  # 上次刷新bili_ticket的时间戳
        self.bili_ticket = None  # 保存bili_ticket的值

        # 基础请求头，稍后会根据用户配置进行更新
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://show.bilibili.com",
            "Referer": "https://show.bilibili.com/",
            "Cookie": None,
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        }
        
        self.ptoken: Optional[str] = None
        self.ctoken: Optional[str] = None
        # 提供可静态分析的 api 入口
        self.api = API(self)
        
        # 尝试导入bili_ticket_gt_python
        try:
            import bili_ticket_gt_python
            self.click = bili_ticket_gt_python.ClickPy()
            # logger.info("bili_ticket_gt_python 加载成功")
        except ImportError:
            logger.warning("bili_ticket_gt_python 未安装，部分验证码功能将不可用")
            self.click = None
    
    def load_cookie(self, cookie: str) -> None:
        """
        加载cookie并更新用户配置
        """
        self.cookie = cookie
        self.headers["Cookie"] = cookie
        if cookie:
            self.headers["Cookie"] = cookie
        else:
            # 如果传入空字符串，清理 Cookie 头
            self.headers.pop("Cookie", None)
    
    def _make_api_call(self, method: str, url: str, headers: dict, json_data=None, params=None, timeout: int = 120, impersonate: str = None) -> Optional[dict]:
        """统一API调用方法，支持impersonate参数，官方推荐写法"""
        try:
            enhanced_headers = headers.copy()
            if hasattr(self, "x_risk_header") and self.x_risk_header:
                enhanced_headers.setdefault("x-risk-header", self.x_risk_header)
            if hasattr(self, 'device_fingerprint'):
                device_info = {
                    "platform": "ios",
                    "version": getattr(self.device_fingerprint, "bili_app_version", "8.48.0"),
                    "device_type": self.device_fingerprint.model,
                    "network": "wifi",
                    "device_id": self.device_fingerprint.device_id,
                    "canvas_fp": self.device_fingerprint.canvas_fp[:16],
                    "webgl_fp": self.device_fingerprint.webgl_fp[:16],
                    "screen_resolution": self.device_fingerprint.resolution
                }
                enhanced_headers["X-Bili-Device-Req-Json"] = json.dumps(device_info)
            enhanced_headers["X-Bili-Trace-Id"] = f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0"
            request_args = {
                "method": method.upper(),
                "url": url,
                "headers": enhanced_headers,
                "timeout": timeout
            }
            if params:
                request_args["params"] = params
            if json_data:
                request_args["json"] = json_data
            if impersonate:
                request_args["impersonate"] = impersonate
            response = curl_cffi.requests.request(**request_args)
            if method.upper() == 'POST':
                try:
                    logger.debug(f"POST {url}")
                    logger.debug(f"Response: {response.status_code}")
                    logger.debug(f"Response: {response.text}")
                except Exception as e:
                    logger.error(f"Error logging response: {e}")
            response.raise_for_status()
            result = response.json()
            code = result.get("code")
            if code in (-401, -352):
                risk_params = None
                if code == -401:
                    risk_params = result.get("data", {}).get("ga_data", {}).get("riskParams")
                if not risk_params and code == -352:
                    risk_params = result.get("data", {}).get("v_voucher")
                if not risk_params:
                    risk_params = response.headers.get("x-bili-gaia-vvoucher")
                if risk_params:
                    logger.warning("检测到风控验证，尝试自动处理...")
                    if self.handle_gaia(risk_params):
                        logger.success("风控验证通过，重新请求...")
                        return self._make_api_call(method, url, headers, json_data, params, timeout, impersonate)
                    else:
                        logger.error("风控验证失败")
            return result
        except curl_cffi.requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {url}: {e}")
            raise
    
    def _build_ctoken(
        self,
        touches: int = 0,
        scroll_x: int = 0,
        visibility: int = 0,
        scroll_y: int = 0,
        unloads: int = 0,
        seconds_alive: int = 0,
        delta_time: int = 0,
        screen_x: int = 0,
        screen_y: int = 0,
        inner_width: int = None,
        inner_height: int = None,
        outer_width: int = None,
        outer_height: int = None,
        screen_width: int = None,
    ) -> str:
        """精简版 ctoken 生成，与前端 ticket_collection.encode 等价。"""
        # 如果未提供屏幕尺寸相关参数，从设备指纹获取分辨率
        if any(p is None for p in [inner_width, inner_height, outer_width, outer_height, screen_width]):
            res = self.device_fingerprint.resolution
            width, height = map(int, res.split('x'))
            inner_width = inner_width or width
            inner_height = inner_height or height
            outer_width = outer_width or width
            outer_height = outer_height or height
            screen_width = screen_width or width

        clip8 = lambda v: max(0, min(255, int(v)))
        clip16 = lambda v: max(0, min(65535, int(v)))

        # 初始化 16 字节缓冲
        buf = bytearray([
            clip8(touches),
            clip8(scroll_x),
            clip8(visibility),
            clip8(scroll_y),
            clip8(inner_width),
            clip8(unloads),
            clip8(inner_height),
            clip8(outer_width),
            0, 0, 0, 0,  # 8~11 占位（稍后覆盖）
            clip8(outer_height),
            clip8(screen_x),
            clip8(screen_y),
            clip8(screen_width),
        ])

        # 以网络字节序写入 16-bit 字段
        struct.pack_into('>H', buf, 8, clip16(seconds_alive))
        struct.pack_into('>H', buf, 10, clip16(delta_time))

        # UTF-16 LE 扩展，再 Base64
        doubled = bytearray()
        for b in buf:
            doubled.append(b)
            doubled.append(0)
        return base64.b64encode(doubled).decode()

    def set_device(self, device: "VirtualDevice") -> None:
        """手动绑定虚拟设备到当前 Api 实例，并更新相关请求头。"""
        self.device = device
        self.device_fingerprint = device

        # 更新请求头，填入设备指纹字段
        self.headers.update({
            "User-Agent": device.user_agent,
            "X-Bili-Device-Fp": device.device_id,
            "X-Bili-Canvas-Fp": device.canvas_fp[:16],
            "X-Bili-WebGL-Fp": device.webgl_fp[:16],
        })
        logger.debug(f"已绑定虚拟设备: {device.device_name} (ID: {device.device_id[:8]}...)")

        def _update_cookie(key: str, value: str):
            if not value:
                return
            cookie_str = self.headers.get("Cookie", "") or ""
            items = [c.strip() for c in cookie_str.split(";") if c.strip() and not c.strip().startswith(f"{key}=")]
            items.append(f"{key}={value}")
            self.headers["Cookie"] = "; ".join(items)

        if getattr(self, "buvid", None):
            return
        rnd = hashlib.md5(str(random.random()).encode()).hexdigest()
        # 生成 buvid1
        buvid1 = f"XU{rnd[2]}{rnd[12]}{rnd[22]}{rnd}".upper()
        self.buvid = buvid1
        
        # 生成 buvid_fp
        rnd2 = hashlib.md5(str(random.random()).encode()).hexdigest()
        fp_raw = rnd2 + time.strftime("%Y%m%d%H%M%S", time.localtime()) + "".join(random.choice("0123456789abcdef") for _ in range(16))
        fp_raw_sub = [fp_raw[i:i+2] for i in range(0, len(fp_raw), 2)]
        veri = sum(int(x,16) for x in fp_raw_sub[::2]) % 256
        buvid_fp = f"{fp_raw}{hex(veri)[2:]}"
        
        # 获取 buvid3 / buvid4
        buvid3 = buvid4 = ""
        try:
            r = requests.get("https://api.bilibili.com/x/frontend/finger/spi", headers={"User-Agent": self.headers["User-Agent"]}, timeout=10)
            if r.status_code == 200:
                jd = r.json().get("data", {})
                buvid3 = jd.get("b_3", "")
                buvid4 = jd.get("b_4", "")
        except Exception as e:
            logger.debug(f"finger/spi 失败: {e}")
            
        # 生成 _uuid
        import uuid
        _uuid = f"{uuid.uuid4()}{str(int(time.time()*1000)%100000).ljust(5,'0')}infoc"
        for k,v in ("buvid",buvid1), ("buvid3",buvid3), ("buvid4",buvid4), ("buvid_fp",buvid_fp), ("_uuid",_uuid):
            _update_cookie(k,v)
            
        # 整合 buvid 和 risk header
        identify = hashlib.md5(str(int(time.time()*1000)).encode()).hexdigest()
        parts = [
            "appkey/1d8b6e7d45233436",
            "brand/Apple",
            f"localBuvid/{self.buvid}",
            "mVersion/296",
            f"mallVersion/{device.bili_app_build}",
            f"model/{device.model}",
            f"osver/{device.ios_version.split('.')[0]}",
            "platform/h5",
            "uid/0",
            "channel/1",
            f"deviceId/{self.buvid}",
            "sLocale/zh_CN",
            "cLocale/zh_CN",
            f"identify/{identify}"
        ]
        self.x_risk_header = " ".join(parts)

        logger.debug(f"已生成 x-risk-header: {self.x_risk_header}")

    def handle_gaia(self, riskParams) -> bool:
        """处理 bilibili Gaia 风控验证"""
        # 注册
        register = self._make_api_call(
            "POST",
            "https://api.bilibili.com/x/gaia-vgate/v1/register",
            self.headers,
            json_data=riskParams,
        )
        logger.debug(register)

        if register["code"] != 0:
            logger.error(f"Gaia注册失败: {register['message']}")
            return False

        token: str = register["data"]["token"]
        # 设置 gaia token cookie - 使用正确的方式
        if "Cookie" in self.headers and self.headers["Cookie"]:
            cookie_str = self.headers["Cookie"]
            items = [c.strip() for c in cookie_str.split(";") if c.strip() and not c.strip().startswith("x-bili-gaia-vtoken=")]
            items.append(f"x-bili-gaia-vtoken={token}")
            self.headers["Cookie"] = "; ".join(items)
        else:
            self.headers["Cookie"] = f"x-bili-gaia-vtoken={token}"

        # 获取 csrf - 从 cookie 中获取 bili_jct
        csrf = ""
        if "Cookie" in self.headers and self.headers["Cookie"]:
            for cookie_item in self.headers["Cookie"].split(";"):
                if cookie_item.strip().startswith("bili_jct="):
                    csrf = cookie_item.strip().split("=", 1)[1]
                    break

        logger.debug("GAIA Token: " + token)
        
        # 获取验证码类型
        captcha_type = register["data"]["type"]
        
        if captcha_type == "":
            logger.debug("GAIA Type: Direct")
            resp = self._make_api_call(
                "POST",
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                self.headers,
                json_data={
                    "token": token,
                    "csrf": csrf
                }
            )
            logger.debug(resp)
            if resp["code"] != 0:
                logger.error(f"Gaia验证失败: {resp['message']}")
                return False
            else:
                logger.debug("GAIA Validate: " + resp["data"]["msg"])
                return True
        elif captcha_type == "biliword":
            logger.debug("GAIA Type: Biliword")
            logger.error("暂不支持 Biliword 验证码类型")
            return False
        elif captcha_type == "geetest":
            logger.debug("GAIA Type: GeeTest")
            gt = register["data"]["geetest"]["gt"]
            challenge = register["data"]["geetest"]["challenge"]
            logger.debug("GAIA GeeTest: " + gt + " " + challenge)
            
            if self.click is None:
                logger.error("验证码系统未设置")
                return False
            
            logger.debug("Running GeeTest Auto Solver...")
            try:
                validate = self.click.simple_match_retry(gt, challenge)
                seccode = validate + "|jordan"
            except Exception as e:
                logger.error(f"验证码识别失败: {e}")
                return False
            
            logger.debug("GAIA Validate: " + validate)
            logger.debug("GAIA Seccode: " + seccode)
            
            resp = self._make_api_call(
                "POST",
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                self.headers,
                json_data={
                    "token": token,
                    "csrf": csrf,
                    "challenge": challenge,
                    "validate": validate,
                    "seccode": seccode,
                }
            )
            logger.debug(resp)
            if resp["code"] != 0:
                logger.error(f"Gaia验证失败: {resp['message']}")
                return False
            else:
                logger.debug("GAIA Validate: " + resp["data"]["msg"])
                return True
        elif captcha_type == "phone":
            logger.debug("GAIA Type: Phone")
            tel = register["data"]["phone"]["tel"]
            telLen = register["data"]["phone"]["telLen"]
            logger.debug("GAIA Phone: " + tel + " " + str(telLen))
            
            # 检查是否有配置的手机号，且长度匹配
            complete_tel = None
            if hasattr(self, 'config') and self.config and "phone" in self.config:
                if len(self.config["phone"]) == telLen:
                    complete_tel = self.config["phone"]
            
            if complete_tel is None:
                try:
                    complete_tel = InputPrompt(f"请补全手机号码 ({tel}): ").prompt()
                    if len(complete_tel) != telLen:
                        logger.error(f"手机号码长度错误，应为 {telLen} 位")
                        return False
                except CancelledError:
                    logger.info("用户取消手机验证")
                    return False
            
            logger.debug("GAIA Phone Complete: " + complete_tel)
            
            resp = self._make_api_call(
                "POST",
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                self.headers,
                json_data={
                    "token": token,
                    "csrf": csrf,
                    "code": complete_tel
                }
            )
            logger.debug(resp)
            if resp["code"] != 0:
                logger.error(f"Gaia验证失败: {resp['message']}")
                return False
            else:
                logger.debug("GAIA Phone Verify: " + resp["data"]["msg"])
                return True
        elif captcha_type == "img":
            logger.debug("GAIA Type: Img")
            img_resp = self._make_api_call(
                "GET",
                f"https://api.bilibili.com/x/gaia-vgate/v1/img?csrf={csrf}&token={token}",
                self.headers
            )
            logger.debug(img_resp)
            if img_resp["code"] != 0:
                logger.error(f"获取图形验证码失败: {img_resp['message']}")
                return False
            else:
                try:
                    import base64
                    
                    img_base64 = img_resp["data"]["img"]
                    logger.debug("GAIA Img: " + img_base64)
                    
                    # 使用工具类保存验证码图片并打开文件夹
                    img_data = base64.b64decode(img_base64)
                    file_utils.save_image_and_open_folder(img_data, "gaia_captcha")
                    
                    img_verify = InputPrompt("请输入图形验证码: ").prompt()
                    
                    resp = self._make_api_call(
                        "POST",
                        "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                        self.headers,
                        json_data={
                            "token": token,
                            "csrf": csrf,
                            "code": img_verify
                        }
                    )
                    if resp["code"] != 0:
                        logger.error(f"Gaia验证失败: {resp['message']}")
                        return False
                    else:
                        logger.debug("GAIA Img Verify: " + resp["data"]["msg"])
                        return True
                except Exception as e:
                    logger.error(f"处理图形验证码异常: {e}")
                    return False
                finally:
                    # 无论如何退出都清理验证码文件
                    file_utils.clean_temp_files("gaia_captcha")
        elif captcha_type == "sms":
            logger.debug("GAIA Type: SMS")
            resp = self._make_api_call(
                "POST",
                "https://api.bilibili.com/x/gaia-vgate/v1/sendMsg",
                self.headers,
                json_data={
                    "token": token,
                    "csrf": csrf
                }
            )
            logger.debug(resp)
            if resp["code"] != 0:
                logger.error(f"发送短信失败: {resp['message']}")
                return False
            else:
                logger.debug("GAIA SMS: " + resp["data"]["msg"])
                try:
                    verify_code = InputPrompt("请输入短信验证码: ").prompt()
                    
                    resp = self._make_api_call(
                        "POST",
                        "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                        self.headers,
                        json_data={
                            "token": token,
                            "csrf": csrf,
                            "code": verify_code
                        }
                    )
                    logger.debug(resp)
                    if resp["code"] != 0:
                        logger.error(f"Gaia验证失败: {resp['message']}")
                        return False
                    else:
                        logger.debug("GAIA SMS Verify: " + resp["data"]["msg"])
                        return True
                except CancelledError:
                    logger.info("用户取消短信验证")
                    return False
        elif captcha_type == "sms_mo":
            logger.debug("GAIA Type: SMS_MO")
            sms_mo_tel = register["data"]["sms_mo"]["sms_mo_tel"]
            tel = register["data"]["sms_mo"]["tel"]
            content = register["data"]["sms_mo"]["content"]
            logger.debug("GAIA SMS_MO: " + sms_mo_tel + " " + tel + " " + content)
            logger.info(f"请使用手机 {tel} 发送短信内容 '{content}' 到 {sms_mo_tel}")
            
            try:
                confirm = ConfirmPrompt("是否已发送短信?").prompt()
                if confirm:
                    resp = self._make_api_call(
                        "POST",
                        "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                        self.headers,
                        json_data={
                            "token": token,
                            "csrf": csrf,
                            "content": content
                        }
                    )
                    logger.debug(resp)
                    if resp["code"] != 0:
                        logger.error(f"Gaia验证失败: {resp['message']}")
                        return False
                    else:
                        logger.debug("GAIA SMS_MO Verify: " + resp["data"]["msg"])
                        return True
                else:
                    return False
            except CancelledError:
                logger.info("用户取消短信MO验证")
                return False
        else:
            logger.error("不支持的验证码类型")
            return False

    def generate_click_position(self):
        """生成随机点击位置，用于模拟真实用户点击
        
        返回:
            dict: 包含点击位置信息的字典
        """
        click_position = {
            "x": random.randint(200, 400),
            "y": random.randint(750, 800),
            "origin": int(time.time() * 1000) - random.randint(100000, 200000),
            "now": int(time.time() * 1000),
        }
        return click_position





