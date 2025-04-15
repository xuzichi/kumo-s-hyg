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
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:52.0) Gecko/20100101 Firefox/52.0",
            "Referer": "https://show.bilibili.com/",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Cookie": cookie,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "",
            "Connection": "keep-alive"
        }
        
    def set_cookie(self, cookie: str) -> None:
        self.headers["Cookie"] = cookie
        
    @staticmethod
    def _make_api_call(method: str, url: str, headers: dict, data=None, params=None, timeout: int = 120) -> Optional[dict]:
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, data=data, timeout=timeout)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed for {url}: {e}")
            return None

    def project(self, project_id)-> "ProjectJson":
        return Api._make_api_call('GET', f'https://show.bilibili.com/api/ticket/project/getV2?id={project_id}', self.headers)

    def buyer(self,)->"BuyerJson":
        return Api._make_api_call('GET', "https://show.bilibili.com/api/ticket/buyer/list?is_default", self.headers)

    def address(self, )-> "AddressJson":
        return Api._make_api_call('GET', "https://show.bilibili.com/api/ticket/addr/list", self.headers)

    def confirm(self, project_id, token, voucher: str = "", request_source: str = "pc-new") -> "confirmJson":
        url = f"https://show.bilibili.com/api/ticket/order/confirmInfo?token={token}&voucher={voucher}&project_id={project_id}&requestSource={request_source}"
        return Api._make_api_call('GET', url, self.headers)

    def prepare(self,  project_id, count, screen_id, sku_id) -> "prepareJson":
        url = f"https://show.bilibili.com/api/ticket/order/prepare?project_id={project_id}"
        payload = {
            "project_id": str(project_id),
            "count": str(count),
            "order_type": "1",
            "screen_id": str(screen_id),
            "sku_id": str(sku_id),
            "token": "",
            "newRisk": "true",
            "ignoreRequestLimit": "true",
            "requestSource": "neul-next",
        }
        json_payload = urlencode(payload).replace("%27true%27", "true").replace("%27", "%22").encode()
        _headers = self.headers.copy()
        _headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return Api._make_api_call('POST', url, _headers, data=json_payload)

    def create(self, project_id, token, screen_id, sku_id, count, pay_money, buyer_info, deliver_info=None, buyer=None, tel=None) -> "createJson":
        payload = {
            "buyer_info": buyer_info,
            "count": str(count),
            "pay_money": pay_money * count,
            "project_id": str(project_id),
            "screen_id": screen_id,
            "sku_id": sku_id,
            "timestamp": int(round(time.time() * 1000)),
            "token": token,
            "deviceId": "",
        }
        if deliver_info:
            payload["deliver_info"] = deliver_info
        if buyer and tel:
            del payload["buyer_info"]
            payload["buyer"] = buyer
            payload["tel"] = tel

        json_payload = urlencode(payload).replace("%27true%27", "true").replace("%27", "%22").encode()
        url = f"https://show.bilibili.com/api/ticket/order/createV2?project_id={project_id}"
        _headers = self.headers.copy()
        _headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return Api._make_api_call('POST', url, _headers, data=json_payload)

    def gaia_vgate_register( self, prepare_json: "prepareJson") -> dict:
        url = f"https://api.bilibili.com/x/gaia-vgate/v1/register"
        payload = {
            'data': prepare_json["data"]["ga_data"]["riskParams"],
        }
        json_payload = urlencode(payload).replace("%27true%27", "true").replace("%27", "%22").encode()
        _headers = self.headers.copy()
        _headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return Api._make_api_call('POST', url, _headers, data=json_payload)

    def my_info(self,  ) -> "myInfoJson":
        url = 'https://api.bilibili.com/x/space/v2/myinfo?web_location=333.1387'
        return Api._make_api_call('GET', url, self.headers)

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
        _headers = self.headers.copy()
        _headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
        return Api._make_api_call('GET', url, _headers)
    
    def project_info_by_date(self, project_id: str, date: str) -> "ProjectInfoByDateJson":
        url = f'https://show.bilibili.com/api/ticket/project/infoByDate?id={project_id}&date={date}'
        return Api._make_api_call('GET', url, self.headers)

    @staticmethod
    def qr_login() -> str:
        
        def cookie(cookies) -> str:
            lst = []
            for item in cookies.items():
                lst.append(f"{item[0]}={item[1]}")
            cookie_str = ";".join(lst)
            return cookie_str
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        session = requests.session()
        session.get("https://www.bilibili.com/", headers=headers)
        generate = session.get("https://passport.bilibili.com/x/passport-login/web/qrcode/generate",headers=headers,).json()

        if generate["code"] != 0:
            logger.error("获取二维码失败，请检查网络连接")
            return None

        url = generate["data"]["url"]
        qrcode_key = generate["data"]["qrcode_key"]

        qr = qrcode.QRCode()
        qr.add_data(url)
        qr.print_ascii(invert=True)
        img = qr.make_image()
        img.show()
        logger.info("请使用哔哩哔哩 App 扫描二维码登录")

        while True:
            time.sleep(1)
            poll_url = f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?source=main-fe-header&qrcode_key={qrcode_key}"
            req = session.get(poll_url, headers=headers)
            check = req.json()["data"]
            if check["code"] == 0:
                logger.success("登录成功")
                cookies = requests.utils.dict_from_cookiejar(session.cookies)
                return cookie(cookies)
            elif check["code"] == 86101:
                pass  # 等待扫描
            elif check["code"] == 86090:
                logger.info("等待确认")
            elif check["code"] in [86083, 86038]:
                logger.error(check["message"])
                return None # 重新登录
            else:
                logger.error(check)
                return None # 重新登录
            
            
            
    
            
            