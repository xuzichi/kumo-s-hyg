import traceback
import time
import yaml
import os
import subprocess
from pathlib import Path

from noneprompt import (
    InputPrompt,
    ListPrompt,
    Choice,
    CancelledError,
    CheckboxPrompt,
    ConfirmPrompt,
)

from app.logic import Logic
from app.order import Order
from .log import logger
from .api import Api


class ConfigBuilder:
    def __init__(self):
        self.api = Api()
        self.cookie = None
        self.template_config = None  # 用于存储模板配置

    def build_config(self, existing_config_path=None):
        """构建新的配置文件或编辑现有配置文件"""
        # 如果是编辑现有配置，先读取cookie
        if existing_config_path:
            try:
                with open(existing_config_path, "r", encoding="utf-8") as f:
                    existing_config = yaml.safe_load(f)
                    self.cookie = existing_config.get('cookie')
                    if self.cookie:
                        self.api.set_cookie(self.cookie)
                        my_info_json = self.api.my_info()
                        if my_info_json['code'] == -101:
                            logger.error("配置文件中的cookie已失效，需要重新登录")
                            if not self._login():
                                return
                        else:
                            logger.opt(colors=True).info(f'使用配置文件中的登录信息: <green>{my_info_json["data"]["profile"]["name"]}</green>')
                    else:
                        logger.error("配置文件中没有找到cookie，需要重新登录")
                        if not self._login():
                            return
            except Exception as e:
                logger.error(f"读取配置文件失败: {e}")
                if not self._login():
                    return
        else:
            # 新建配置，需要登录
            if not self._login():
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

    def _login(self):
        """登录流程"""
        while True:
            try:
                login_options = [
                    Choice("S 扫码登录", data="qrcode"),
                    Choice("I 键入Cookie", data="input"),
                    Choice("C 从现有配置文件中读取", data="config"),
                    Choice("- 取消", data="cancel"),
                ]
                
                _ = ListPrompt(
                    "请选择登录方式:",
                    choices=login_options
                ).prompt()
                
                if _.data == "qrcode": 
                    logger.opt(colors=True).info('<cyan>正在生成二维码...</cyan>')
                    self.cookie = self.api.qr_login()
                    # 扫码登录后，确保UI状态稳定
                    if self.cookie:
                        logger.opt(colors=True).info('<green>扫码登录成功!</green>')
                    else:
                        logger.error("扫码登录失败, 请重新登录")
                        continue
                elif _.data == "input":
                    logger.opt(colors=True).info("请使用浏览器登录B站后, 打开 <green>https://account.bilibili.com/account/home</green>, 在浏览器的开发者工具中找到 Network 选项卡, 选择 home 请求, 在请求头中找到 Cookie 字段, 复制 Cookie 的值, ，粘贴到下面的输入框中.")
                    self.cookie = InputPrompt("请输入 Cookie:").prompt()
                elif _.data == "config":
                    config_files = list(Path("config").glob("*.yml"))
                    if not config_files:
                        logger.error("config文件夹中没有配置文件, 请先创建配置文件")
                        continue
                    
                    # 按修改时间排序
                    config_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    
                    choices = []
                    for config_file in config_files:
                        try:
                            with open(config_file, "r", encoding="utf-8") as f:
                                config = yaml.safe_load(f)
                                project_id = config.get('project_id', '未知')
                                
                            mtime = config_file.stat().st_mtime
                            time_str = time.strftime('%m-%d %H:%M', time.localtime(mtime))
                            choice_text = f"{config_file.stem} ({time_str})"
                            choices.append(Choice(choice_text, data=config_file))
                        except Exception as e:
                            choice_text = f"❌ {config_file.stem} (配置文件损坏)"
                            choices.append(Choice(choice_text, data=config_file))
                    
                    file = ListPrompt(
                        "请选择配置文件作为模板:",
                        choices=choices + [Choice("← 返回", data="back")]
                    ).prompt()
                    
                    if file.data == "back":
                        continue
                    
                    with open(file.data, "r", encoding="utf-8") as f:
                        try:
                            config_data = yaml.safe_load(f)
                            self.cookie = config_data['cookie']
                            # 保存配置数据用于后续填充
                            self.template_config = config_data
                            logger.opt(colors=True).info(f'<cyan>将使用配置文件 {file.data.name} 作为模板</cyan>')
                        except Exception as e:  
                            logger.error("读取配置文件失败, 请检查配置文件格式")
                            continue
                elif _.data == "cancel":
                    return False

                if not self.cookie:
                    logger.error("未找到Cookie")
                    continue
                    
                try:
                    self.api.set_cookie(self.cookie)
                    my_info_json = self.api.my_info()
                    logger.opt(colors=True).info(f'登录用户: <green>{my_info_json["data"]["profile"]["name"]}</green>')
                    # 等待一下确保界面稳定
                    return True
                except Exception as e:
                    logger.error(f"获取用户信息失败, 请检查Cookie是否正确: {e}")
            except KeyboardInterrupt:
                logger.error("登录已取消")
                return False
            except Exception as e:
                logger.error(f"登录过程出现错误: {e}")
                logger.debug(traceback.format_exc())
                # 捕获所有异常，防止界面错乱
                # 给UI一些时间恢复
                continue

    def _get_project_info(self, default_project_id=None):
        """获取项目信息"""
        while True:
            logger.opt(colors=True).info("接下来, 请在演出的链接中找数字ID, 例如 <green>https://show.bilibili.com/platform/detail.html?id=98594</green>, 的ID为 <green>98594</green>.")
            if default_project_id:
                project_id = InputPrompt("请输入项目ID:", default_text=str(default_project_id)).prompt()
            else:
                project_id = InputPrompt("请输入项目ID:",).prompt()
            if not project_id.isdigit():
                logger.error("项目ID必须为数字")
                continue
            logger.info('配置文件生成中...')
            break
        
        project_json = self.api.project(project_id=project_id)
        logger.debug(project_json)
        try:
            logger.opt(colors=True).info(f'项目信息: <green>{project_json["data"]["name"]}</green> {project_json["data"]["sale_flag"]}')
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
            logger.opt(colors=True).warning('<yellow>⚠️  检测到所有票种的限购数量都为0，可能是没有大会员或者没有购买权限导致的，将使用默认限购数量：99张</yellow>')
                
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
        
        # 选择是否等待开票后再抢票
        wait_invoice_choice = ListPrompt(
            "是否等待开票后再抢票？",
            choices=[
                Choice("是 (等待开票后再抢票，推荐)", data=True),
                Choice("否 (立即开始抢票)", data=False),
            ]
        ).prompt()
        wait_invoice = wait_invoice_choice.data
        
        # 添加基础配置
        config_str += f'''

setting: # 常规配置, 根据需求修改
  wait_invoice: {str(wait_invoice).lower()}  # 等待开票后再抢票.
  interval: 0.88  # 全局尝试订单请求间隔, 0.88 是测试下来最稳定的间隔不触发 '前方拥堵' 的间隔.

# ==========================
cookie: {self.cookie}
# ==========================
    '''
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
            address_json = self.api.address()
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
            buyer_json = self.api.buyer()
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
                address_json = self.api.address()
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


