"""
配置构建器 - 负责创建和编辑配置文件
"""

from datetime import datetime, timedelta
import traceback
import time
import yaml
from pathlib import Path
import re
from typing import Optional

from noneprompt import (
    InputPrompt,
    ListPrompt,
    Choice,
    CancelledError,
    CheckboxPrompt,
    ConfirmPrompt,
)

from ..utils.log import logger
from ..client import Client

# 新增：账号管理
from .account_screen import AccountScreen
from app.utils import account_manager as am
from app.utils.push_manager import push_manager


class ConfigBuilder:
    def __init__(self):
        self.client = Client()
        self.cookie = None
        self.template_config = None  # 用于存储模板配置

    def build_config(self, existing_config_path=None):
        """构建新的配置文件或编辑现有配置文件"""
        # 如果是编辑现有配置，先读取cookie
        if existing_config_path:
            try:
                with open(existing_config_path, "r", encoding="utf-8") as f:
                    existing_config = yaml.safe_load(f)
                    account_id = existing_config.get('account_id')
                    if account_id:
                        account = am.get_account(account_id)
                        if account:
                            # 直接展示账号选择界面, 将当前账号排到第一位
                            if not self._choose_account(preferred_user_id=account_id):
                                return
                        else:
                            logger.error("配置文件中的账号不存在，需要重新选择")
                            if not self._choose_account():
                                return
                    else:
                        logger.error("配置文件中没有找到 account_id，需要重新选择账号")
                        if not self._choose_account():
                            return
            except Exception as e:
                logger.error(f"读取配置文件失败: {e}")
                if not self._choose_account():
                    return
        else:
            # 新建配置，需要选择账号
            if not self._choose_account():
                return
            
        # 获取项目信息
        default_project_id = None
        if existing_config_path:
            # 如果是编辑现有配置，尝试读取项目ID作为默认值
            try:
                with open(existing_config_path, "r", encoding="utf-8") as f:
                    existing_config = yaml.safe_load(f)
                    default_project_id = existing_config.get('project_id')
            except Exception:
                pass
        elif self.template_config:
            # 如果使用模板配置，读取模板的项目ID作为默认值
            default_project_id = self.template_config.get('project_id')
            
        isBws = self._set_bws()
        if isBws:
            project_json = self._get_bws_project_info()
            if not project_json:
                return
            
            # 构建配置
            config_str = self._build_bws_config_content(project_json)
            if not config_str:
                return

            # 保存配置文件
            if existing_config_path:
                self._save_bws_config(config_str, project_json, existing_config_path)
            else:
                self._save_bws_config(config_str, project_json)
            
        else:
            project_json = self._get_project_info(default_project_id)
            if not project_json:
                return
                
            # 构建配置
            config_str = self._build_config_content(project_json)
            if not config_str:
                return
                
            # 保存配置文件
            if existing_config_path:
                self._save_config(config_str, project_json, existing_config_path)
            else:
                self._save_config(config_str, project_json)

    def rebuild_config_from_existing(self, config_path):
        """从现有配置文件重新构建配置"""
        logger.opt(colors=True).info(f'<cyan>编辑配置文件: {config_path.name}</cyan>')
        self.build_config(config_path)

    
    def _choose_account(self, preferred_user_id: Optional[str] = None):
        """选择账号返回 True，否则 False，可指定首选账号ID"""
        cookie = AccountScreen().choose_account(preferred_user_id)
        if not cookie:
            return False

        self.cookie = cookie
        # 获取 account_id 以便写入配置
        match = re.search(r'DedeUserID=([^;]+)', cookie)
        if not match:
            logger.error("Cookie中未找到 DedeUserID，无法确定账号ID")
            return False
        user_id = match.group(1)

        account = am.get_account(user_id)
        if not account:
            logger.error("未找到对应账号信息！请先在账号管理中添加账号")
            return False

        self.selected_account_id = user_id

        # 载入 cookie 到 API 供后续接口调用
        try:
            self.client.load_cookie(self.cookie)
            self.client.set_device(account.device)
            my_info_json = self.client.api.my_info()
            logger.opt(colors=True).info(f'登录用户: {my_info_json["data"]["profile"]["name"]}')
            return True
        except Exception as e:
            logger.error(f"加载账号失败: {e}")
            return False

    def _get_project_info(self, default_project_id=None):
        """获取项目信息"""
        while True:
            logger.opt(colors=True).info("接下来, 请输入项目ID或搜索关键词, 例如 <green>102626</green> 或 <green>BML</green>")
            if default_project_id:
                project_input = InputPrompt("请输入项目ID或搜索关键词:", default_text=str(default_project_id)).prompt()
            else:
                project_input = InputPrompt("请输入项目ID或搜索关键词:").prompt()
            
            # 判断输入是否为纯数字（项目ID）
            if project_input.isdigit():
                project_id = project_input
                logger.info('配置文件生成中...')
                project_json = self.client.api.project(project_id=project_id)
            else:
                # 作为关键词搜索
                logger.info(f'正在搜索关键词: {project_input}...')
                search_result = self.client.api.search_project(keyword=project_input)
                
                # 添加debug输出
                logger.debug(f"搜索API返回: {search_result}")
                
                # 修复判断条件，正确检查搜索结果
                if search_result.get('errno') != 0 or not search_result.get('data', {}).get('result'):
                    logger.error(f"搜索失败或未找到结果，请检查关键词或直接输入项目ID")
                    logger.debug(f"搜索失败详情: errno={search_result.get('errno')}, msg={search_result.get('msg')}")
                    continue
                
                logger.debug(f"搜索成功，找到 {len(search_result['data']['result'])} 个结果")
                
                # 构建选择列表
                project_choices = []
                for i, item in enumerate(search_result['data']['result']):
                    logger.debug(f"处理搜索结果 {i+1}: {item}")
                    
                    # 格式化价格显示，将分转为元
                    price_info = ""
                    if item.get('price_low') and item.get('price_high'):
                        price_low = item['price_low'] / 100
                        price_high = item['price_high'] / 100
                        price_info = f" ¥{price_low}-{price_high}"
                    
                    # 格式化日期显示 - 适配新的API格式
                    date_info = f" {item.get('start_time', '')} - {item.get('end_time', '')}"
                    
                    # 构建选项文本 - 适配新的API字段名
                    title = item.get('title') or item.get('project_name', '未知演出')  # 新API可能有 title 或 project_name
                    sale_flag = item.get('sale_flag', '')
                    item_id = item.get('id', '')
                    choice_text = f"{title}{date_info}{price_info} [{sale_flag}]"
                    project_choices.append(Choice(choice_text, data=str(item_id)))
                
                if not project_choices:
                    logger.error("未找到相关演出，请尝试其他关键词或直接输入项目ID")
                    continue
                
                # 添加一个重新搜索的选项
                project_choices.append(Choice("重新搜索", data="search_again"))
                
                # 显示选择列表
                selected_project = ListPrompt(
                    "请选择一个演出项目:",
                    choices=project_choices
                ).prompt()
                
                if selected_project.data == "search_again":
                    continue
                
                project_id = selected_project.data
                logger.info('配置文件生成中...')
                project_json = self.client.api.project(project_id=project_id)
            
            logger.debug(project_json)
            try:
                logger.opt(colors=True).info(f'项目信息: {project_json["data"]["name"]} {project_json["data"]["sale_flag"]}')
            except Exception as e:
                logger.error(f"获取项目信息失败, 请检查项目ID是否正确")
                return None
            
            # 检查项目状态
            if not project_json['data']['screen_list']:
                logger.error("该项目暂无可用场次")
                return None
                
            return project_json

    def _build_config_content(self, project_json):
        """构建配置文件内容"""
        project_id = project_json['data']['id']
        
        # 选择演出日期
        selected_date = None
        if project_json['data']['sales_dates']:
            date_choices = [Choice(f"{date['date']}", data=date['date']) for date in project_json['data']['sales_dates']]
            selected_date_choice = ListPrompt(
                "请选择演出日期:",
                choices=date_choices
            ).prompt()
            selected_date = selected_date_choice.data
            
        # 选择票种信息
        ticket_choices = []
        for screen_idx, screen in enumerate(project_json['data']['screen_list']):
            for ticket_idx, ticket in enumerate(screen['ticket_list']):
                price_yuan = ticket['price'] / 100
                choice_text = f"{screen['name']} {ticket['desc']} {price_yuan}元"
                ticket_choices.append(Choice(choice_text, data=(screen_idx, ticket_idx)))
        
        if not ticket_choices:
            logger.error("该项目暂无可用票种")
            return None
                
        selected_ticket_choice = ListPrompt(
            "请选择票种信息:",
            choices=ticket_choices
        ).prompt()
        
        selected_tickets = [selected_ticket_choice.data]
        
        # 检查是否所有票种的static_limit.num都为0（可能是大会员检测）
        all_limits_zero = True
        for screen in project_json['data']['screen_list']:
            for ticket in screen['ticket_list']:
                static_limit = ticket.get('static_limit', {})
                if static_limit.get('num', 0) > 0:
                    all_limits_zero = False
                    break
            if not all_limits_zero:
                break
        
        if all_limits_zero:
            logger.opt(colors=True).warning('<yellow>检测到所有票种的限购数量都为0，可能是没有大会员或者没有购买权限导致的，将使用默认限购数量：99张</yellow>')
                
        # 开始构建配置字符串
        config_str = f'''project_id: {project_id} # {project_json['data']['name']} {project_json['data']['sale_flag']}'''.strip()
        config_str += f'\n'
        
        if project_json['data']['sales_dates']:
            config_str += f'\nsales_date: # 选择演出日期(单选):'
            for i in project_json['data']['sales_dates']:
                if i['date'] == selected_date:
                    config_str += f'''\n  - {i['date']} # {i['date']}'''
                else:
                    config_str += f'''\n  # - {i['date']} # {i['date']}'''
            config_str += f'\n'

        config_str += f'\nscreen_ticket: # 选择票种信息(单选):'
        for screen_idx, screen in enumerate(project_json['data']['screen_list']):
            for ticket_idx, ticket in enumerate(screen['ticket_list']):
                price_yuan = ticket['price'] / 100
                if (screen_idx, ticket_idx) == selected_tickets[0]:
                    config_str += f'''\n  - [{screen_idx}, {ticket_idx}] # {screen['name']} {ticket['desc']} {price_yuan}元'''
                else:
                    config_str += f'''\n  # - [{screen_idx}, {ticket_idx}] # {screen['name']} {ticket['desc']} {price_yuan}元'''

        # 处理实名制和地址选择
        buyer_address_config = self._handle_buyer_and_address(project_json, selected_tickets[0])
        if buyer_address_config is None:  # 如果返回None表示用户未完成必要的选择
            return None
        config_str += buyer_address_config
        
        # 插入账号ID
        config_str += f"\n\naccount_id: {self.selected_account_id}"
        return config_str

    def _handle_buyer_and_address(self, project_json, selected_ticket_info):
        """处理购票人和地址选择"""
        config_str = ""
        
        # 判断实名制类型
        buyer_info = project_json['data'].get('buyer_info', '')
        id_bind = project_json['data'].get('id_bind', 0)
        is_realname = bool(buyer_info) or id_bind in [1, 2]
        
        # 获取选中票种的限购信息
        screen_idx, ticket_idx = selected_ticket_info
        static_limit = project_json['data']['screen_list'][screen_idx]['ticket_list'][ticket_idx].get('static_limit', {})
        max_limit = static_limit.get('num', 1)
        
        # 如果static_limit.num为0，说明限购识别失败，使用默认值99
        if max_limit == 0:
            max_limit = 99  # 识别失败时的默认值
        
        address_outputed = False
        
        # 处理纸质票地址
        if project_json['data']['has_paper_ticket']:
            logger.opt(colors=True).info('<cyan>此演出为纸质票演出, 请选择收货地址</cyan>')
            address_json = self.client.api.address()
            address_choices = []
            for i, addr in enumerate(address_json['data']['addr_list']):
                choice_text = f"{addr['name']} {addr['phone']} {addr['prov']}{addr['city']}{addr['area']}{addr['addr']}"
                address_choices.append(Choice(choice_text, data=i))
                
            selected_address_choice = ListPrompt(
                "请选择收货地址:",
                choices=address_choices
            ).prompt()
            selected_address = selected_address_choice.data
            
            config_str += f'\n'
            config_str += f'\n# 此演出为纸质票演出, 注意收货地址'
            config_str += f'\naddress_index: # 选择地址信息(单选):'
            for i in range(len(address_json['data']["addr_list"])):
                if i == selected_address:
                    config_str += f'''\n  - {i} # {address_json['data']['addr_list'][i]['name']} {address_json['data']['addr_list'][i]['phone']} {address_json['data']['addr_list'][i]['prov']}{address_json['data']['addr_list'][i]['city']}{address_json['data']['addr_list'][i]['area']}{address_json['data']['addr_list'][i]['addr']}'''
                else:   
                    config_str += f'''\n  # - {i} # {address_json['data']['addr_list'][i]['name']} {address_json['data']['addr_list'][i]['phone']} {address_json['data']['addr_list'][i]['prov']}{address_json['data']['addr_list'][i]['city']}{address_json['data']['addr_list'][i]['area']}{address_json['data']['addr_list'][i]['addr']}'''
            address_outputed = True
            
        # 处理实名制购票人
        if is_realname:
            buyer_json = self.client.api.buyer()
            buyer_choices = []
            for i, buyer in enumerate(buyer_json['data']['list']):
                choice_text = f"{buyer['name']} {buyer['personal_id'][0:2]}*************{buyer['personal_id'][-1:]}"
                buyer_choices.append(Choice(choice_text, data=i))
            
            # 实名制演出：可以选择多个购票人，最多选择max_limit个
            logger.opt(colors=True).info(f'<cyan>此演出为实名制演出, 限购{max_limit}张, 可以选择多个购票人(最多{max_limit}个)</cyan>')
            
            # 循环直到用户选择了至少一个购票人
            while True:
                selected_buyer_choices = CheckboxPrompt(
                    f"请选择购票人信息(可多选, 最多{max_limit}个) - 按下空格或鼠标点击以多选:",
                    choices=buyer_choices
                ).prompt()
                
                if not selected_buyer_choices:
                    logger.error("请至少选择一个购票人")
                elif len(selected_buyer_choices) > max_limit:
                    logger.error(f"最多只能选择{max_limit}个购票人")
                else:
                    break
                
            selected_buyers = [choice.data for choice in selected_buyer_choices]
            config_str += f'\n'
            config_str += f'\n# 此演出为实名制演出, 限购{max_limit}张, 可以选择多个购票人(最多{max_limit}个)'
            config_str += f'\nbuyer_index: # 选择购票人信息(可多选, 最多{max_limit}个):'
            
            for i in range(len(buyer_json['data']["list"])):
                if i in selected_buyers:
                    config_str += f'''\n  - {i} # {buyer_json['data']['list'][i]['name']} {buyer_json['data']['list'][i]['personal_id'][0:2]}*************{buyer_json['data']['list'][i]['personal_id'][-1:]}'''
                else:
                    config_str += f'''\n  # - {i} # {buyer_json['data']['list'][i]['name']} {buyer_json['data']['list'][i]['personal_id'][0:2]}*************{buyer_json['data']['list'][i]['personal_id'][-1:]}'''

        else:
            # 非实名制演出
            logger.opt(colors=True).info(f'<cyan>此演出为非实名制演出, 限购{max_limit}张, 将从您选择的地址信息中构建姓名/电话</cyan>')
            
            if not address_outputed:
                # 如果不是纸质票，需要选择记名信息
                address_json = self.client.api.address()
                address_choices = []
                for i, addr in enumerate(address_json['data']['addr_list']):
                    choice_text = f"{addr['name']} {addr['phone']}"
                    address_choices.append(Choice(choice_text, data=i))
                    
                selected_address_choice = ListPrompt(
                    "请选择记名信息:",
                    choices=address_choices
                ).prompt()
                selected_address = selected_address_choice.data
                
                config_str += f'\n'
                config_str += f'\n# 此演出为非实名制演出, 限购{max_limit}张, 将从您选择的地址信息中构建姓名/电话'
                config_str += f'\naddress_index: # 选择记名信息(单选):'
                for i in range(len(address_json['data']["addr_list"])):
                    if i == selected_address:
                        config_str += f'''\n  - {i} # {address_json['data']['addr_list'][i]['name']} {address_json['data']['addr_list'][i]['phone']}'''
                    else:
                        config_str += f'''\n  # - {i} # {address_json['data']['addr_list'][i]['name']} {address_json['data']['addr_list'][i]['phone']}'''
                address_outputed = True

            # 选择购买数量 - 根据限购数量动态生成选项
            count_choices = []
            for i in range(1, min(max_limit + 1, 9)):  # 最多显示8个选项
                count_choices.append(Choice(f"{i}张", data=i))
            
            selected_count_choice = ListPrompt(
                f"请选择购买数量(最多{max_limit}张):",
                choices=count_choices
            ).prompt()
            selected_count = selected_count_choice.data

            config_str += f'\n'
            config_str += f'\ncount: {selected_count} # 非实名制演出通过此参数设置购买数量(最多{max_limit}张)'

        return config_str

    def _save_config(self, config_str, project_json, existing_path=None):
        """保存配置文件"""
        if existing_path:
            # 编辑现有配置，直接覆盖
            config_name = existing_path.stem
            save_path = existing_path
        else:
            # 新建配置，询问文件名
            default_text = project_json['data']['name'].replace("-","_").replace(" ","_")
            while True:
                config_name = InputPrompt(question="给配置文件起一个名字吧", default_text=default_text).prompt()
                save_path = Path(f"config/{config_name}.yml")
                
                # 检查是否存在
                if save_path.exists():
                    # 提示是否覆盖
                    _ = ListPrompt(
                        "配置文件已存在, 是否覆盖?",
                        choices=[
                            Choice("是", data="yes"),
                            Choice("否", data="no"),
                        ]
                    ).prompt()
                    if _.data == "no":
                        # 如果选择不覆盖，继续循环让用户重新输入文件名
                        logger.info("请重新输入配置文件名")
                        continue
                # 如果文件不存在或用户选择覆盖，跳出循环
                break
                
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(config_str)
        logger.success(f'配置文件已保存为 {config_name}.yml')
        
        # 重置模板配置
        self.template_config = None 


    def _set_bws(self):
        while True:
            isBws = InputPrompt("请选择是会员购还是bws项目(y/n)").prompt()
            return isBws != "n"

    def _get_bws_project_info(self):
        while True:
            # logger.opt(colors=True).info("接下来, 请输入bws活动时间, 例如 <green>20250711,20250712,20250713</green>")
            # reserve_date = InputPrompt("请输入bws活动时间").prompt()

            # logger.info(f"您输入的bws活动时间为: {reserve_date}")
            logger.info(f"正在搜索")
            search_result = self.client.api.search_bws_project()
            logger.info(f"搜索API返回: {search_result}")

            # 修复判断条件，正确检查搜索结果
            if search_result.get('code') != 0:
                logger.error(f"搜索失败或未找到结果，请检查关键词或直接输入项目ID")
                logger.debug(f"搜索失败详情: errno={search_result.get('errno')}, msg={search_result.get('msg')}")
                continue
            
            # 获取可选择日期
            date_keys = []
            for key in search_result.get('data', {}).get('user_reserve_info', {}).keys():
                if key.isdigit() and len(key) == 8:  # 简单验证8位数字格式
                    date_keys.append(key)
            for key in search_result.get('data', {}).get('user_ticket_info', {}).keys():
                if key.isdigit() and len(key) == 8:
                    date_keys.append(key)
            for key in search_result.get('data', {}).get('reserve_list', {}).keys():
                if key.isdigit() and len(key) == 8:
                    date_keys.append(key)
            date_keys = list(set(date_keys))
            logger.info(f"可选择日期{date_keys}")
            date_choices = []
            for i in date_keys:
                date_choices.append(Choice(f"{i}", data=str(i)))
            selected_date = ListPrompt(
                "请选择一个日期:",
                choices=date_choices
            ).prompt()

            # 获取票号
            ticket = search_result['data']['user_ticket_info'][f"{selected_date.data}"]["ticket"]
            logger.info(f"{selected_date.data} 的票号: {ticket}")
            logger.info(f"{search_result['data']['reserve_list']}")
            # 构建选择列表
            project_choices = []
            for i, item in enumerate(search_result['data']['reserve_list'][f"{selected_date.data}"]):
                logger.info(f"cqy 01")
                logger.debug(f"处理搜索结果 {i + 1}: {item}")
                reserve_id = item['reserve_id']
                act_title = item['act_title']
                reserve_type = item['reserve_type']

                reserve_begin_time = item['reserve_begin_time']
                act_begin_time = item['act_begin_time']
                reserve_begin_dt = datetime.fromtimestamp(reserve_begin_time)
                act_begin_dt = datetime.fromtimestamp(act_begin_time)

                choice_text = f"预约:{reserve_begin_dt} {reserve_id} {act_title} 开始:{act_begin_dt}"
                project_choices.append(Choice(choice_text, data=str(reserve_id) + "|" + str(reserve_begin_time)))
            
            if not project_choices:
                logger.error("未找到相关活动")
                continue

            selected_project = ListPrompt(
                "请选择一个活动项目:",
                choices=project_choices
            ).prompt()

            reserve_id = selected_project.data.split("|")[0]
            reserve_begin_time = selected_project.data.split("|")[1]
            logger.info(f"{selected_date.data} 的票号: {ticket} 预约项目号: {reserve_id} 预定开始时间: {reserve_begin_time}")
            return { 'inter_reserve_id': reserve_id, 'ticket_no': ticket, 'reserve_begin_time': reserve_begin_time }

    def _build_bws_config_content(self, project_json, interval = 0.8):

        inter_reserve_id = project_json['inter_reserve_id']
        ticket_no = project_json['ticket_no']
        reserve_begin_time = project_json['reserve_begin_time']

        return f"is_bws: true\n\nticket_no: {ticket_no}\n\ninter_reserve_id: {inter_reserve_id}\n\nreserve_begin_time: {reserve_begin_time}\n\ninterval: {interval}\n\naccount_id: {self.selected_account_id}"

    def _save_bws_config(self, config_str, project_json, existing_path=None):
        if existing_path:
            # 编辑现有配置，直接覆盖
            config_name = existing_path.stem
            save_path = existing_path
        else:
            # 新建配置，询问文件名
            default_text = f"bw乐园{project_json['inter_reserve_id']}-{project_json['ticket_no']}"
            while True:
                config_name = InputPrompt(question="给配置文件起一个名字吧", default_text=default_text).prompt()
                save_path = Path(f"config/{config_name}.yml")
                
                # 检查是否存在
                if save_path.exists():
                    # 提示是否覆盖
                    _ = ListPrompt(
                        "配置文件已存在, 是否覆盖?",
                        choices=[
                            Choice("是", data="yes"),
                            Choice("否", data="no"),
                        ]
                    ).prompt()
                    if _.data == "no":
                        # 如果选择不覆盖，继续循环让用户重新输入文件名
                        logger.info("请重新输入配置文件名")
                        continue
                # 如果文件不存在或用户选择覆盖，跳出循环
                break
                
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(config_str)
        logger.success(f'配置文件已保存为 {config_name}.yml')
        
        # 重置模板配置
        self.template_config = None 