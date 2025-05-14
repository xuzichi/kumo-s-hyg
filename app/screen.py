import traceback
from urllib3 import PoolManager
import json
import yaml
from pathlib import Path
from typing import Dict, Optional, Tuple, List

from noneprompt import (
    InputPrompt,
    ListPrompt,
    Choice,
    CancelledError

)

from app.logic import Logic
from app.order import Order

from .log import logger
from .api import Api



range


class Main:
    def __init__(self):
        self.cookie: str = None
        self.api = Api()
        logger.opt(colors=True).info('We1c0me <green>khyg</green> v0.0.1')
        if not Path("config").exists():            
            Path("config").mkdir(parents=True, exist_ok=True)
            
    def run(self):
        while True:
            _ = ListPrompt(
            "选择工具:",
            choices=[
                Choice("运行配置", data="run"),
                Choice("生成配置", data="build"),
                Choice("退出", data="exit"),

            ]
        ).prompt()
            try:
                if _.data == "run":
                    self.run_config_np()
                elif _.data == "build":
                    self.build_config_np()
                elif _.data == "exit":
                    logger.opt(colors=True).info('Program exit.')
                    break
            except CancelledError:
                continue
            except KeyboardInterrupt:
                continue
            except Exception as e:
                logger.error(f'发生错误: \n{traceback.format_exc()}')             

    def build_config_np(self):
        while True:
            _ = ListPrompt(
                "请选择登录方式:",
                choices=[
                    Choice("扫码登录", data="qrcode"),
                    Choice("键入Cookie", data="input"),
                    Choice("从现有配置文件中读取", data="config"),
                    Choice("取消", data="cancel"),
                ]
            ).prompt()
            if _.data == "qrcode": 
                self.cookie = self.api.qr_login()
            elif _.data == "input":
                logger.opt(colors=True).info("请使用浏览器登录B站后, 打开 <green>https://account.bilibili.com/account/home</green>, 在浏览器的开发者工具中找到 Network 选项卡, 选择 home 请求, 在请求头中找到 Cookie 字段, 复制 Cookie 的值, ，粘贴到下面的输入框中.")
                self.cookie = InputPrompt("请输入 Cookie:").prompt()
            elif _.data == "config":
                config_files = list(Path("config").glob("*.yml"))
                if not config_files:
                    logger.error("config文件夹中没有配置文件, 请先创建配置文件")
                    continue
                
                file = ListPrompt(
                    "请选择配置文件:",
                    choices=[Choice(f.name, data=f) for f in config_files]
                ).prompt()
                
                with open(file.data, "r") as f:
                    try:
                        self.cookie = yaml.safe_load(f)['cookie']
                    except Exception as e:  
                        logger.error("读取配置文件失败, 请检查配置文件格式")
                        continue
            elif _.data == "cancel":
                return

            if not self.cookie:
                logger.error("未找到Cookie")
                continue
            try:
                self.api.set_cookie(self.cookie)
                my_info_json = self.api.my_info()
                logger.opt(colors=True).info(f'登录用户: <green>{my_info_json["data"]["profile"]["name"]}</green>')
                break  
            except Exception as e:
                logger.error("获取用户信息失败, 请检查Cookie是否正确")

        while True:
            logger.opt(colors=True).info("接下来, 请在演出的链接中找数字ID, 例如 <green>https://show.bilibili.com/platform/detail.html?id=98594</green>, 的ID为 <green>98594</green>.")
            project_id = InputPrompt("请输入项目ID:",).prompt()
            if not project_id.isdigit():
                logger.error("项目ID必须为数字")
                continue
            logger.info('配置文件生成中...')
            break
        
        project_json = self.api.project(project_id=project_id)
        # 开始输出 yml 
        config_str = f'''  project_id: {project_id} # {project_json['data']['name']} {project_json['data']['sale_flag']}'''.strip()
        config_str += f'\n'
        if project_json['data']['sales_dates'] != []:
            config_str += f'\nsales_date: # 选择演出日期(单选):'
            for i in project_json['data']['sales_dates']:
                if i['date'] == project_json['data']['sales_dates'][0]['date']:
                    config_str += f'''\n  - {i['date']} # {i['date']}'''
                else:
                    config_str += f'''\n  # - {i['date']} # {i['date']}'''
            config_str += f'\n'

        config_str += f'\nscreen_ticket: # 选择票种信息(单选):'
        for screen_idx, screen in enumerate(project_json['data']['screen_list']):
            for ticket_idx, ticket in enumerate(screen['ticket_list']):
                price_yuan = ticket['price'] / 100
                if screen_idx == 0 and ticket_idx == 0:
                    config_str += f'''\n  - [{screen_idx}, {ticket_idx}] # {screen['name']} {ticket['desc']} {price_yuan}元'''
                else:
                    config_str += f'''\n  # - [{screen_idx}, {ticket_idx}] # {screen['name']} {ticket['desc']} {price_yuan}元'''

        data_str = json.dumps(project_json, ensure_ascii=False)
        
        address_outputed = False     
        if project_json['data']['has_paper_ticket']:
            config_str += f'\n'
            config_str += f'\n# 此演出为纸质票演出, 注意收货地址'
            config_str += f'\naddress_index: # 选择地址信息(单选):'
            address_json = self.api.address()
            for i in range(len(address_json['data']["addr_list"])):
                if i == 0:
                    config_str += f'''\n  - {i} # {address_json['data']['addr_list'][i]['name']} {address_json['data']['addr_list'][i]['phone']} {address_json['data']['addr_list'][i]['prov']}{address_json['data']['addr_list'][i]['city']}{address_json['data']['addr_list'][i]['area']}{address_json['data']['addr_list'][i]['addr']}'''
                else:   
                    config_str += f'''\n  # - {i} # {address_json['data']['addr_list'][i]['name']} {address_json['data']['addr_list'][i]['phone']} {address_json['data']['addr_list'][i]['prov']}{address_json['data']['addr_list'][i]['city']}{address_json['data']['addr_list'][i]['area']}{address_json['data']['addr_list'][i]['addr']}'''
            address_outputed = True
            
        if '一人一证' in data_str or '一单一证' in data_str:
            if '一单一证' in data_str:
                config_str += f'\n'
                config_str += f'\n# 此演出为实名制演出, 可以选择多个购票人'
            elif '一人一证' in data_str:
                config_str += f'\n'
                config_str += f'\n# 此演出为实名制演出, 只能选择一个购票人'
                
            buyer_json = self.api.buyer()
            if '一单一证' in data_str:
                config_str += f'\nbuyer_index: # 选择购票人信息(可多选):'
            elif '一人一证' in data_str:
                config_str += f'\nbuyer_index: # 选择购票人信息(单选):'
            for i in range(len(buyer_json['data']["list"])):
                if i == 0:
                    config_str += f'''\n  - {i} # {buyer_json['data']['list'][i]['name']} {buyer_json['data']['list'][i]['personal_id'][0:2]}*************{buyer_json['data']['list'][i]['personal_id'][-1:]}'''
                else:
                    config_str += f'''\n  # - {i} # {buyer_json['data']['list'][i]['name']} {buyer_json['data']['list'][i]['personal_id'][0:2]}*************{buyer_json['data']['list'][i]['personal_id'][-1:]}'''

        else:
            if address_outputed:
                config_str += f'\n'
                config_str += f'\n# 此演出为非实名制演出, 将从您选择的地址信息中构建姓名/电话'
            else:
                config_str += f'\n'
                config_str += f'\n# 此演出为非实名制演出, 将从您选择的地址信息中构建姓名/电话'
                config_str += f'\naddress_index: # 选择记名信息(单选):'
                address_json = self.api.address()
                for i in range(len(address_json['data']["addr_list"])):
                    if i == 0:
                        config_str += f'''\n  - {i} # {address_json['data']['addr_list'][i]['name']} {address_json['data']['addr_list'][i]['phone']}'''
                    else:
                        config_str += f'''\n  # - {i} # {address_json['data']['addr_list'][i]['name']} {address_json['data']['addr_list'][i]['phone']}'''
                address_outputed = True

            config_str += f'\n'
            config_str += f'\ncount: 1 # 非实名制演出通过此参数设置购买数量'

        config_str += f'''

setting: # 常规配置, 根据需求修改
  wait_invoice: true  # 等待开票后再抢票.
  interval: 0.33  # 全局尝试订单请求间隔, 太快可能会被 412 风控.
  in_stock: false  # 回流模式, 无票时添加一个轮训间隔, 抢票模式下请设置为 false. 
  in_stock_interval: 10  # 回流模式轮训间隔, 太快可能会被 412 风控.

# ==========================
cookie: {self.cookie}
# ==========================
    '''
        # 保存, 打开config文件夹
        # 让用户输入名称
        default_text = project_json['data']['name'].replace("-","_").replace(" ","_")
        while True:
            _  = InputPrompt(question="给配置文件起一个名字吧",default_text=default_text).prompt()
            # 否已存在,如果存在提示是否覆盖
            break
        config_name = _
        # 检查是否存在
        if Path(f"config/{config_name}.yml").exists():
            # 提示是否覆盖
            _ = ListPrompt(
                "配置文件已存在, 是否覆盖?",
                choices=[
                    Choice("是", data="yes"),
                    Choice("否", data="no"),
                ]
            ).prompt()
            if _.data == "no":
                return
        with open(f"config/{config_name}.yml", "w") as f:
            f.write(config_str)
        logger.success(f'配置文件已保存为 {config_name}.yml')
        logger.opt(colors=True).info('运行配置前请先修改配置文件以设置抢票信息, yaml语法参见 <green>https://www.runoob.com/w3cnote/yaml-intro.html</green>.')
            
    def run_by_config(self, config_name):
        with open(config_name, "r") as f:
            try:
                config = yaml.safe_load(f)
                self.api.set_cookie(config['cookie'])
                my_info_json = self.api.my_info()
                if my_info_json['code'] == -101:
                    logger.error("cookie已实效, 请重新登录.")
                    return
                logger.opt(colors=True).info(f'登录用户: <green>{my_info_json["data"]["profile"]["name"]}</green>')
            except Exception as e:  
                logger.error("读取配置文件失败, 请检查配置文件格式")
                raise e
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
                print(traceback.format_exc())
                raise e

    def run_config_np(self):
        config_files = list(Path("config").glob("*.yml"))
        if not config_files:
            logger.error("config文件夹中没有配置文件, 请先创建配置文件")
            return
        
        file = ListPrompt(
            "请选择配置文件:",
            choices=[Choice(f.name, data=f) for f in config_files]
        ).prompt()
        config_name = file.data
        self.run_by_config(config_name)
        
        