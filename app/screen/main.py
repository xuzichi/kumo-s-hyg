"""
主页 - 程序的主要入口界面
"""

import traceback
import time
import yaml
from pathlib import Path

from noneprompt import (
    ListPrompt,
    Choice,
    CancelledError,
)

from app.logic import Logic
from app.order import Order
from ..log import logger
from ..api import Api
from .config_builder import ConfigBuilder
from .config_manager import ConfigManager
from .device_manager import DeviceManager


class Main:
    def __init__(self):
        self.cookie: str = None
        self.api = Api()
        self.template_config = None  # 用于存储模板配置
        if not Path("config").exists():            
            Path("config").mkdir(parents=True, exist_ok=True)
            
    def run(self):
        while True:
            # 读取所有配置文件并按修改时间排序
            config_files = list(Path("config").glob("*.yml"))
            config_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 构建选择列表
            choices = []
            
            if config_files:
                for config_file in config_files:
                    try:
                        with open(config_file, "r", encoding="utf-8") as f:
                            config = yaml.safe_load(f)                                                    
                        choices.append(Choice(config_file.stem, data=("run", config_file)))
                    except Exception as e:
                        choice_text = f"{config_file.stem} (配置文件损坏)"
                        choices.append(Choice(choice_text, data=("run", config_file)))
            else:
                choices.append(Choice("暂无配置文件，请先生成配置", data="no_config"))
            
            choices.append(Choice("+ 新建配置", data="new"))
            choices.append(Choice("W 编辑配置", data="edit"))
            choices.append(Choice("- 删除配置", data="delete"))
            choices.append(Choice("V 虚拟设备", data="device_manage"))
            choices.append(Choice("← 退出", data="exit"))
            
            _ = ListPrompt(
                "请选择操作:",
                choices=choices
            ).prompt()
            
            try:
                if _.data == "new":
                    self.build_config()
                elif _.data == "edit":
                    self.edit_config()
                elif _.data == "delete":
                    self.delete_config()
                elif _.data == "device_manage":
                    self.show_device_management()
                elif isinstance(_.data, tuple) and _.data[0] == "run":
                    config_file = _.data[1]
                    self.run_by_config(config_file)
                elif _.data == "no_config":
                    logger.opt(colors=True).info('请先生成配置文件')
                    continue
                elif _.data == "exit":
                    logger.opt(colors=True).info('exit, bye!')
                    break
            except CancelledError:
                continue
            except KeyboardInterrupt:
                continue
            except Exception as e:
                logger.error(f'发生错误: {e}')
                logger.debug(f'发生错误: \n{traceback.format_exc()}')

    def build_config(self, existing_config_path=None):
        """构建新的配置文件或编辑现有配置文件"""
        builder = ConfigBuilder()
        builder.build_config(existing_config_path)

    def edit_config(self):
        """编辑配置文件"""
        manager = ConfigManager()
        manager.edit_config()

    def delete_config(self):
        """删除配置文件"""
        manager = ConfigManager()
        manager.delete_config()

    def show_device_management(self):
        """显示设备管理界面"""
        device_manager = DeviceManager()
        device_manager.show_management_interface()

    def run_by_config(self, config_name):
        """运行指定的配置文件"""
        with open(config_name, "r", encoding="utf-8") as f:
            try:
                config = yaml.safe_load(f)
                self.api.set_cookie(config['cookie'])
                my_info_json = self.api.my_info()
                if my_info_json['code'] == -101:
                    logger.error("cookie已实效, 请重新登录.")
                    return
                
                # 获取当前虚拟设备信息
                from app.device_config import get_current_device
                current_device = get_current_device()
                device_name = current_device.device_name if current_device else "未知设备"
                user_name = my_info_json["data"]["profile"]["name"]
                
                # 获取项目详细信息
                project_json = self.api.project(project_id=config['project_id'])
                
                # 打印配置摘要信息
                logger.opt(colors=True).info('─' * 50)
                logger.opt(colors=True).info(f'<cyan>【配置摘要】</cyan>')
                logger.opt(colors=True).info(f'项目名称: {project_json["data"]["name"]}')
                logger.opt(colors=True).info(f'虚拟设备: {device_name}')
                logger.opt(colors=True).info(f'登录用户: {user_name}')
                
                # 打印票种信息
                if 'screen_ticket' in config and config['screen_ticket']:
                    for ticket_info in config['screen_ticket']:
                        screen_idx, ticket_idx = ticket_info
                        if screen_idx < len(project_json['data']['screen_list']) and ticket_idx < len(project_json['data']['screen_list'][screen_idx]['ticket_list']):
                            screen = project_json['data']['screen_list'][screen_idx]
                            ticket = screen['ticket_list'][ticket_idx]
                            price_yuan = ticket['price'] / 100
                            logger.opt(colors=True).info(f'选择票种: {screen["name"]} {ticket["desc"]} {price_yuan}元')
                
                # 打印地址信息（如果有）
                if 'address_index' in config and config['address_index']:
                    address_json = self.api.address()
                    for addr_idx in config['address_index']:
                        if addr_idx < len(address_json['data']['addr_list']):
                            addr = address_json['data']['addr_list'][addr_idx]
                            if project_json['data'].get('has_paper_ticket', False):
                                logger.opt(colors=True).info(f'收货地址: {addr["name"]} {addr["phone"]} {addr["prov"]}{addr["city"]}{addr["area"]}{addr["addr"]}')
                            else:
                                logger.opt(colors=True).info(f'记名信息: {addr["name"]} {addr["phone"]}')
                
                # 打印购票人信息（如果有）
                if 'buyer_index' in config and config['buyer_index']:
                    buyer_json = self.api.buyer()
                    for buyer_idx in config['buyer_index']:
                        if buyer_idx < len(buyer_json['data']['list']):
                            buyer = buyer_json['data']['list'][buyer_idx]
                            masked_id = f"{buyer['personal_id'][0:2]}*************{buyer['personal_id'][-1:]}"
                            logger.opt(colors=True).info(f'购票人: {buyer["name"]} {masked_id}')
                
                # 打印购票数量（非实名制）
                if 'count' in config:
                    logger.opt(colors=True).info(f'购票数量: {config["count"]}张')
                    
                logger.opt(colors=True).info('─' * 50)
                logger.opt(colors=True).info('<cyan>即将开始抢票...</cyan>')
                
            except Exception as e:  
                logger.error("读取配置文件失败, 请检查配置文件格式")
                import traceback
                logger.debug(traceback.format_exc())
                return
                
            try:
                Logic(
                    order=Order(
                        cookie=config['cookie'],
                        project_id=config['project_id']
                        ),
                    config=config,
                    ).run()
            except CancelledError:
                return
            except KeyboardInterrupt:
                return
            except Exception as e:
                import traceback
                logger.debug(traceback.format_exc())
                raise e 