class ConfigManager:
    def __init__(self):
        pass

    def edit_config(self):
        """编辑配置文件"""
        config_files = list(Path("config").glob("*.yml"))
        if not config_files:
            logger.error("config文件夹中没有配置文件")
            return

        # 按修改时间排序
        config_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        choices = []
        for config_file in config_files:
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    project_id = config.get('project_id', '未知')
                    
                mtime = config_file.stat().st_mtime
                time_str = time.strftime('%m-%d %H:%M', time.localtime(mtime))
                choice_text = f"{config_file.stem} ({time_str})"
                choices.append(Choice(choice_text, data=config_file))
            except Exception as e:
                choice_text = f"❌ {config_file.stem} (配置文件损坏)"
                choices.append(Choice(choice_text, data=config_file))

        selected_file = ListPrompt(
            "请选择要编辑的配置文件:",
            choices=choices + [Choice("← 返回", data="back")]
        ).prompt()
        
        if selected_file.data == "back":
            return

        # 直接使用配置构建器重新构建
        builder = ConfigBuilder()
        builder.rebuild_config_from_existing(selected_file.data)

    def delete_config(self):
        """删除配置文件"""
        config_files = list(Path("config").glob("*.yml"))
        if not config_files:
            logger.error("config文件夹中没有配置文件")
            return

        # 按修改时间排序
        config_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        choices = []
        for config_file in config_files:
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    project_id = config.get('project_id', '未知')
                    
                mtime = config_file.stat().st_mtime
                time_str = time.strftime('%m-%d %H:%M', time.localtime(mtime))
                choice_text = f"{config_file.stem} ({time_str})"
                choices.append(Choice(choice_text, data=config_file))
            except Exception as e:
                choice_text = f"❌ {config_file.stem} (配置文件损坏)"
                choices.append(Choice(choice_text, data=config_file))

        selected_file = ListPrompt(
            "请选择要删除的配置文件:",
            choices=choices + [Choice("← 返回", data="back")]
        ).prompt()
        
        if selected_file.data == "back":
            return

        # 确认删除
        confirm = ConfirmPrompt(
            f"确定要删除配置文件 {selected_file.data.name} 吗？此操作不可恢复！"
        ).prompt()
        
        if confirm:
            try:
                selected_file.data.unlink()
                logger.success(f"配置文件 {selected_file.data.name} 已删除")
            except Exception as e:
                logger.error(f"删除配置文件失败: {e}")
        else:
            logger.info("已取消删除操作")


