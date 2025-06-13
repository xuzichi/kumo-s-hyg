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
        self.in_stock = config["setting"]["in_stock"]
        self.in_stock_interval = config["setting"]["in_stock_interval"]
            
    def run(self):
        try:                        
            # build 参数
            self.order.build(config=self.config)
            
            if self.wait_invoice: # 等待开票
                logger.info(f"到达开票时间后开始抢票.")
                while True:
                    if int(time.time()) >= self.order.sale_start:
                        break
                    logger.info(f"."*randint(1, 10))
                    time.sleep(0.7)
            
            self.order.prepare()
            self.order.confirm()

            while True:
                time.sleep(self.interval) 
                try:    
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
                        continue
                    elif res["errno"] == 100001:
                        logger.info(f"前方拥堵.")
                        continue
                    elif res["errno"] == 100051:
                        logger.warning(f"订单准备过期, 请重新验证.")
                        self.order.prepare()
                        self.order.confirm()
                        continue
                    elif res["errno"] == 100009:
                        logger.info(f"库存不足, 暂无余票")
                        if self.in_stock:
                            logger.info(f"监控库存中, 等待 {self.in_stock_interval} 秒")
                            time.sleep(self.in_stock_interval)
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
                    
        except CancelledError:
            return
        except KeyboardInterrupt:
            return
        except Exception as e:
            logger.error(f"发生错误: {e}")
            logger.debug(traceback.format_exc())
            
    