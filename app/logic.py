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


ERRNO_DICT = {
    0: "成功",
    3: "身份证盾中",
    100009: "库存不足, 暂无余票",
    100001: "无票",
    100041: "对未发售的票进行抢票",
    100003: "该项目每人限购1张",
    100016: "项目不可售",
    100039: "活动收摊啦, 下次要快点哦", # prepare
    100048: "已经下单, 有尚未完成订单",
    100017: "票种不可售",
    100051: "订单准备过期，重新验证", # token 过期
    100034: "票价错误",
    100050: "当前页面已失效，请返回详情页重新下单", # confirm
    209001: "本项目需要联系人信息，请填写姓名及手机号", # create
    900001: "前方拥堵，请重试.", # 前方拥堵，请重试.
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
            # build 参数
            self.order.build(config=self.config)
            
            if self.wait_invoice: # 等待开票
                self.wait_for_sale_start()
            
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
                    
                    res = self.order.create() # 下单        
                    if res["errno"] == 0:
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
                    elif res["errno"] == 3:
                        logger.info(f"请慢一点...")
                        time.sleep(4.96)
                        order_attempt = 0  # 重置计数器，因为已经等待了4.96秒
                        continue
                    elif res["errno"] == 100001:
                        logger.info(f"前方拥堵.")
                        continue
                    elif res["errno"] == 100051:
                        logger.warning(f"订单准备过期, 请重新验证.")
                        self.order.prepare()
                        self.order.confirm()
                        order_attempt = 0  # 重置计数器，重新准备后第一次不等待
                        continue
                    elif res["errno"] == 100009:
                        logger.info(f"库存不足, 暂无余票")
                        continue
                    elif res["errno"] == 900001:
                        logger.info(f"前方拥堵, 请重试.")
                        continue
                    elif res["errno"] == 100003:
                        logger.warning(f"该项目每人限购1张, 购票人已存在订单.")
                        break
                    elif res["errno"] == 100016:
                        logger.warning(f"该项目不可售, 请检查项目是否存在.")
                        continue
                    elif res["errno"] == 100017:
                        logger.warning(f"票种不可售, 请检查票种是否存在.")
                        continue
                    elif res["errno"] == 100079:
                        logger.warning(f"本项目已经下单, 有尚未完成订单, 请完成订单后再试.")
                        break
                    elif res["errno"] == 100039:
                        logger.warning(f"活动收摊啦, 下次要快点哦")
                        break
                    # 其他错误
                    elif res["errno"] in ERRNO_DICT:
                        logger.info(f"{ERRNO_DICT[res['errno']]}")
                    else:
                        logger.info(f"未处理的返回: {res}")
                        
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
            
    