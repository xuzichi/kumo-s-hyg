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
}


class Logic:
    def __init__(self, order: Order, config_name: str) -> None:
        self.order = order        
        self.config_name = config_name
        self.config = None
        self.config_hash = None
        self._monitoring = False
    
    def run(self):
        try:
            logger.opt(colors=True).info(f"配置文件 {self.config_name} 开始运行.")
            
            self.config_hash = self.compute_config_hash(self.config_name)
            self.config = self.read_config(self.config_name)
            
            self.wait_invoice = self.config["setting"]["wait_invoice"]
            self.interval = self.config["setting"]["interval"]
            self.in_stock = self.config["setting"]["in_stock"]
            self.in_stock_interval = self.config["setting"]["in_stock_interval"]
            
            self.order.build_by_config(config=self.config)
                    
            config_monitor_thread = threading.Thread(target=self.config_monitor, daemon=True)
            config_monitor_thread.start()
            
            if self.wait_invoice: # 等待开票
                self.wait_for_invoice()
            
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
                            logger.success('购票成功! 请尽快打开订单界面支付')
                            break
                        else:
                            logger.error(f"假票, 请重新下单.")
                            continue
                    elif res["errno"] == 3:
                        logger.info(f"请慢一点...")
                        time.sleep(4.96)
                        continue
                    elif res["errno"] == 100001:
                        logger.info(f"暂未放票或已售罄")
                        continue
                    elif res["errno"] == 100051:
                        logger.warning(f"订单准备过期, 请重新验证")
                        self.order.prepare()
                        self.order.confirm()
                        continue
                    elif res["errno"] == 100009:
                        logger.info(f"库存不足, 暂无余票")
                        if self.in_stock:
                            logger.info(f"监控库存中, 等待 {self.in_stock_interval} 秒")
                            time.sleep(self.in_stock_interval)
                            continue
                    elif res["errno"] == 100003:
                        logger.warning(f"该项目每人限购1张, 购票人已存在订单.")
                        break
                    elif res["errno"] == 100079:
                        logger.warning(f"本项目已经下单, 有尚未完成订单, 请完成订单后再试")
                        break
                    elif res["errno"] in ERRNO_DICT:
                        logger.info(f"{ERRNO_DICT[res['errno']]}")
                    else:
                        logger.info(f"发生错误: {res}")
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(e)
                    logger.error(f"发生错误: {e}")
                    print(traceback.format_exc())
                    time.sleep(1)
                    
        except CancelledError:
            logger.error(f"已取消")
        except Exception as e:
            logger.error(f"发生错误: {e}")
            print(traceback.format_exc())
        finally:
            try:
                self._monitoring = False # 停止监控
                config_monitor_thread.join()
                logger.opt(colors=True).info(f"<blue>[WatchCat]</blue> 文件 {self.config_name} 监控结束")
            except Exception as e:
                print(traceback.format_exc())
                   
    def compute_config_hash(self, config_name: str) -> str:
        with open(config_name, "r") as f:
            import hashlib
            m = hashlib.md5()
            with open(config_name, "rb") as f:
                m.update(f.read())
            return m.hexdigest()
        
    def read_config(self, config_name: str) -> dict:
        with open(config_name, "r") as f:
            try:
                config = yaml.safe_load(f)
            except Exception as e:
                logger.error(f"[ConfigLoader] 读取配置文件失败, 请检查配置文件格式: {config_name}")
                raise e
        return config

    def wait_for_invoice(self):
        logger.info(f"到达开票时间后开始抢票")
        while True:
            wait_interval = 10
            # <20s时加快检测频率
            if int(time.time()) > self.order.sale_end:
                logger.info(f"项目已结束")
                return
            if int(time.time()) >= self.order.sale_start:
                logger.success(f"项目已开票")
                break
            if int(time.time()) >= self.order.sale_start - 60:
                wait_interval = 1
            if int(time.time()) >= self.order.sale_start - 5:
                wait_interval = 0.3
            if wait_interval <= 1: # 当只剩下 1min 时, 输出seconds
                logger.info(f"距离开票时间还有{int((self.order.sale_start - int(time.time())))}秒")
            else:
                time_difference_seconds = int(self.order.sale_start - int(time.time()))
                days = time_difference_seconds // (60 * 60 * 24)
                remaining_seconds_after_days = time_difference_seconds % (60 * 60 * 24)
                hours = remaining_seconds_after_days // (60 * 60)
                remaining_seconds_after_hours = remaining_seconds_after_days % (60 * 60)
                minutes = remaining_seconds_after_hours // 60
                logger.info(f"距离开票时间还有{days}天{hours}小时{minutes}分钟")
            time.sleep(wait_interval)
            
    def config_monitor(self,):
        logger.opt(colors=True).info(f"<blue>[WatchCat]</blue> 配置文件 {self.config_name} 监控中...")
        while self._monitoring:
            time.sleep(0.7) # 0.7s 检测一次
            pre_config_hash = self.compute_config_hash(self.config_name)
            if pre_config_hash != self.config_hash:
                self.on_modified()
                self.config_hash = pre_config_hash
                
    def on_modified(self,):                
        config_old = self.config
        self.set_config(self.config_name)
        config_new = self.config
                
        big_change = False
        need_re_order_full_build = False
        need_re_order_setting_build = False
        
        # 对比可能出现的键差异 screen_ticket address_index buyer_index setting
        if 'screen_ticket' in config_old and config_old['screen_ticket'] != config_new['screen_ticket']:
            need_re_order_full_build = True
            logger.opt(colors=True).info(f"<blue>[WatchCat]</blue> screen_ticket 已修改")
        if 'address_index' in config_old and config_old['address_index'] != config_new['address_index']:
            need_re_order_full_build = True
            logger.opt(colors=True).info(f"<blue>[WatchCat]</blue> address_index 已修改")
        if 'count' in config_old and config_old['count'] != config_new['count']:
            need_re_order_full_build = True
            logger.opt(colors=True).info(f"<blue>[WatchCat]</blue> count 已修改")
        if 'buyer_index' in config_old and config_old['buyer_index'] != config_new['buyer_index']:
            need_re_order_full_build = True
            logger.opt(colors=True).info(f"<blue>[WatchCat]</blue> buyer_index 已修改")                    
        if 'setting' in config_old and config_old['setting'] != config_new['setting']:
            need_re_order_setting_build = True
            logger.opt(colors=True).info(f"<blue>[WatchCat]</blue> setting 已修改")
        if 'cookie' in config_old and config_old['cookie'] != config_new['cookie']:
            big_change = True
            logger.opt(colors=True).info(f"<blue>[WatchCat]</blue> cookie 已修改, 此项变动需重新运行配置")
        if 'project_id' in config_old and config_old['project_id'] != config_new['project_id']:
            big_change = True
            logger.opt(colors=True).info(f"<blue>[WatchCat]</blue> project_id 已修改, 此项变动需重新运行配置")

        if big_change:  
            logger.opt(colors=True).error(f"<blue>[WatchCat]</blue> 配置文件发生重大变动, 请重新运行配置")
            return 
        if need_re_order_full_build:
            self.order_full_build(config=config_new)
            logger.opt(colors=True).success(f"<blue>[WatchCat]</blue> 订单信息已更新")
        if need_re_order_setting_build:
            self.order_setting_build(config=config_new)
            logger.opt(colors=True).success(f"<blue>[WatchCat]</blue> 'setting' 信息已更新")
        if not need_re_order_full_build and not need_re_order_setting_build and not big_change:
            # 更新无效
            pass

            
            
            