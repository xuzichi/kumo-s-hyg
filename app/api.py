import base64
import json
from pathlib import Path
import time
import ssl
import threading
import traceback
from urllib.parse import urlencode
import qrcode
import requests
from typing import Optional, List, Dict
import json
from dataclasses import dataclass
import random
import hashlib
import uuid

from .log import logger
from .captcha import CaptchaHandler
from .token_generator import create_token_generator
import yaml


def create_device_fingerprint_generator():
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
    
    # === 设备状态 ===
    device_model = random.choice(IPHONE_MODELS)
    fingerprint_cache = {
        'device_id': None,
        'canvas_fp': None, 
        'webgl_fp': None
    }
    
    def generate_device_id():
        """生成设备ID指纹 - 基于JS逆向的generateDeviceFingerPointer实现"""
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
        """生成Canvas指纹 - 模拟真实文本绘制和字体渲染"""
        if fingerprint_cache['canvas_fp']:
            return fingerprint_cache['canvas_fp']
            
        # Canvas绘制内容（基于真实指纹检测文本）
        canvas_texts = [
            "BzqvpbVhJ9J8fCqFzq&'*bvJ4DsJBQ\"LVQ*qzKE",  # 指纹检测文本
            f"iPhone,{device_model}",  # 设备信息
            "😊🍎🌟",  # emoji测试
            "hello world 123",  # 简单文本
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
        """生成WebGL指纹 - 基于真实GPU信息和扩展"""
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
        # iOS版本生成（真实分布）
        major_versions = [17, 18]
        major = random.choice(major_versions)
        minor = random.randint(0, 6) if major == 17 else random.randint(0, 2)
        patch = random.randint(0, 3)
        ios_version = f"{major}.{minor}.{patch}"
        
        # WebKit版本（与iOS版本相关）
        webkit_base = 605 if major == 17 else 618
        webkit_version = f"{webkit_base + random.randint(0, 15)}.1.{random.randint(10, 99)}"
        
        return ios_version, webkit_version
    
    # === 统一接口 ===
    def get_all_fingerprints():
        """生成完整的设备指纹信息"""
        ios_version, webkit_version = generate_version_info()
        additional_fps = generate_additional_fingerprints()
        
        # 生成User-Agent
        ua = (f"Mozilla/5.0 (iPhone; CPU iPhone OS {ios_version.replace('.', '_')} like Mac OS X) "
              f"AppleWebKit/{webkit_version} (KHTML, like Gecko) Mobile/22F76 BiliApp/84800100 "
              f"os/ios model/{device_model} mobi_app/iphone build/84800100 osVer/{ios_version} "
              f"network/wifi channel/AppStore")
        
        return {
            'user_agent': ua,
            'device_id': generate_device_id(),
            'canvas_fp': generate_canvas_fingerprint(),
            'webgl_fp': generate_webgl_fingerprint(),
            'fe_sign': hashlib.sha256(f"{device_model}:{ios_version}:{time.time()}".encode()).hexdigest()[:32],
            'brand': 'iPhone',
            'model': device_model,
            'ios_version': ios_version,
            'webkit_version': webkit_version,
            **additional_fps
        }
    
    # 返回闭包接口
    return get_all_fingerprints


class DeviceFingerprint:
    """设备指纹生成器 - 基于闭包模式的清晰实现"""
    def __init__(self):
        # 创建指纹生成器闭包
        self._fingerprint_generator = create_device_fingerprint_generator()
        
    def get_all_fingerprints(self):
        """获取所有设备指纹信息"""
        return self._fingerprint_generator()


@dataclass
class BuyerJson:
    pass


@dataclass
class AddressJson:
    pass


@dataclass
class ProjectJson:
    pass


@dataclass
class confirmJson:
    pass


@dataclass
class prepareJson:
    pass


@dataclass
class createJson:
    pass

@dataclass
class myInfoJson:
    pass

@dataclass
class createStatusJson:
    pass

@dataclass
class ProjectInfoByDateJson:
    pass



class Api:
    def __init__(self, cookie: Optional[str] = None) -> None:
        # 初始化设备指纹生成器
        self.fingerprint = DeviceFingerprint()
        self.captcha_handler = CaptchaHandler(self)
        
        self.buvid3 = None  # 存储真实的buvid3
        if cookie:
            import re
            match = re.search(r'buvid3=([^;]+)', cookie)
            if match:
                self.buvid3 = match.group(1)
        self.token_generator = create_token_generator(self.buvid3)
        
        # 获取动态生成的指纹信息
        fingerprints = self.fingerprint.get_all_fingerprints()
        
        # 使用动态生成的User-Agent和其他指纹信息
        self.headers = {
            "User-Agent": fingerprints['user_agent'],
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://show.bilibili.com",
            "Referer": "https://show.bilibili.com/",
            "Cookie": cookie,
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
            # 添加更多指纹相关的头
            "X-Bili-Device-Fp": fingerprints['device_id'],
            "X-Bili-Canvas-Fp": fingerprints['canvas_fp'][:16],  # 截取前16位
            "X-Bili-WebGL-Fp": fingerprints['webgl_fp'][:16],
        }
        
        # 存储设备指纹信息
        self.device_fingerprints = fingerprints
        logger.debug(f"设备指纹已生成:")
        logger.debug(f"  Device ID: {fingerprints['device_id']}")
        logger.debug(f"  Buvid3: {self.buvid3 or '未从Cookie获取'}")
        logger.debug(f"  Model: {fingerprints['model']}")
        logger.debug(f"  iOS Version: {fingerprints['ios_version']}")
        logger.debug(f"  Canvas FP: {fingerprints['canvas_fp'][:16]}...")
        logger.debug(f"  WebGL FP: {fingerprints['webgl_fp'][:16]}...")
        logger.debug(f"  Resolution: {fingerprints['resolution']}")
    
    def set_cookie(self, cookie: str) -> None:
        self.headers["Cookie"] = cookie
        # 更新token生成器的buvid3
        if cookie:
            import re
            match = re.search(r'buvid3=([^;]+)', cookie)
            if match:
                self.buvid3 = match.group(1)
                self.token_generator = create_token_generator(self.buvid3)
        
    def _make_api_call(self, method: str, url: str, headers: dict, json_data=None, params=None, timeout: int = 120) -> Optional[dict]:
        """增强的API调用方法，支持错误处理和风控检测"""
        try:
            # 动态更新请求头
            enhanced_headers = headers.copy()
            
            # 添加设备信息头（如果指纹可用）
            if hasattr(self, 'device_fingerprints'):
                device_info = {
                    "platform": "ios",
                    "version": "8.48.0",
                    "device_type": self.device_fingerprints['model'],
                    "network": "wifi",
                    "device_id": self.device_fingerprints['device_id'],
                    "canvas_fp": self.device_fingerprints['canvas_fp'][:16],
                    "webgl_fp": self.device_fingerprints['webgl_fp'][:16],
                    "screen_resolution": self.device_fingerprints['resolution']
                }
                enhanced_headers["X-Bili-Device-Req-Json"] = json.dumps(device_info)
            
            enhanced_headers["X-Bili-Trace-Id"] = f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0"
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=enhanced_headers, params=params, timeout=timeout)
            elif method.upper() == 'POST':
                response = requests.post(
                    url,
                    headers=enhanced_headers,
                    json=json_data,
                    timeout=timeout
                )
                try:
                    logger.debug(f"POST {url}")
                    logger.debug(f"Response: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error logging response: {e}")
            
            response.raise_for_status()
            result = response.json()
            
            # 检查是否触发风控
            if result.get("code") == -401 and "ga_data" in result.get("data", {}):
                logger.warning("检测到风控验证，尝试自动处理...")
                risk_params = result["data"]["ga_data"]["riskParams"]
                if self.captcha_handler.handle_gaia_validation(risk_params):
                    logger.success("风控验证通过，重新请求...")
                    # 重新发起请求
                    return self._make_api_call(method, url, headers, json_data, params, timeout)
                else:
                    logger.error("风控验证失败")
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {url}: {e}")
            raise

    def project(self, project_id)-> "ProjectJson":
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        return self._make_api_call('GET', f'https://show.bilibili.com/api/ticket/project/getV2?id={project_id}', mobile_headers)

    def buyer(self,)->"BuyerJson":
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return self._make_api_call('GET', "https://show.bilibili.com/api/ticket/buyer/list?is_default", mobile_headers)

    def address(self, )-> "AddressJson":
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return self._make_api_call('GET', "https://show.bilibili.com/api/ticket/addr/list", mobile_headers)

    def confirm(self, project_id, token, voucher: str = "", request_source: str = "h5") -> "confirmJson":
        # 使用正确的token生成器生成ptoken
        ptoken = self.token_generator.generate_ptoken()
            
        url = f"https://show.bilibili.com/api/ticket/order/confirmInfo?token={token}&voucher={voucher}&projectId={project_id}&ptoken={ptoken}&project_id={project_id}&requestSource={request_source}"
        mobile_headers = self.headers.copy()
        logger.debug(f"Confirm请求，携带正确ptoken: {ptoken}")
        return self._make_api_call('GET', url, mobile_headers)

    def prepare(self,  project_id, count, screen_id, sku_id) -> "prepareJson":
        """
        prepare请求，携带正确的ctoken
        """
        url = f"https://show.bilibili.com/api/ticket/order/prepare?project_id={project_id}"
        
        # 使用正确的token生成器生成ctoken
        prepare_token = self.token_generator.generate_ctoken()
        
        payload = {
            "project_id": project_id,
            "count": count,
            "order_type": 1,
            "screen_id": screen_id,
            "sku_id": sku_id,
            "token": prepare_token,
            "newRisk": True,
            "requestSource": "neul-next",
        }
        
        mobile_headers = self.headers.copy()
        logger.debug(f"Prepare请求，携带正确ctoken: {prepare_token}")
        return self._make_api_call('POST', url, mobile_headers, json_data=payload)

    def create(self, project_id, token, screen_id, sku_id, count, pay_money, buyer_info, ptoken="", deliver_info=None, buyer=None, tel=None) -> "createJson":
        """
        create请求，携带正确的ctoken和ptoken
        """                
        if not ptoken:
            real_ptoken = self.token_generator.generate_ptoken()
        else:
            real_ptoken = ptoken
        
        payload = {
            "count": count,
            "pay_money": pay_money * count,
            "project_id": project_id,
            "screen_id": screen_id,
            "sku_id": sku_id,
            "timestamp": int(round(time.time() * 1000)),
            "order_type": 1,
            "deviceId": self.device_fingerprints['device_id'],
            "newRisk": True,
            "token": token,
            "requestSource": "neul-next",
            "ctoken": self.token_generator.generate_ctoken(),
            "version": "1.1.0"
        }
        logger.debug(f"CREATE: {json.dumps(payload, indent=4)}")
        
        if buyer_info:
            payload["buyer_info"] = json.dumps(buyer_info).replace("'", "\\'")
        if deliver_info:
            payload["deliver_info"] = deliver_info
        if buyer and tel:
            if "buyer_info" in payload:
                del payload["buyer_info"]
            payload["buyer"] = buyer
            payload["tel"] = tel

        # URL中携带ptoken
        url = f"https://show.bilibili.com/api/ticket/order/createV2?project_id={project_id}&ptoken={real_ptoken}"
        
        # 添加风控头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Gaia-Vtoken": f"fake_gaia_{random.randint(100000, 999999)}"
        })
        
        # logger.debug(f"ctoken: {real_ctoken}\nptoken: {real_ptoken}")
        return self._make_api_call('POST', url, mobile_headers, json_data=payload)

    def gaia_vgate_register( self, prepare_json: "prepareJson") -> dict:
        url = f"https://api.bilibili.com/x/gaia-vgate/v1/register"
        payload = {
            'data': prepare_json["data"]["ga_data"]["riskParams"],
        }
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        return self._make_api_call('POST', url, mobile_headers, json_data=payload)
        
    def my_info(self,  ) -> "myInfoJson":
        url = 'https://api.bilibili.com/x/space/v2/myinfo?web_location=333.1387'
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        return self._make_api_call('GET', url, mobile_headers)

    def create_status(self, project_id: str, pay_token: str, order_id: Optional[str] = None,) -> "createStatusJson":
        url = (
            "https://show.bilibili.com/api/ticket/order/createstatus?project_id="
            + str(project_id)
            + "&token="
            + pay_token
            + "&timestamp="
            + str(int(time.time() * 1000))
        )
        if order_id:
            url += "&orderId=" + str(order_id)
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        return self._make_api_call('GET', url, mobile_headers)
    
    def project_info_by_date(self, project_id: str, date: str) -> "ProjectInfoByDateJson":
        url = f'https://show.bilibili.com/api/ticket/project/infoByDate?id={project_id}&date={date}'
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        return self._make_api_call('GET', url, mobile_headers)


    def logout(self):        
        url = "https://passport.bilibili.com/login/exit/v2"
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        data={
            "biliCSRF": self.headers["Cookie"][
                self.headers["Cookie"].index("bili_jct") + 9 : self.headers[
                    "Cookie"
                ].index("bili_jct")
                + 41
            ]
        }
        return self._make_api_call('POST', url, mobile_headers, json_data=data)
    
            
            
    @staticmethod
    def qr_login() -> Optional[str]:
        
        def cookie(cookies) -> str:
            lst = []
            for item in cookies.items():
                lst.append(f"{item[0]}={item[1]}")
            cookie_str = ";".join(lst)
            return cookie_str
                
        try:
            # 使用设备配置文件中的设备信息
            from app.device_config import create_device_fingerprint_with_config
            device_info = create_device_fingerprint_with_config()
            if not device_info:
                logger.error("无法获取设备配置信息")
                return None
            
            # 构建真实的移动端请求头
            mobile_headers = {
                "User-Agent": device_info['user_agent'],
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://www.bilibili.com/",
                "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
                # 添加设备指纹头
                "X-Bili-Device-Fp": device_info['device_id'],
                "X-Bili-Canvas-Fp": device_info['canvas_fp'][:16],
                "X-Bili-WebGL-Fp": device_info['webgl_fp'][:16],
            }
            session = requests.session()
            
            # 在session中设置真实的设备信息
            session.cookies.set('b_nut', str(int(time.time())), domain='.bilibili.com')
            session.cookies.set('buvid3', f"{device_info['device_id']}infoc", domain='.bilibili.com')
            session.cookies.set('buvid4', f"u{device_info['device_id'][:8]}-{device_info['device_id'][8:]}-{int(time.time()*1000)}-{device_info['device_id'][8:16]}infoc", domain='.bilibili.com')
            session.cookies.set('_uuid', device_info['device_id'].lower(), domain='.bilibili.com')
            
            # 更新请求头，添加设备相关信息
            mobile_headers.update({
                "X-Bili-Gaia-Vtoken": f"fake_gaia_{random.randint(100000, 999999)}",
                "X-Bili-Device-Req-Json": json.dumps({
                    "platform": "ios",
                    "version": "8.48.0",
                    "device_type": device_info['model'],
                    "network": "wifi",
                    "device_id": device_info['device_id'],
                    "canvas_fp": device_info['canvas_fp'][:16],
                    "webgl_fp": device_info['webgl_fp'][:16],
                    "screen_resolution": device_info['resolution']
                })
            })
            
            session.get("https://www.bilibili.com/", headers=mobile_headers)
            generate = session.get("https://passport.bilibili.com/x/passport-login/web/qrcode/generate", headers=mobile_headers).json()

            if generate["code"] != 0:
                logger.error("获取二维码失败，请检查网络连接")
                return None

            url = generate["data"]["url"]
            qrcode_key = generate["data"]["qrcode_key"]

            # 生成二维码并保存到文件
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 保存二维码到文件
            qr_file = Path("./login_qrcode.png")
            img.save(qr_file)
            logger.opt(colors=True).info(f"<green>二维码已保存为 {qr_file.name}，请手动打开此文件扫描登录</green>")
            logger.opt(colors=True).info("<yellow>请使用哔哩哔哩 App 扫描二维码登录</yellow>")

            while True:
                time.sleep(1)
                try:
                    poll_url = f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?source=main-fe-header&qrcode_key={qrcode_key}"
                    req = session.get(poll_url, headers=mobile_headers)
                    check = req.json()["data"]
                except Exception as e:
                    logger.error(f"轮询登录状态失败: {e}")
                    return None
                
                if check["code"] == 0:
                    # 登录成功
                    logger.opt(colors=True).info("<green>登录成功!</green>")
                    cookies = requests.utils.dict_from_cookiejar(session.cookies)
                    return cookie(cookies)
                    
                elif check["code"] == 86101:
                    pass
                elif check["code"] == 86090:
                    pass
                elif check["code"] in [86083, 86038]:
                    logger.error(f"二维码登录失败: {check.get('message', '未知错误')}")
                    return None
                else:
                    logger.error(f"未知登录状态: {check}")
                    return None

        
        except Exception as e:
            logger.debug(f"扫码登录过程中出现错误: {e}")
            logger.debug(traceback.format_exc())
            return None
            
        finally:
            # 清理二维码文件
            try:
                qr_file = Path("./login_qrcode.png")
                if qr_file.exists():
                    qr_file.unlink()
                    logger.debug("登录二维码文件已清理")
            except Exception as e:
                logger.debug(f"清理二维码文件失败: {e}")
            
            
            
            
    
            
            