class Main:
    def __init__(self):
        self.cookie: str = None
        self.api = Api()
        self.template_config = None  # 用于存储模板配置
        logger.opt(colors=True).info('We1c0me <green>khyg</green> v0.0.1')
        if not Path("config").exists():            
            Path("config").mkdir(parents=True, exist_ok=True)
            
    def run(self):
        while True:
            # 读取所有配置文件并按修改时间排序
            config_files = list(Path("config").glob("*.yml"))
            config_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)  # 按修改时间降序排列
            
            # 构建选择列表
            choices = []
            
            if config_files:
                for config_file in config_files:
                    # 读取配置文件获取项目信息
                    try:
                        with open(config_file, "r", encoding="utf-8") as f:
                            config = yaml.safe_load(f)                                                    
                        choices.append(Choice(config_file.stem, data=("run", config_file)))
                    except Exception as e:
                        # 如果读取配置文件失败，仍然显示文件名
                        choice_text = f"❌ {config_file.stem} (配置文件损坏)"
                        choices.append(Choice(choice_text, data=("run", config_file)))
            else:
                choices.append(Choice("暂无配置文件，请先生成配置", data="no_config"))
            
            choices.append(Choice("+ 新建配置", data="new"))
            choices.append(Choice("W 编辑配置", data="edit"))
            choices.append(Choice("- 删除配置", data="delete"))
            choices.append(Choice("- 退出", data="exit"))
            
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

    def run_by_config(self, config_name):
        with open(config_name, "r", encoding="utf-8") as f:
            try:
                config = yaml.safe_load(f)
                self.api.set_cookie(config['cookie'])
                my_info_json = self.api.my_info()
                if my_info_json['code'] == -101:
                    logger.error("cookie已实效, 请重新登录.")
                    return
                logger.opt(colors=True).info(f'登录用户: <green>{my_info_json["data"]["profile"]["name"]}</green>')
                
                # 获取项目详细信息
                project_json = self.api.project(project_id=config['project_id'])
                
                # 打印配置摘要信息
                logger.opt(colors=True).info('─' * 50)
                logger.opt(colors=True).info(f'<cyan>【配置摘要】</cyan>')
                logger.opt(colors=True).info(f'配置名称: <green>{config_name.stem}</green>')
                logger.opt(colors=True).info(f'项目名称: <green>{project_json["data"]["name"]}</green>')
                
                # 打印票种信息
                if 'screen_ticket' in config and config['screen_ticket']:
                    for ticket_info in config['screen_ticket']:
                        screen_idx, ticket_idx = ticket_info
                        if screen_idx < len(project_json['data']['screen_list']) and ticket_idx < len(project_json['data']['screen_list'][screen_idx]['ticket_list']):
                            screen = project_json['data']['screen_list'][screen_idx]
                            ticket = screen['ticket_list'][ticket_idx]
                            price_yuan = ticket['price'] / 100
                            logger.opt(colors=True).info(f'选择票种: <green>{screen["name"]} {ticket["desc"]} {price_yuan}元</green>')
                
                # 打印地址信息（如果有）
                if 'address_index' in config and config['address_index']:
                    address_json = self.api.address()
                    for addr_idx in config['address_index']:
                        if addr_idx < len(address_json['data']['addr_list']):
                            addr = address_json['data']['addr_list'][addr_idx]
                            if project_json['data'].get('has_paper_ticket', False):
                                logger.opt(colors=True).info(f'收货地址: <green>{addr["name"]} {addr["phone"]} {addr["prov"]}{addr["city"]}{addr["area"]}{addr["addr"]}</green>')
                            else:
                                logger.opt(colors=True).info(f'记名信息: <green>{addr["name"]} {addr["phone"]}</green>')
                
                # 打印购票人信息（如果有）
                if 'buyer_index' in config and config['buyer_index']:
                    buyer_json = self.api.buyer()
                    for buyer_idx in config['buyer_index']:
                        if buyer_idx < len(buyer_json['data']['list']):
                            buyer = buyer_json['data']['list'][buyer_idx]
                            masked_id = f"{buyer['personal_id'][0:2]}*************{buyer['personal_id'][-1:]}"
                            logger.opt(colors=True).info(f'购票人: <green>{buyer["name"]} {masked_id}</green>')
                
                # 打印购票数量（非实名制）
                if 'count' in config:
                    logger.opt(colors=True).info(f'购票数量: <green>{config["count"]}张</green>')
                    
                logger.opt(colors=True).info('─' * 50)
                logger.opt(colors=True).info('<cyan>即将开始抢票...</cyan>')
                
            except Exception as e:  
                logger.error("读取配置文件失败, 请检查配置文件格式")
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