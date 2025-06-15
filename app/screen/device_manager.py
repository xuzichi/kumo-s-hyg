"""
设备管理器 - 负责虚拟设备的管理界面
"""

from noneprompt import (
    ListPrompt,
    Choice,
    CancelledError,
    ConfirmPrompt,
)

from ..log import logger
from app.device_config import (
    generate_virtual_device,
    list_devices,
    get_current_device,
    set_default_device,
    delete_device,
)


class DeviceManager:
    def __init__(self):
        pass

    def show_management_interface(self):
        """显示设备管理界面"""
        while True:
            devices = list_devices()
            current_device = get_current_device()
            
            choices = []
            
            # 显示设备列表
            if devices:
                for device_info in devices:
                    is_default = current_device and current_device.device_id == device_info['device_id']
                    status = " (当前设备)" if is_default else ""
                    device_name = f"{device_info['device_name']}{status}"
                    choices.append(Choice(device_name, data=("select", device_info['device_id'])))
            else:
                choices.append(Choice("暂无虚拟设备", data="no_device"))
            
            choices.extend([
                Choice("+ 生成新设备", data="create"),
                Choice("- 删除设备", data="delete") if devices else None,
                Choice("← 返回", data="back")
            ])
            
            # 过滤掉None选项
            choices = [c for c in choices if c is not None]
            
            selection = ListPrompt(
                "V 虚拟设备管理:",
                choices=choices
            ).prompt()
            
            try:
                if selection.data == "create":
                    self.create_new_device()
                elif selection.data == "delete":
                    self.delete_device()
                elif isinstance(selection.data, tuple) and selection.data[0] == "select":
                    device_id = selection.data[1]
                    if set_default_device(device_id):
                        logger.opt(colors=True).success('已设置为当前设备')
                    else:
                        logger.error("设置当前设备失败")
                elif selection.data == "no_device":
                    logger.opt(colors=True).info('暂无虚拟设备，请先生成')
                elif selection.data == "back":
                    break
            except CancelledError:
                continue

    def create_new_device(self):
        """创建新虚拟设备 - 完全自动化"""
        try:
            logger.opt(colors=True).info('正在生成新虚拟设备...')
            new_device = generate_virtual_device(set_as_default=False)
            
            logger.opt(colors=True).success(f'虚拟设备 "{new_device.device_name}" 创建成功')
            logger.opt(colors=True).info(f'设备型号: {new_device.model}')
            logger.opt(colors=True).info(f'iOS版本: {new_device.ios_version}')
                
        except Exception as e:
            logger.error(f"创建虚拟设备时出错: {e}")

    def delete_device(self):
        """删除虚拟设备"""
        devices = list_devices()
        if not devices:
            logger.opt(colors=True).info('暂无可删除的虚拟设备')
            return
        
        choices = []
        for device_info in devices:
            device_name = f"{device_info['device_name']} ({device_info['model']})"
            choices.append(Choice(device_name, data=device_info['device_id']))
        
        choices.append(Choice("取消", data="cancel"))
        
        selection = ListPrompt(
            "选择要删除的虚拟设备:",
            choices=choices
        ).prompt()
        
        if selection.data == "cancel":
            return
        
        # 确认删除
        device_info = next(dev for dev in devices if dev['device_id'] == selection.data)
        confirm = ConfirmPrompt(
            f"确定要删除虚拟设备 \"{device_info['device_name']}\" 吗？此操作不可恢复！"
        ).prompt()
        
        if confirm:
            if delete_device(selection.data):
                logger.opt(colors=True).success('虚拟设备已删除')
            else:
                logger.error("删除虚拟设备失败") 