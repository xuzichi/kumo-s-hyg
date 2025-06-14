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

from .log import logger
from .captcha import CaptchaHandler
import yaml


class DeviceFingerprint:
    """轻量级设备指纹生成器"""
    def __init__(self):
        # iPhone X以后的所有机型
        self.iphone_models = [
            'iPhone10,3', 'iPhone10,6',  # iPhone X
            'iPhone11,2', 'iPhone11,4', 'iPhone11,6', 'iPhone11,8',  # iPhone XS/XS Max/XR
            'iPhone12,1', 'iPhone12,3', 'iPhone12,5',  # iPhone 11/11 Pro/11 Pro Max
            'iPhone13,1', 'iPhone13,2', 'iPhone13,3', 'iPhone13,4',  # iPhone 12 mini/12/12 Pro/12 Pro Max
            'iPhone14,2', 'iPhone14,3', 'iPhone14,4', 'iPhone14,5', 'iPhone14,7', 'iPhone14,8',  # iPhone 13/14系列
            'iPhone15,2', 'iPhone15,3', 'iPhone15,4', 'iPhone15,5',  # iPhone 14 Pro/15系列
            'iPhone16,1', 'iPhone16,2',  # iPhone 15 Pro/Pro Max
            'iPhone17,1', 'iPhone17,2', 'iPhone17,3', 'iPhone17,4'   # iPhone 16系列
        ]
        self.model = random.choice(self.iphone_models)
        
    def get_all_fingerprints(self):
        """生成所有设备指纹信息"""
        version = f"18.{random.randint(0,5)}.{random.randint(0,3)}"
        ua = f"Mozilla/5.0 (iPhone; CPU iPhone OS {version.replace('.', '_')} like Mac OS X) AppleWebKit/{random.randint(605,620)}.1.{random.randint(10,50)} (KHTML, like Gecko) Mobile/22F76 BiliApp/84800100 os/ios model/{self.model} mobi_app/iphone build/84800100 osVer/{version} network/wifi channel/AppStore"
        
        return {
            'user_agent': ua,
            'device_id': hashlib.md5(f"iPhone{self.model}{time.time()}".encode()).hexdigest()[:16].upper(),
            'buvid': f"XU{hashlib.md5(str(random.random()).encode()).hexdigest()[:8].upper()}{hashlib.md5(str(random.random()).encode()).hexdigest()[:24]}",
            'canvas_fp': ''.join(random.choices('0123456789abcdef', k=32)),
            'webgl_fp': ''.join(random.choices('0123456789abcdef', k=32)),
            'fe_sign': ''.join(random.choices('0123456789abcdef', k=32)),
            'brand': 'iPhone',
            'model': self.model
        }


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
        }
        
        # 存储设备指纹信息
        self.device_fingerprints = fingerprints
        logger.debug(f"设备指纹已生成: {fingerprints['device_id'][:8]}...")
        logger.debug(f"动态UA: {fingerprints['user_agent'][:50]}...")
            
    

        
    def set_cookie(self, cookie: str) -> None:
        self.headers["Cookie"] = cookie
        
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
                    "network": "wifi"
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
        url = f"https://show.bilibili.com/api/ticket/order/confirmInfo?token={token}&voucher={voucher}&project_id={project_id}&requestSource={request_source}"
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        return self._make_api_call('GET', url, mobile_headers)

    def prepare(self,  project_id, count, screen_id, sku_id) -> "prepareJson":
        url = f"https://show.bilibili.com/api/ticket/order/prepare?project_id={project_id}"
        payload = {
            "project_id": project_id,
            "count": count,
            "order_type": 1,
            "screen_id": screen_id,
            "sku_id": sku_id,
            "token": "",
            "newRisk": True,
            "ignoreRequestLimit": True,
            "requestSource": "h5",  # 移动端使用 h5
        }
        
        # 添加移动端特有的请求头  
        mobile_headers = self.headers.copy()
        
        return self._make_api_call('POST', url, mobile_headers, json_data=payload)

    def create(self, project_id, token, screen_id, sku_id, count, pay_money, buyer_info, deliver_info=None, buyer=None, tel=None) -> "createJson":
        logger.debug(f" project_id: {project_id} token: {token} screen_id: {screen_id} sku_id: {sku_id} count: {count} pay_money: {pay_money} buyer_info: {buyer_info} deliver_info: {deliver_info} buyer: {buyer} tel: {tel}")
        
        payload = {
            "buyer_info": json.dumps(buyer_info).replace("'", "\\'"),
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
            "requestSource": "h5",  # 移动端使用 h5
        }
        if deliver_info:
            payload["deliver_info"] = deliver_info
        if buyer and tel:
            del payload["buyer_info"]
            payload["buyer"] = buyer
            payload["tel"] = tel

        # 添加移动端特有的请求头
        mobile_headers = self.headers.copy()

        url = f"https://show.bilibili.com/api/ticket/order/createV2?project_id={project_id}"
        return self._make_api_call('POST', url, mobile_headers, json_data=payload)

    def gaia_vgate_register( self, prepare_json: "prepareJson") -> dict:
        url = f"https://api.bilibili.com/x/gaia-vgate/v1/register"
        payload = {
            'data': prepare_json["data"]["ga_data"]["riskParams"],
        }
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        return self._make_api_call('POST', url, mobile_headers, json_data=payload)
    
    # ===== HOT项目专用函数 =====
    
    def hot_prepare(self, project_id, count, screen_id, sku_id) -> "prepareJson":
        """
        热门项目的prepare请求，携带假的ctoken
        """
        url = f"https://show.bilibili.com/api/ticket/order/prepare?project_id={project_id}"
        
        # 生成假的ctoken
        fake_ctoken = base64.b64encode(bytes([random.randint(1, 30), 0, random.randint(0, 5), 0, random.randint(0, 3), 0, 0xff, 0, random.randint(0, 5), 0, random.randint(0, 10), 0, 0xff, 0, 0xff, 0, random.randint(0, 5), 0, random.randint(1, 255), 0, 0, 0, 0, 0, 0, 0, 0xff, 0, 0, 0, 0xff, 0])).decode('utf-8')
        
        payload = {
            "project_id": project_id,
            "count": count,
            "order_type": 1,
            "screen_id": screen_id,
            "sku_id": sku_id,
            "token": fake_ctoken,  # 使用假的ctoken
            "newRisk": True,
            "ignoreRequestLimit": True,
            "requestSource": "neul-next",  # 热门项目使用neul-next
        }
        
        # 添加风控头
        mobile_headers = self.headers.copy()
        
        logger.info(f"热门项目Prepare请求，携带假ctoken: {fake_ctoken[:20]}...")
        return self._make_api_call('POST', url, mobile_headers, json_data=payload)
    
    def hot_create(self, project_id, token, screen_id, sku_id, count, pay_money, buyer_info, ptoken="", deliver_info=None, buyer=None, tel=None) -> "createJson":
        """
        热门项目的create请求，携带ctoken和ptoken
        """
        logger.debug(f"HOT CREATE: project_id: {project_id} token: {token} screen_id: {screen_id} sku_id: {sku_id} count: {count} pay_money: {pay_money}")
        
        # 生成假的ctoken和ptoken
        fake_ctoken = base64.b64encode(bytes([random.randint(1, 30), 0, random.randint(0, 5), 0, random.randint(0, 3), 0, 0xff, 0, random.randint(0, 5), 0, random.randint(0, 10), 0, 0xff, 0, 0xff, 0, random.randint(0, 5), 0, random.randint(1, 255), 0, 0, 0, 0, 0, 0, 0, 0xff, 0, 0, 0, 0xff, 0])).decode('utf-8')
        
        if not ptoken:
            fake_ptoken = base64.b64encode(bytes([0, random.randint(1, 30), 0, 0xff, random.randint(0, 5), 0, 0x04, 0, 0x09, 0, random.randint(0, 5), 0, 0x58, 0, 0x09, 0, random.randint(0, 5), 0, random.randint(1, 255), 0, 0, 0, 0, 0, 0, 0, 0x06, 0, random.randint(0, 10), 0, random.randint(80, 120), 0])).decode('utf-8')
        else:
            fake_ptoken = ptoken
        
        payload = {
            "buyer_info": json.dumps(buyer_info).replace("'", "\\'"),
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
            "requestSource": "neul-next",  # 热门项目使用neul-next
            "ctoken": fake_ctoken,  # 添加假的ctoken
            "version": "1.1.0"
        }
        
        if deliver_info:
            payload["deliver_info"] = deliver_info
        if buyer and tel:
            del payload["buyer_info"]
            payload["buyer"] = buyer
            payload["tel"] = tel

        # 添加风控头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Gaia-Vtoken": f"fake_gaia_{random.randint(100000, 999999)}"  # 假的gaia token
        })

        # URL中携带ptoken
        url = f"https://show.bilibili.com/api/ticket/order/createV2?project_id={project_id}&ptoken={fake_ptoken}"
        
        logger.debug(f"热门项目Create请求，携带假ctoken: {fake_ctoken[:20]}... 和假ptoken: {fake_ptoken[:20]}...")
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
            # 使用移动端请求头
            mobile_headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/621.2.5.10.10 (KHTML, like Gecko) Mobile/22F76 BiliApp/84800100 os/ios model/iPhone 16 Pro Max mobi_app/iphone build/84800100 osVer/18.5 network/2 channel/AppStore Buvid/YC45E6C974DE0A5D43D28E060E5F0779661D c_locale/zh-Hans_CN s_locale/zh_CN sessionID/d11718ec disable_rcmd/0 timezone/Asia/Shanghai utcOffset/+08:00 isDaylightTime/0 alwaysTranslate/0 ipRegion/CN legalRegion/CN themeId/1 sh/62 mallVersion=8480000 mVersion=309 flutterNotch=1 magent=BILI_H5_IOS_18.5_8.48.0_84800100",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://www.bilibili.com/",
                "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
            }
            session = requests.session()
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
            
            
            
            
    
            
            
