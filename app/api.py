import base64
import json
from pathlib import Path
import time
import ssl
import threading
import traceback
from urllib.parse import urlencode
import requests
from typing import Optional, List, Dict, TYPE_CHECKING
from dataclasses import dataclass
import random
import hashlib
import uuid
import struct
import re
import urllib.parse
import hmac
import functools
import bili_ticket_gt_python

from .utils.log import logger
from .utils.file_utils import file_utils
from .utils.qrcode_terminal import qr_terminal_draw, render_3by2
from noneprompt import InputPrompt, CancelledError

if TYPE_CHECKING:
    from .client import Client


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

@dataclass
class SearchProjectJson:
    pass


class API:
    """B站票务API接口封装"""
    
    def __init__(self, client: "Client"):
        self.client = client
    
    def project(self, project_id) -> "ProjectJson":
        # 使用移动端请求头
        mobile_headers = self.client.headers.copy()
        return self.client._make_api_call('GET', f'https://show.bilibili.com/api/ticket/project/getV2?id={project_id}', mobile_headers)

    def buyer(self) -> "BuyerJson":
        # 使用移动端请求头
        mobile_headers = self.client.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return self.client._make_api_call('GET', "https://show.bilibili.com/api/ticket/buyer/list?is_default", mobile_headers)

    def address(self) -> "AddressJson":
        # 使用移动端请求头
        mobile_headers = self.client.headers.copy()
        mobile_headers.update({
            "X-Bili-Trace-Id": f"{int(time.time() * 1000)}:{int(time.time() * 1000)}:0:0",
        })
        return self.client._make_api_call('GET', "https://show.bilibili.com/api/ticket/addr/list", mobile_headers)

    def confirm(self, project_id, token, voucher: str = "", request_source: str = "h5") -> "confirmJson":
        """
        获取订单确认信息
        """
        # 使用已捕获的 ptoken
        real_ptoken = self.client.ptoken
        url = (
            f"https://show.bilibili.com/api/ticket/order/confirmInfo"
            f"?token={token}"
            f"&voucher={voucher}"
            f"&projectId={project_id}"
            f"&ptoken={real_ptoken}"
            f"&project_id={project_id}"
            f"&requestSource={request_source}"
        )
        mobile_headers = self.client.headers.copy()
        return self.client._make_api_call('GET', url, mobile_headers)

    def prepare(self, project_id, count, screen_id, sku_id) -> "prepareJson":
        url = f"https://show.bilibili.com/api/ticket/order/prepare?project_id={project_id}"
        
        # 刷新bili_ticket以降低风控概率
        self.ensure_bili_ticket()
        
        # 从设备指纹获取分辨率
        res = self.client.device_fingerprint.resolution
        width, height = map(int, res.split('x'))

        prepare_token = self.client._build_ctoken(
            inner_width=width,
            inner_height=height,
            outer_width=width,
            outer_height=height,
            screen_width=width,
        )

        # 缓存以便后续 create 使用相同的 ctoken
        self.client.ctoken = prepare_token
        
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
        
        mobile_headers = self.client.headers.copy()
        result = self.client._make_api_call('POST', url, mobile_headers, json_data=payload)
        
        # 从prepare响应中专门提取ptoken
        try:
            if isinstance(result, dict):
                if "ptoken" in result and isinstance(result["ptoken"], str):
                    self.client.ptoken = result["ptoken"]
                    logger.debug(f"从prepare响应中捕获ptoken: {self.client.ptoken}")
                elif isinstance(result.get("data"), dict) and isinstance(result["data"].get("ptoken"), str):
                    self.client.ptoken = result["data"].get("ptoken")
                    logger.debug(f"从prepare响应中捕获ptoken: {self.client.ptoken}")
        except Exception as e:
            logger.error(f"从prepare响应中提取ptoken失败: {e}")
            
        return result

    def create(self, project_id, token, screen_id, sku_id, count, pay_money, buyer_info, ptoken="", deliver_info=None, buyer=None, tel=None) -> "createJson":             
        # 优先使用显式传入，其次使用已保存的 ptoken
        real_ptoken = ptoken or self.client.ptoken
        
        # 刷新bili_ticket以降低风控概率
        self.ensure_bili_ticket()
        
        # 从设备指纹获取分辨率
        res = self.client.device_fingerprint.resolution
        width, height = map(int, res.split('x'))
        
        payload = {
            "count": count,
            "pay_money": pay_money * count,
            "project_id": project_id,
            "screen_id": screen_id,
            "sku_id": sku_id,
            "timestamp": int(round(time.time() * 1000)),
            "order_type": 1,
            "deviceId": self.client.device_fingerprint.device_id,
            "newRisk": True,
            "token": token,
            "requestSource": "neul-next",
            "ctoken": self.client.ctoken or self.client._build_ctoken(
                inner_width=width,
                inner_height=height,
                outer_width=width,
                outer_height=height,
                screen_width=width,
            ),
            "version": getattr(self.client.device_fingerprint, "bili_app_version", "8.48.0"),
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
        mobile_headers = self.client.headers.copy()
        mobile_headers.update({
            "X-Bili-Gaia-Vtoken": f"fake_gaia_{random.randint(100000, 999999)}"
        })
        
        # logger.debug(f"ctoken: {real_ctoken}\nptoken: {real_ptoken}")
        return self.client._make_api_call('POST', url, mobile_headers, json_data=payload)

    def gaia_vgate_register(self, prepare_json: "prepareJson") -> dict:
        url = f"https://api.bilibili.com/x/gaia-vgate/v1/register"
        payload = {
            'data': prepare_json["data"]["ga_data"]["riskParams"],
        }
        # 使用移动端请求头
        mobile_headers = self.client.headers.copy()
        return self.client._make_api_call('POST', url, mobile_headers, json_data=payload)
        
    def my_info(self) -> "myInfoJson":
        url = 'https://api.bilibili.com/x/space/v2/myinfo?web_location=333.1387'
        # 使用移动端请求头
        mobile_headers = self.client.headers.copy()
        return self.client._make_api_call('GET', url, mobile_headers)

    def create_status(self, project_id: str, pay_token: str, order_id: Optional[str] = None) -> "createStatusJson":
        """
        查询订单创建状态
        """
        url = (
            f"https://show.bilibili.com/api/ticket/order/createstatus?project_id={project_id}"
            f"&token={pay_token}"
            f"&timestamp={int(time.time() * 1000)}"
        )
        if order_id:
            url += f"&orderId={order_id}"
        # 使用移动端请求头
        mobile_headers = self.client.headers.copy()
        return self.client._make_api_call('GET', url, mobile_headers)
    
    def project_info_by_date(self, project_id: str, date: str) -> "ProjectInfoByDateJson":
        url = f'https://show.bilibili.com/api/ticket/project/infoByDate?id={project_id}&date={date}'
        # 使用移动端请求头
        mobile_headers = self.client.headers.copy()
        return self.client._make_api_call('GET', url, mobile_headers)

    def search_project(self, keyword: str, page: int = 1, pagesize: int = 16) -> "SearchProjectJson":
        """
        根据关键词搜索演出项目
        
        参数:
        -----
        keyword : str
            搜索关键词
        page : int
            页码，默认为1
        pagesize : int
            每页数量，默认为16
        
        返回:
        -----
        SearchProjectJson
            搜索结果
        """
        # 使用新的搜索API
        url = 'https://show.bilibili.com/api/ticket/search/list'
        params = {
            'version': '134',
            'keyword': keyword,
            'pagesize': pagesize,
            'page': page,
            'platform': 'web',
        }
        
        # 使用移动端请求头
        mobile_headers = self.client.headers.copy()
        return self.client._make_api_call('GET', url, mobile_headers, params=params)

    def logout(self):
        """
        退出登录
        """
        url = "https://passport.bilibili.com/login/exit/v2"
        payload = {
            "biliCSRF": "",
            "gourl": "https://www.bilibili.com/"
        }
        
        mobile_headers = self.client.headers.copy()
        return self.client._make_api_call('POST', url, mobile_headers, json_data=payload)

    def get_bili_ticket(self):
        """
        获取bili_ticket，用于增强安全性
        """
        # 准备请求数据
        timestamp = int(time.time())
        # 使用HMAC-SHA256算法计算hexsign，密钥为"XgwSnGZ1p"，消息为"ts"加时间戳
        hexsign = hmac.new(
            "XgwSnGZ1p".encode('utf-8'), 
            f"ts{timestamp}".encode('utf-8'), 
            hashlib.sha256
        ).hexdigest()
        
        # 从cookie中提取csrf
        csrf = ""
        if "Cookie" in self.client.headers and self.client.headers["Cookie"]:
            for cookie_item in self.client.headers["Cookie"].split(";"):
                if cookie_item.strip().startswith("bili_jct="):
                    csrf = cookie_item.strip().split("=", 1)[1]
                    break
        
        # 构造URL参数
        params = {
            "key_id": "ec02",
            "hexsign": hexsign,
            "context[ts]": str(timestamp),
            "csrf": csrf
        }
        
        # 构造完整URL
        base_url = "https://api.bilibili.com/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket"
        url_params = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{base_url}?{url_params}"
        
        # 使用简单的请求头
        mobile_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        }
        
        try:
            # 使用client内部的_make_api_call方法，但传入自定义headers
            result = self.client._make_api_call('POST', full_url, mobile_headers)
            
            if result and result.get("code") == 0:
                ticket = result.get("data", {}).get("ticket", "")
                if ticket:
                    self.client.bili_ticket = ticket
                    self.client.bili_ticket_last_refresh = time.time()
                    logger.debug(f"获取bili_ticket成功: {ticket[:20]}...")
                    
                    # 更新Cookie中的bili_ticket
                    if "Cookie" in self.client.headers and self.client.headers["Cookie"]:
                        cookie_str = self.client.headers["Cookie"]
                        items = [c.strip() for c in cookie_str.split(";") if c.strip() and not c.strip().startswith("bili_ticket=")]
                        items.append(f"bili_ticket={ticket}")
                        self.client.headers["Cookie"] = "; ".join(items)
                    else:
                        self.client.headers["Cookie"] = f"bili_ticket={ticket}"
                    
                    return ticket
                else:
                    logger.warning("bili_ticket响应中无ticket字段")
            else:
                if result:
                    logger.debug(f"获取bili_ticket失败: {result}")
                    logger.warning(f"获取bili_ticket失败: {result.get('message', '未知错误')}")
                else:
                    logger.warning("bili_ticket请求失败: 无响应")
                
        except Exception as e:
            logger.error(f"获取bili_ticket异常: {e}")
        
        return None

    def ensure_bili_ticket(self, force_refresh=False):
        """
        确保bili_ticket有效，如果过期或不存在则重新获取
        
        参数:
        -----
        force_refresh : bool
            是否强制刷新，默认为False
        """
        current_time = time.time()
        
        # 检查是否需要刷新（每1小时刷新一次，或强制刷新）
        if (force_refresh or 
            not self.client.bili_ticket or 
            current_time - self.client.bili_ticket_last_refresh > 3600):
            
            logger.debug("bili_ticket需要刷新")
            return self.get_bili_ticket()
        else:
            logger.debug("bili_ticket仍然有效")
            return self.client.bili_ticket

    def enc_wbi(self, params: dict):
        """
        WBI签名加密，用于某些需要签名的接口
        
        参数:
        -----
        params : dict
            需要签名的参数字典
            
        返回:
        -----
        dict
            添加了w_rid签名的参数字典
        """
        # 如果没有wbi密钥，先获取
        if not self.client.wbi_img_key or not self.client.wbi_sub_key:
            try:
                resp = requests.get("https://api.bilibili.com/x/web-interface/nav", 
                                  headers=self.client.headers, timeout=10)
                if resp.status_code == 200:
                    nav_data = resp.json()
                    if nav_data.get("code") == 0:
                        wbi_img = nav_data.get("data", {}).get("wbi_img", {})
                        self.client.wbi_img_key = wbi_img.get("img_url", "").split("/")[-1].split(".")[0]
                        self.client.wbi_sub_key = wbi_img.get("sub_url", "").split("/")[-1].split(".")[0]
            except Exception as e:
                logger.warning(f"获取WBI密钥失败: {e}")
                return params
        
        def get_mixin_key(orig: str):
            """获取混合密钥"""
            mixin_key_enc_tab = [
                46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
                33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
                61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
                36, 20, 34, 44, 52
            ]
            return "".join([orig[i] for i in mixin_key_enc_tab])[:32]
        
        if not self.client.wbi_img_key or not self.client.wbi_sub_key:
            return params
            
        mixin_key = get_mixin_key(self.client.wbi_img_key + self.client.wbi_sub_key)
        curr_time = round(time.time())
        params["wts"] = curr_time
        
        # 按key排序并拼接
        query = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        
        # 计算MD5
        wbi_sign = hashlib.md5((query + mixin_key).encode()).hexdigest()
        params["w_rid"] = wbi_sign
        
        return params

    def qr_login(self, timeout: int = 180) -> Optional[str]:
        """
        二维码登录
        
        参数:
        -----
        timeout : int
            超时时间，默认180秒
            
        返回:
        -----
        Optional[str]
            登录成功返回cookie字符串，失败返回None
        """
        import requests
        
        try:
            session = requests.Session()
            # 使用self中的一部分设备信息
            # 先随个 设备
            from app.utils.virtual_device import create_virtual_device
            device = create_virtual_device()
            self.client.set_device(device)
            common_headers = {
                "User-Agent": self.client.headers["User-Agent"],
                "Referer": "https://www.bilibili.com/",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.bilibili.com",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }

            # 1. 生成二维码
            gen_resp = session.get(
                "https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
                params={"source": "main-fe"},
                timeout=30,
                headers=common_headers,
            )
            try:
                gen_json = gen_resp.json()
            except ValueError:
                logger.error(f"二维码接口响应不是有效JSON: {gen_resp.status_code} {gen_resp.text[:200]}")
                return None

            data = gen_json.get("data", {})
            qr_url = data.get("url")
            qr_key = data.get("qrcode_key")
            if not qr_url or not qr_key:
                logger.error("二维码信息缺失，无法继续登录")
                return None

            # 2. 生成并保存二维码到temp文件夹
            qr_terminal_draw(qr_url)
            # file_utils.save_qr_and_open_folder(qr_url, "bilibili_login_qr")
            logger.info("请使用 B 站客户端扫码并确认登录")
            # 3. 轮询扫码状态
            poll_url = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
            start_time = time.time()
            while time.time() - start_time < timeout:
                poll_resp = session.get(
                    poll_url,
                    params={"qrcode_key": qr_key},
                    timeout=30,
                    headers=common_headers,
                )
                poll_json = poll_resp.json()
                if poll_json.get("code") != 0:
                    logger.error(f"轮询接口异常: {poll_json.get('message')}")
                    return None

                poll_data = poll_json.get("data", {})
                status_code = poll_data.get("code")
                # 86101 未扫码, 86090 已扫码未确认, 86038 二维码已失效
                if status_code == 0:
                    # 登录成功
                    cookie_str = ""
                    cookies_list = poll_data.get("cookie_info", {}).get("cookies")
                    if cookies_list:
                        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies_list)
                    # 若接口未返回 cookie_info，则从 session.cookies 提取
                    if not cookie_str:
                        cookie_str = "; ".join([f"{c.name}={c.value}" for c in session.cookies])
                    logger.success("登录成功！")
                    
                    # 加载cookie
                    self.client.load_cookie(cookie_str)
                    
                    # 登录成功后获取bili_ticket增强安全性
                    try:
                        self.get_bili_ticket()
                    except Exception as e:
                        logger.warning(f"获取bili_ticket失败，但不影响登录: {e}")
                    
                    return cookie_str
                elif status_code == 86101:
                    # 等待扫码
                    pass
                elif status_code == 86090:
                    logger.info("二维码已扫码，请在手机端确认…")
                elif status_code == 86038:
                    logger.error("二维码已失效，请重新发起登录。")
                    return None

                time.sleep(2)

            logger.error("登录超时，已取消。")
            return None
        except KeyboardInterrupt:
            return None
        except Exception as e:
            logger.error(f"扫码登录异常: {e}")
            logger.debug(traceback.format_exc())
            return None
        finally:
            # 无论如何退出都清理二维码文件
            file_utils.clean_temp_files("bilibili_login_qr")

    def generate_click_position(self):
        """生成随机点击位置，用于模拟真实用户点击
        
        返回:
            dict: 包含点击位置信息的字典
        """
        import random
        click_position = {
            "x": random.randint(200, 400),
            "y": random.randint(750, 800),
            "origin": int(time.time() * 1000) - random.randint(100000, 200000),
            "now": int(time.time() * 1000),
        }
        return click_position
    def search_bws_project(self):
        """查询bws项目
        """
        # 从cookie中提取csrf
        csrf = ""
        if "Cookie" in self.client.headers and self.client.headers["Cookie"]:
            for cookie_item in self.client.headers["Cookie"].split(";"):
                if cookie_item.strip().startswith("bili_jct="):
                    csrf = cookie_item.strip().split("=", 1)[1]
                    break

        reserve_date = "20250711,20250712,20250713"
        url = ("https://api.bilibili.com/x/activity/bws/online/park/reserve/info"
            f"?csrf={csrf}"
            f"&reserve_date={reserve_date}"
            f"&reserve_type=-1")
        
        # 使用移动端请求头
        mobile_headers = self.client.headers.copy()
        return self.client._make_api_call('GET', url, mobile_headers)

    def create_bws_reserve(self, ticket_no, inter_reserve_id):

        # 从cookie中提取csrf
        csrf = ""
        if "Cookie" in self.client.headers and self.client.headers["Cookie"]:
            for cookie_item in self.client.headers["Cookie"].split(";"):
                if cookie_item.strip().startswith("bili_jct="):
                    csrf = cookie_item.strip().split("=", 1)[1]
                    break

        payload = {
            'csrf': csrf,
            'inter_reserve_id': inter_reserve_id,
            'ticket_no': ticket_no
        }
        logger.info(f"payload: {payload}")
        url = 'https://api.bilibili.com/x/activity/bws/online/park/reserve/do'
        mobile_headers = self.client.headers.copy()
        return self.client._make_api_call('POST', url, mobile_headers, params=payload)
