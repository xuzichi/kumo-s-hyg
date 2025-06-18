from __future__ import annotations

import traceback
import yaml
from pathlib import Path
import re
import time
from datetime import datetime, timedelta

from noneprompt import (
    ListPrompt,
    Choice,
    CancelledError,
    InputPrompt,
    ConfirmPrompt,
)

from app.logic import Logic
from app.order import Order
from ..utils.log import logger
from .. import client
from .config_builder import ConfigBuilder
from app.utils import account_manager


class ConfigExecutor:
    def __init__(self, client: client):
        self.client = client

    def show_config_menu(self, config_path: Path):
        """展示针对单个配置文件的操作选单"""
        while True:
            try:
                choice = ListPrompt(
                    f"配置: {config_path.stem}",
                    choices=[
                        Choice("▶ 运行", data="run"),
                        Choice("▶ 运行 (anyway)", data="run_anyway"),
                        Choice("✎ 编辑", data="edit"),
                        Choice("C 拷贝", data="copy"),
                        Choice("D 删除", data="delete"),
                        Choice("← 返回", data="back"),
                    ],
                ).prompt()
            except CancelledError:
                return  # go back to main menu

            if choice.data == "run":
                self.run_by_config(config_path, wait_anyway=False)
                return
            if choice.data == "run_anyway":
                self.run_by_config(config_path, wait_anyway=True)
                return
            if choice.data == "edit":
                ConfigBuilder().rebuild_config_from_existing(config_path)

            if choice.data == "copy":
                base_name = config_path.stem
                m = re.search(r"_copy_(\d+)$", base_name)
                if m:
                    base_root = base_name[: -len(m.group(0))]
                    next_index = int(m.group(1)) + 1
                else:
                    base_root = base_name
                    next_index = 1

                # 寻找可用文件名
                while True:
                    candidate = f"{base_root}_copy_{next_index}"
                    if not (config_path.parent / f"{candidate}.yml").exists():
                        break
                    next_index += 1

                try:
                    new_name = InputPrompt("复制为:", default_text=candidate).prompt()
                except CancelledError:
                    continue  # 返回当前菜单

                if not new_name:
                    logger.warning("文件名不能为空！")
                    continue
                target_path = config_path.parent / f"{new_name}.yml"
                if target_path.exists():
                    logger.error("目标文件已存在！")
                    continue
                target_path.write_text(config_path.read_text(), encoding="utf-8")
                logger.success(f"已复制为 {target_path.name}")
                return
            if choice.data == "delete":
                from noneprompt import ConfirmPrompt

                try:
                    confirm = ConfirmPrompt(f"确定删除 {config_path.name}?").prompt()
                except CancelledError:
                    continue
                if confirm:
                    config_path.unlink(missing_ok=True)
                    logger.success("已删除配置文件")
                    return
            if choice.data == "back":
                return

    def wait_for_sale_start(self, sale_start_time: int) -> None:
        """
        等待开票时间到达，并显示倒计时
        
        Args:
            sale_start_time: 开票时间戳（秒）
        """
        current_time = int(time.time())
        
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
                minutes = int(remaining_seconds // 60)
                seconds = int(remaining_seconds % 60)
                time_str = f"{minutes:02d}:{seconds:02d}"
            else:  # 少于1分钟
                time_str = f"{remaining_seconds:.1f}秒"
            
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

    def run_by_config(self, config_name, wait_anyway: bool = False):
        """运行指定的配置文件"""
        with open(config_name, "r", encoding="utf-8") as f:
            try:
                config = yaml.safe_load(f)
                aid = str(config["account_id"]) if "account_id" in config else None
                account = account_manager.get_account(aid) if aid else None
                if not account:
                    logger.error("配置文件中未找到有效 account_id, 或对应账号不存在")
                    return
                # 绑定 Cookie 与设备
                self.client.load_cookie(account.cookie)
                self.client.set_device(account.device)
                
                # 准备阶段：检查账号状态和获取必要信息
                try:
                    self.client.api.ensure_bili_ticket()
                    
                    # 获取当前用户信息
                    my_info_json = self.client.api.my_info()
                    logger.opt(colors=True).info(f'当前用户: {my_info_json["data"]["profile"]["name"]}')
                    
                except Exception as e:
                    logger.error(f"获取用户信息失败: {e}")
                    return
                
                try:
                    # 获取项目信息以获取演出名称
                    project_json = self.client.api.project(project_id=config["project_id"])

                    # 打印配置摘要信息
                    logger.opt(colors=True).info("─" * 50)
                    logger.opt(colors=True).info(f"<cyan>【配置摘要】</cyan>")
                    logger.opt(colors=True).info(f"项目名称: {project_json['data']['name']}")
                    logger.opt(colors=True).info(f"虚拟设备: {account.device.device_name if account else '未知设备'}")
                    logger.opt(colors=True).info(f"登录用户: {account.username if account else '未知用户'}")

                    # 打印票种信息
                    if "screen_ticket" in config and config["screen_ticket"]:
                        for ticket_info in config["screen_ticket"]:
                            screen_idx, ticket_idx = ticket_info
                            if screen_idx < len(
                                project_json["data"]["screen_list"]
                            ) and ticket_idx < len(
                                project_json["data"]["screen_list"][screen_idx][
                                    "ticket_list"
                                ]
                            ):
                                screen = project_json["data"]["screen_list"][screen_idx]
                                ticket = screen["ticket_list"][ticket_idx]
                                price_yuan = ticket["price"] / 100
                                logger.opt(colors=True).info(
                                    f'选择票种: {screen["name"]} {ticket["desc"]} {price_yuan}元'
                                )

                    # 打印地址信息（如果有）
                    if "address_index" in config and config["address_index"]:
                        address_json = self.client.api.address()
                        for addr_idx in config["address_index"]:
                            if addr_idx < len(address_json["data"]["addr_list"]):
                                addr = address_json["data"]["addr_list"][addr_idx]
                                if project_json["data"].get("has_paper_ticket", False):
                                    logger.opt(colors=True).info(
                                        f'收货地址: {addr["name"]} {addr["phone"]} {addr["prov"]}{addr["city"]}{addr["area"]}{addr["addr"]}'
                                    )
                                else:
                                    logger.opt(colors=True).info(
                                        f'记名信息: {addr["name"]} {addr["phone"]}'
                                    )

                    # 打印购票人信息（如果有）
                    if "buyer_index" in config and config["buyer_index"]:
                        buyer_json = self.client.api.buyer()
                        for buyer_idx in config["buyer_index"]:
                            if buyer_idx < len(buyer_json["data"]["list"]):
                                buyer = buyer_json["data"]["list"][buyer_idx]
                                masked_id = f"{buyer['personal_id'][0:2]}*************{buyer['personal_id'][-1:]}"
                                logger.opt(colors=True).info(
                                    f'购票人: {buyer["name"]} {masked_id}'
                                )

                    # 打印购票数量（非实名制）
                    if "count" in config:
                        logger.opt(colors=True).info(f"购票数量: {config['count']}张")

                    logger.opt(colors=True).info("─" * 50)
                    logger.opt(colors=True).info("<cyan>即将开始抢票...</cyan>")

                except Exception as e:
                    logger.error("读取配置文件失败, 请检查配置文件格式")
                    import traceback

                    logger.debug(traceback.format_exc())
                    return

            except Exception as e:
                logger.error("读取配置文件失败, 请检查配置文件格式")
                import traceback

                logger.debug(traceback.format_exc())
                return

            try:
                # 创建订单对象
                order = Order(cookie=account.cookie, project_id=config["project_id"], device=account.device)
                
                # 如果不是 wait_anyway 模式，则等待开票时间
                if not wait_anyway and "sale_start" in project_json["data"]:
                    sale_start_time = project_json["data"]["sale_start"]
                    self.wait_for_sale_start(sale_start_time)
                
                # 设置为不等待，因为我们已经在这里处理了等待逻辑
                config["wait_invoice"] = False

                # 执行抢票逻辑
                Logic(order=order, config=config).run()
            except CancelledError:
                return
            except KeyboardInterrupt:
                return
            except Exception as e:
                import traceback

                logger.debug(traceback.format_exc())
                raise e 