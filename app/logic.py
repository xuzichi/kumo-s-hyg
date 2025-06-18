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

from .utils.log import logger
import yaml
from .order import Order
from .client import Client
from .client import prepareJson, confirmJson, createJson, ProjectJson, BuyerJson, AddressJson
from .utils.push_manager import push_manager

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
    100044: "触发验证码，正在自动处理",
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
        
        self.wait_invoice = config.get("wait_invoice", False)
        self.interval = 0.9  # 全局尝试订单请求间隔, 0.9 是测试下来最稳定的间隔不触发 '前方拥堵' 的间隔
    
    def run(self):
        try:                        
            # build 参数（会自动检测项目类型）
            self.order.build(config=self.config)
            
            # 执行prepare和confirm
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
                    
                    # 执行create下单
                    res = self.order.create()        
                    error_code = res.get("errno", -1)
                    
                    if error_code == 0:
                        logger.warning(f"下单成功, 正在判断是否为假票...")
                        pay_token = res["data"]["token"]
                        order_id = res["data"]["orderId"] if "orderId" in res["data"] else None
                        create_status = self.order.client.api.create_status(project_id=self.order.project_id, pay_token=pay_token, order_id=order_id)
                        if create_status["errno"] == 0:
                            logger.success('购票成功! 请尽快打开订单界面支付!')
                            # 推送
                            push_manager.send(title="[khyg] 购票成功", content=f"请在10分钟内打开订单界面支付!")
                            break
                        else:
                            logger.error(f"假票, 请重新下单.")
                            continue
                    
                    # 使用增强的错误处理
                    if error_code in ERROR_HANDLERS:
                        error_msg = ERROR_HANDLERS[error_code]
                    else:
                        error_msg = f"未知错误码: {error_code}"
                    
                    if error_code == 100044:
                        # 验证码处理逻辑
                        logger.warning(f"{error_msg}")
                        
                        # 检查是否有验证码信息
                        if "ga_data" in res.get("data", {}):
                            logger.info("检测到验证码，尝试自动处理...")
                            risk_params = res["data"]["ga_data"]["riskParams"]
                            if self.order.client.gaia_handler.handle_validation(risk_params):
                                logger.success("验证码处理成功，重新下单")
                                # 重新prepare和confirm以获取新token
                                self.order.prepare()
                                self.order.confirm()
                                order_attempt = 0  # 重置计数器
                                continue
                            else:
                                logger.error("验证码处理失败")
                                time.sleep(0.9)  # 等待一段时间后重试
                                continue
                                
                    elif error_code == 412:
                        logger.error(f"{error_msg} - 可能触发了风控机制")
                        logger.info(f"等待 30 秒后重试...")
                        time.sleep(30)
                        order_attempt = 0  # 重置计数器
                        continue
                    elif error_code == 100051 or error_code == 100050:
                        logger.warning(f"{error_msg}")
                        # 重新prepare和confirm
                        self.order.prepare()
                        self.order.confirm()
                        order_attempt = 0 
                        continue
                    elif error_code in [100003, 100079, 100016, 100039, 100048]:
                        logger.warning(f"{error_msg}")
                        push_manager.send(title="[khyg] 购票失败", content=f"{error_msg}")
                        break  # 项目相关错误，直接退出
                    
                    elif error_code in [3, 429, 100001, 100009, 219, 221, 900001, -509, -799]:
                        if error_code == 3: # 身份证盾中，等待4.96秒后重试
                            logger.info(error_msg)
                            time.sleep(4.96)
                            order_attempt = 0  # 重置计数器
                        else:
                            logger.info(f"{error_msg}")
                            
                        continue
                    # elif error_code == -401:
                    #     logger.warning(f"{error_msg} - 可能触发了风控验证")
                    #     logger.info("尝试刷新bili_ticket以降低风控概率...")
                        
                    #     # 尝试刷新bili_ticket并强制更新
                    #     try:
                    #         self.order.client.ensure_bili_ticket(force_refresh=True)
                    #         logger.info("bili_ticket刷新成功，重试中...")
                    #     except Exception as e:
                    #         logger.warning(f"刷新bili_ticket失败: {e}")
                            
                    #     # 等待一段时间后重试
                    #     logger.info(f"等待 20 秒后重试...")
                    #     time.sleep(20)
                    #     order_attempt = 0  # 重置计数器
                    #     continue
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
                    time.sleep(1.2)
                    order_attempt = 0  # 重置计数器，因为已经等待了1秒
                    
        except CancelledError:
            return
        except KeyboardInterrupt:
            return
        except Exception as e:
            logger.error(f"发生错误: {e}")
            logger.debug(traceback.format_exc())
            
    