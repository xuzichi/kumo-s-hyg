"""
账号管理界面 - 管理用户的账号列表
"""

import time
import traceback
from pathlib import Path
from typing import Optional

from noneprompt import (
    ListPrompt,
    InputPrompt,
    Choice,
    CancelledError,
    ConfirmPrompt,
)

from ..log import logger
from .. import account_manager
from ..account_manager import Account
from ..virtual_device import create_virtual_device
from ..api.client import Client


class AccountScreen:
    """账号管理界面"""
    
    def __init__(self):
        self.api = Client()
    
    def choose_account(self, preferred_user_id: Optional[str] = None) -> Optional[str]:
        """展示账号选择 / 创建 / 删除界面，返回选择后的有效 Cookie。"""

        while True:
            profiles = account_manager.list_accounts()
            # 若提供首选账号, 将其移到列表最前
            if preferred_user_id:
                for idx, p in enumerate(profiles):
                    if str(p['user_id']) == str(preferred_user_id):
                        # 移动到开头
                        profiles.insert(0, profiles.pop(idx))
                        break

            choices = [
                *(Choice(
                    f"{p['username']} (最后登录 {time.strftime('%Y-%m-%d %H:%M', time.localtime(p['last_login']))})",
                    data=("use", p['user_id'])
                ) for p in profiles),
                Choice("+ 新增账号", data=("add", None)),
                Choice("- 删除账号", data=("delete", None)) if profiles else None,
                Choice("← 取消", data=("cancel", None)),
            ]
            choices = [c for c in choices if c is not None]

            try:
                res = ListPrompt("请选择账号操作:", choices=choices).prompt()
            except CancelledError:
                return None

            action, payload = res.data

            if action == "use":
                account = account_manager.get_account(payload)
                if not account:
                    logger.error("读取账号信息失败，可能已被删除。")
                    continue
                account.last_login = int(time.time())
                account_manager.save_account(account)
                logger.success(f"已选择账号: {account.username}")
                return account.cookie

            if action == "add":
                cookie = self._login_new_account()
                if cookie:
                    return cookie

            if action == "delete":
                self._delete_account()

            if action == "cancel":
                return None
        
    def _login_new_account(self) -> Optional[str]:
        """登录并创建新账号。"""

        while True:
            try:
                _ = ListPrompt(
                    "请选择登录方式:",
                    choices=[
                        Choice("S 扫码登录", data="qrcode"),
                        Choice("I 键入Cookie", data="input"),
                        Choice("← 返回", data="back"),
                    ],
                ).prompt()
            except CancelledError:
                return None

            if _.data == "back":
                return None

            cookie: Optional[str] = None
            if _.data == "qrcode":
                logger.opt(colors=True).info("<cyan>正在生成二维码...</cyan>")
                # 创建新的虚拟设备并绑定到 Api
                device = create_virtual_device()
                self.api.set_device(device)
                cookie = self.api.qr_login()
                if not cookie:
                    logger.error("扫码登录失败，请重试或使用其他方式。")
                    continue
            elif _.data == "input":
                logger.opt(colors=True).info(
                    "请使用浏览器登录B站后, 打开 <green>https://account.bilibili.com/account/home</green>, "
                    "在开发者工具 Network 选项卡中选取 home 请求, 复制请求头中的 Cookie 字段。"
                )
                try:
                    # 同样先创建并绑定虚拟设备
                    device = create_virtual_device()
                    self.api.set_device(device)
                    cookie = InputPrompt("请输入 Cookie:").prompt()
                except CancelledError:
                    return None

            if not cookie:
                logger.error("Cookie 为空！")
                continue

            # 将 Cookie 写入 Api
            self.api.load_cookie(cookie)

            # 创建并保存账号
            account = account_manager.create_account(self.api)
            if account:
                logger.success(f"账号 <green>{account.username}</green> 已保存！")
                return cookie
            else:
                logger.error("添加账号失败")
                return None
    
    def _delete_account(self) -> None:
        profiles = account_manager.list_accounts()
        if not profiles:
            logger.warning("暂无可删除的账号。")
            return

        choices = [Choice(f"{p['username']} ({p['user_id']})", data=p['user_id']) for p in profiles]
        choices.append(Choice("← 取消", data="cancel"))

        try:
            res = ListPrompt("请选择要删除的账号:", choices=choices).prompt()
        except CancelledError:
            return

        if res.data == "cancel":
            return

        uid = res.data
        account = account_manager.get_account(uid)
        if not account:
            logger.error(f"获取 UID:{uid} 账号信息失败，可能已被删除。")
            return
            
        try:
            confirm = ConfirmPrompt(f"确定删除账号 {account.username} 吗？").prompt()
        except CancelledError:
            return

        if confirm:
            if account_manager.delete_account(uid):
                logger.success("账号已删除！")
            else:
                logger.error("删除失败，账号不存在！")
    
                

    