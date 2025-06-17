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
from typing import Optional, List, Dict, TYPE_CHECKING
from dataclasses import dataclass
import random
import hashlib
import uuid
import struct
import re
import urllib.parse

from app.virtual_device import create_virtual_device

from ..log import logger
from .gaia import GaiaHandler
import yaml

if TYPE_CHECKING:
    from ..account_manager import VirtualDevice


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


class Client:
    """对外暴露的客户端入口.

    兼容设计: 为了支持 `client.api.xxx` 的调用方式, 这里提供一个 `api` 属性指向当前实例自身。
    这样既能保持方法路径层级清晰, 又不必大幅改动现有实现。
    """

    def __init__(self) -> None:
        self.gaia_handler = GaiaHandler(self)
        self.cookie = None
        self.device = None
        self.buvid: str | None = None  # buvid1
        
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
        self.api = Client.API(self)
    
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
    
    def _make_api_call(self, method: str, url: str, headers: dict, json_data=None, params=None, timeout: int = 120) -> Optional[dict]:
        """增强的API调用方法，支持错误处理和风控检测"""
        try:
            # 动态更新请求头
            enhanced_headers = headers.copy()
            
            # 自动附带 x-risk-header（若已生成）
            if hasattr(self, "x_risk_header") and self.x_risk_header:
                enhanced_headers.setdefault("x-risk-header", self.x_risk_header)
            
            # 添加设备信息头（如果设备指纹可用）
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
                    logger.debug(f"Response: {response.text}")
                except Exception as e:
                    logger.error(f"Error logging response: {e}")
            
            response.raise_for_status()
            result = response.json()
            
            # 检查是否触发风控
            if result.get("code") == -401 and "ga_data" in result.get("data", {}):
                logger.warning("检测到风控验证，尝试自动处理...")
                risk_params = result["data"]["ga_data"]["riskParams"]
                if self.gaia_handler.handle_gaia_validation(risk_params):
                    logger.success("风控验证通过，重新请求...")
                    # 重新发起请求
                    return self._make_api_call(method, url, headers, json_data, params, timeout)
                else:
                    logger.error("风控验证失败")
            
            
            return result
            
        except requests.exceptions.RequestException as e:
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
        """
        获取订单确认信息
        """
        # 使用已捕获的 ptoken
        real_ptoken = self.ptoken
        url = (
            f"https://show.bilibili.com/api/ticket/order/confirmInfo"
            f"?token={token}"
            f"&voucher={voucher}"
            f"&projectId={project_id}"
            f"&ptoken={real_ptoken}"
            f"&project_id={project_id}"
            f"&requestSource={request_source}"
        )
        mobile_headers = self.headers.copy()
        return self._make_api_call('GET', url, mobile_headers)

    def prepare(self,  project_id, count, screen_id, sku_id) -> "prepareJson":
        url = f"https://show.bilibili.com/api/ticket/order/prepare?project_id={project_id}"
        
        # 从设备指纹获取分辨率
        res = self.device_fingerprint.resolution
        width, height = map(int, res.split('x'))

        prepare_token = self._build_ctoken(
            inner_width=width,
            inner_height=height,
            outer_width=width,
            outer_height=height,
            screen_width=width,
        )

        # 缓存以便后续 create 使用相同的 ctoken
        self.ctoken = prepare_token
        
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
        result = self._make_api_call('POST', url, mobile_headers, json_data=payload)
        
        # 从prepare响应中专门提取ptoken
        try:
            if isinstance(result, dict):
                if "ptoken" in result and isinstance(result["ptoken"], str):
                    self.ptoken = result["ptoken"]
                    logger.debug(f"从prepare响应中捕获ptoken: {self.ptoken}")
                elif isinstance(result.get("data"), dict) and isinstance(result["data"].get("ptoken"), str):
                    self.ptoken = result["data"].get("ptoken")
                    logger.debug(f"从prepare响应中捕获ptoken: {self.ptoken}")
        except Exception as e:
            logger.error(f"从prepare响应中提取ptoken失败: {e}")
            
        return result

    def create(self, project_id, token, screen_id, sku_id, count, pay_money, buyer_info, ptoken="", deliver_info=None, buyer=None, tel=None) -> "createJson":             
        # 优先使用显式传入，其次使用已保存的 ptoken
        real_ptoken = ptoken or self.ptoken
        
        # 从设备指纹获取分辨率
        res = self.device_fingerprint.resolution
        width, height = map(int, res.split('x'))
        
        payload = {
            "count": count,
            "pay_money": pay_money * count,
            "project_id": project_id,
            "screen_id": screen_id,
            "sku_id": sku_id,
            "timestamp": int(round(time.time() * 1000)),
            "order_type": 1,
            "deviceId": self.device_fingerprint.device_id,
            "newRisk": True,
            "token": token,
            "requestSource": "neul-next",
            "ctoken": self.ctoken or self._build_ctoken(
                inner_width=width,
                inner_height=height,
                outer_width=width,
                outer_height=height,
                screen_width=width,
            ),
            "version": getattr(self.device_fingerprint, "bili_app_version", "8.48.0"),
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
        mobile_headers = self.headers.copy()
        return self._make_api_call('GET', url, mobile_headers)
    
    def project_info_by_date(self, project_id: str, date: str) -> "ProjectInfoByDateJson":
        url = f'https://show.bilibili.com/api/ticket/project/infoByDate?id={project_id}&date={date}'
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        return self._make_api_call('GET', url, mobile_headers)

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
        """
        url = f"https://show.bilibili.com/api/ticket/search/list?version=134&keyword={urllib.parse.quote(keyword)}&pagesize={pagesize}&page={page}&platform=web"
        mobile_headers = self.headers.copy()
        return self._make_api_call('GET', url, mobile_headers)

    def logout(self):
        """登出当前账号"""
        url = "https://passport.bilibili.com/login/exit/v2"
        # 使用移动端请求头
        mobile_headers = self.headers.copy()
        
        # 从cookie中提取bili_jct值，更安全的方式
        bili_jct = None
        if self.cookie:
            match = re.search(r'bili_jct=([^;]+)', self.cookie)
            if match:
                bili_jct = match.group(1)
        
        if not bili_jct:
            logger.error("无法从cookie中提取bili_jct，登出失败")
            return {"code": -1, "message": "无法提取bili_jct"}
            
        data = {
            "biliCSRF": bili_jct
        }
        return self._make_api_call('POST', url, mobile_headers, json_data=data)

    def qr_login(self, timeout: int = 180) -> Optional[str]:
        """扫码登录，返回 Cookie 字符串。

        参数
        -----
        timeout : int
            等待用户扫码并确认的最大秒数，默认 3 分钟。
        """
        try:
            session = requests.Session()
            # 使用self中的一部分设备信息
            # 先随个 设备
            device = create_virtual_device()
            self.set_device(device)
            common_headers = {
                "User-Agent": self.headers["User-Agent"],
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

            # 2. 在终端打印二维码
            logger.info("请使用 B 站客户端扫码并确认登录 (有效期约 2 分钟)…")
            qr = qrcode.QRCode(border=1)
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # 新增: 保存二维码图片到本地目录供用户扫码
            img = qr.make_image(fill_color="black", back_color="white")
            qr_dir = Path("account")  # 统一放在 account 目录，若不存在则创建
            qr_dir.mkdir(parents=True, exist_ok=True)
            qr_path = qr_dir / f"login_qr_{int(time.time())}.png"
            img.save(qr_path)
            logger.info(f"二维码已保存至 {qr_path.absolute()}，请使用 B 站客户端扫描")

            # 使用 try/finally 确保登录结束后删除二维码图片
            try:
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
            finally:
                # 登录流程结束后删除二维码图片
                try:
                    if qr_path.exists():
                        qr_path.unlink()
                        logger.debug(f"已删除临时二维码图片: {qr_path}")
                except Exception as del_err:
                    logger.warning(f"删除二维码图片失败: {del_err}")
        except Exception as e:
            logger.error(f"扫码登录异常: {e}")
            logger.debug(traceback.format_exc())
            return None


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

    # --------- 嵌套 API 包装 ---------
    class API:
        """静态内部 API 包装，供 IDE 静态分析"""
        def __init__(self, outer: "Client"):
            self._o = outer
        def project(self, *args, **kwargs):
            return self._o.project(*args, **kwargs)
        def buyer(self, *args, **kwargs):
            return self._o.buyer(*args, **kwargs)
        def address(self, *args, **kwargs):
            return self._o.address(*args, **kwargs)
        def confirm(self, *args, **kwargs):
            return self._o.confirm(*args, **kwargs)
        def prepare(self, *args, **kwargs):
            return self._o.prepare(*args, **kwargs)
        def create(self, *args, **kwargs):
            return self._o.create(*args, **kwargs)
        def my_info(self, *args, **kwargs):
            return self._o.my_info(*args, **kwargs)
        def create_status(self, *args, **kwargs):
            return self._o.create_status(*args, **kwargs)
        def project_info_by_date(self, *args, **kwargs):
            return self._o.project_info_by_date(*args, **kwargs)
        def qr_login(self, *args, **kwargs):
            return self._o.qr_login(*args, **kwargs)
        def search_project(self, *args, **kwargs):
            return self._o.search_project(*args, **kwargs)

    # 保留 api 属性实例（__init__ 中赋值）


# 向后兼容: 保留旧类名 Api
Api = Client




