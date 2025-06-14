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


from .log import logger
import yaml


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
        # 使用移动端 User-Agent (基于你的抓包数据)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/621.2.5.10.10 (KHTML, like Gecko) Mobile/22F76 BiliApp/84800100 os/ios model/iPhone 16 Pro Max mobi_app/iphone build/84800100 osVer/18.5 network/2 channel/AppStore Buvid/YC45E6C974DE0A5D43D28E060E5F0779661D c_locale/zh-Hans_CN s_locale/zh_CN sessionID/d11718ec disable_rcmd/0 timezone/Asia/Shanghai utcOffset/+08:00 isDaylightTime/0 alwaysTranslate/0 ipRegion/CN legalRegion/CN themeId/1 sh/62 mallVersion/8480000 mVersion/309 flutterNotch/1 magent=BILI_H5_IOS_18.5_8.48.0_84800100",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://show.bilibili.com",
            "Referer": "https://show.bilibili.com/",
            "Cookie": cookie,
        }
        
    def set_cookie(self, cookie: str) -> None:
        self.headers["Cookie"] = cookie
        
    @staticmethod
    def _make_api_call(method: str, url: str, headers: dict, json=None, params=None, timeout: int = 120) -> Optional[dict]:
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            elif method.upper() == 'POST':
                response = requests.post(
                    url,
                    headers=headers,
                    json=json,  # 用于JSON数据
                    timeout=timeout
                )
                try:
                    logger.debug(f"POST {url} {json}")
                    logger.debug(f"Response: {response.text}")
                    logger.debug(f"Response: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error logging response: {e}")
            
            response.raise_for_status()  # 检查HTTP错误
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {url}: {e}")
            raise

    def project(self, project_id)-> "ProjectJson":
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return Api._make_api_call('GET', f'https://show.bilibili.com/api/ticket/project/getV2?id={project_id}', mobile_headers)

    def buyer(self,)->"BuyerJson":
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return Api._make_api_call('GET', "https://show.bilibili.com/api/ticket/buyer/list?is_default", mobile_headers)

    def address(self, )-> "AddressJson":
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return Api._make_api_call('GET', "https://show.bilibili.com/api/ticket/addr/list", mobile_headers)

    def confirm(self, project_id, token, voucher: str = "", request_source: str = "h5") -> "confirmJson":
        url = f"https://show.bilibili.com/api/ticket/order/confirmInfo?token={token}&voucher={voucher}&project_id={project_id}&requestSource={request_source}"
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return Api._make_api_call('GET', url, mobile_headers)

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
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        
        return Api._make_api_call('POST', url, mobile_headers, json=payload)

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
            "deviceId": "",
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
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })

        url = f"https://show.bilibili.com/api/ticket/order/createV2?project_id={project_id}"
        return Api._make_api_call('POST', url, mobile_headers, json=payload)

    def gaia_vgate_register( self, prepare_json: "prepareJson") -> dict:
        url = f"https://api.bilibili.com/x/gaia-vgate/v1/register"
        payload = {
            'data': prepare_json["data"]["ga_data"]["riskParams"],
        }
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return Api._make_api_call('POST', url, mobile_headers, json=payload)

    def my_info(self,  ) -> "myInfoJson":
        url = 'https://api.bilibili.com/x/space/v2/myinfo?web_location=333.1387'
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return Api._make_api_call('GET', url, mobile_headers)

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
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return Api._make_api_call('GET', url, mobile_headers)
    
    def project_info_by_date(self, project_id: str, date: str) -> "ProjectInfoByDateJson":
        url = f'https://show.bilibili.com/api/ticket/project/infoByDate?id={project_id}&date={date}'
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return Api._make_api_call('GET', url, mobile_headers)


    def logout(self):        
        url = "https://passport.bilibili.com/login/exit/v2"
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        data={
            "biliCSRF": self.headers["Cookie"][
                self.headers["Cookie"].index("bili_jct") + 9 : self.headers[
                    "Cookie"
                ].index("bili_jct")
                + 41
            ]
        }
        return Api._make_api_call('POST', url, mobile_headers, json=data)
    
            
            
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
            
            
            
            
    
            
            
