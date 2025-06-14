import json
from pathlib import Path
from random import randint
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
from datetime import datetime, timedelta

from noneprompt import (
    InputPrompt,
    ConfirmPrompt,
    ListPrompt,
    CheckboxPrompt,
    Choice,
    CancelledError
)

from .log import logger
import yaml
from .order import Order
from .api import Api
from .api import prepareJson, confirmJson, createJson, ProjectJson, BuyerJson, AddressJson


# 错误码处理增强
ERROR_HANDLERS = {
    0: "请求成功",
    3: "身份证盾中，请稍后重试",
    412: "请求被拦截，触发风控",
    429: "请求过于频繁，请稍后重试",
    -401: "触发风控验证",
    -412: "请求参数错误",
    -509: "请求过于频繁",
    -616: "提交评论失败",
    -799: "请求过于频繁",
    100001: "无票或网络拥堵",
    100003: "该项目每人限购1张",
    100009: "库存不足，暂无余票",
    100016: "项目不可售",
    100017: "票种不可售",
    100034: "票价错误，自动更新",
    100039: "活动收摊啦，下次要快点哦",
    100041: "对未发售的票进行抢票",
    100048: "已经下单，有尚未完成订单",
    100050: "当前页面已失效，请返回详情页重新下单",
    100051: "订单准备过期，重新验证",
    100079: "本项目已经下单，有尚未完成订单",
    209001: "本项目需要联系人信息，请填写姓名及手机号",
    219: "库存不足",
    221: "系统繁忙，请稍后重试",
    900001: "前方拥堵，请重试",
}



class Logic():
    def __init__(self, order: Order, config: dict) -> None:
        self.order = order 
        self.config =  config
        
        self.wait_invoice = config["setting"]["wait_invoice"]
        self.interval =config["setting"]["interval"]
    
    def wait_for_sale_start(self):
        """等待开票时间到达"""
        current_time = int(time.time())
        sale_start_time = self.order.sale_start
        
        if current_time >= sale_start_time:
            logger.opt(colors=True).info("<green>已到开票时间，立即开始抢票!</green>")
            return
        
        # 格式化开票时间
        sale_start_dt = datetime.fromtimestamp(sale_start_time)
        sale_start_str = sale_start_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        logger.opt(colors=True).info(f"<cyan>等待开票中...</cyan>")
        logger.opt(colors=True).info(f"开票时间: <yellow>{sale_start_str}</yellow>")
        
        while True:
            current_time = time.time()  # 使用float精度
            remaining_seconds = sale_start_time - current_time
            
            # 提前0.3秒开始抢票
            if remaining_seconds <= 0.3:
                logger.opt(colors=True).info("<green>开始抢票！</green>")
                break
            
            # 计算剩余时间
            remaining_time = timedelta(seconds=remaining_seconds)
            
            # 格式化剩余时间
            if remaining_seconds >= 3600:  # 超过1小时
                time_str = str(remaining_time).split('.')[0]  # 去掉微秒
            elif remaining_seconds >= 60:  # 超过1分钟
                minutes = remaining_seconds // 60
                seconds = remaining_seconds % 60
                time_str = f"{minutes:02d}:{seconds:02d}"
            else:  # 少于1分钟
                time_str = f"{remaining_seconds}秒"
            
            current_dt = datetime.fromtimestamp(current_time)
            current_str = current_dt.strftime("%H:%M:%S")
            
            if remaining_seconds <= 60:
                logger.opt(colors=True).info(f"<red>⏰ {current_str} | 倒计时: {time_str}</red>")
            elif remaining_seconds <= 300:
                logger.opt(colors=True).info(f"<yellow>⏰ {current_str} | 剩余: {time_str}</yellow>")
            else:
                logger.opt(colors=True).info(f"<cyan>⏰ {current_str} | 剩余: {time_str}</cyan>")
            
            # 等待间隔：剩余时间越短，更新越频繁
            if remaining_seconds <= 5:
                time.sleep(0.1)  # 最后5秒，每0.1秒更新（更精确）
            elif remaining_seconds <= 10:
                time.sleep(0.5)  # 最后10秒，每0.5秒更新
            elif remaining_seconds <= 60:
                time.sleep(1)    # 最后1分钟，每秒更新
            elif remaining_seconds <= 300:
                time.sleep(5)    # 最后5分钟，每5秒更新
            else:
                time.sleep(10)   # 其他时间，每10秒更新
            
    def run(self):
        try:                        
            # build 参数（会自动检测项目类型）
            self.order.build(config=self.config)
            
            if self.wait_invoice: # 等待开票
                self.wait_for_sale_start()
            
            # 智能prepare（自动选择hot或normal）
            self.order.prepare()
            self.order.confirm()
            
            # 添加下单计数器，第一次不等待
            order_attempt = 0
            
            while True:
                try:    
                    # 第一次下单立即执行，后续有间隔
                    if order_attempt > 0:
                        time.sleep(self.interval)
                    
                    order_attempt += 1
                    logger.opt(colors=True).debug(f"<cyan>正在尝试下单, 内部计数器: {order_attempt} </cyan>")
                    
                    # 智能create（自动选择hot或normal）
                    res = self.order.create()        
                    error_code = res.get("errno", -1)
                    
                    if error_code == 0:
                        logger.warning(f"下单成功, 正在判断是否为假票...")
                        pay_token = res["data"]["token"]
                        order_id = res["data"]["orderId"] if "orderId" in res["data"] else None
                        create_status = self.order.api.create_status(project_id=self.order.project_id, pay_token=pay_token, order_id=order_id)
                        if create_status["errno"] == 0:
                            logger.success('购票成功! 请尽快打开订单界面支付!')
                            break
                        else:
                            logger.error(f"假票, 请重新下单.")
                            continue
                    
                    # 使用增强的错误处理
                    if error_code in ERROR_HANDLERS:
                        error_msg = ERROR_HANDLERS[error_code]
                    else:
                        error_msg = f"未知错误码: {error_code}"
                    
                    if error_code == 412:
                        logger.error(f"{error_msg} - 可能触发了风控机制")
                        logger.info(f"等待 30 秒后重试...")
                        time.sleep(30)
                        order_attempt = 0  # 重置计数器
                        continue
                    elif error_code == 100051:
                        logger.warning(f"{error_msg}")
                        # 智能重新prepare（自动选择hot或normal）
                        self.order.prepare()
                        self.order.confirm()
                        order_attempt = 0 
                        continue
                    elif error_code in [100003, 100079, 100016, 100039]:
                        logger.warning(f"{error_msg}")
                        break  # 项目相关错误，直接退出
                    
                    elif error_code in [3, 429, 100001, 100009, 219, 221, 900001, -401, -509, -799]:
                        if error_code == 3: # 身份证盾中，等待4.96秒后重试
                            logger.info(error_msg)
                            time.sleep(4.96)
                            order_attempt = 0  # 重置计数器
                        else:
                            logger.info(f" {error_msg}")
                            
                        continue
                    else:
                        # 未知错误或不可重试错误
                        logger.error(error_msg)
                        logger.debug(f"未捕获的完整响应: {res}")
                        continue
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"发生错误: {e}")
                    logger.debug(traceback.format_exc())
                    time.sleep(1)
                    order_attempt = 0  # 重置计数器，因为已经等待了1秒
                    
        except CancelledError:
            return
        except KeyboardInterrupt:
            return
        except Exception as e:
            logger.error(f"发生错误: {e}")
            logger.debug(traceback.format_exc())
            
    