"""
配置管理器 - 负责编辑和删除配置文件
"""

import time
import yaml
import os
import subprocess
from pathlib import Path

from noneprompt import (
    ListPrompt,
    Choice,
    ConfirmPrompt,
)

from ..log import logger
from .config_builder import ConfigBuilder


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
                choice_text = f"{config_file.stem} (配置文件损坏)"
                choices.append(Choice(choice_text, data=config_file))
        
        choices.append(Choice("← 返回", data="back"))
        
        file = ListPrompt(
            "请选择要编辑的配置文件:",
            choices=choices
        ).prompt()
        
        if file.data == "back":
            return
        
        # 选择编辑方式
        edit_choices = [
            Choice("重新生成配置", data="regenerate"),
            Choice("使用系统编辑器打开", data="editor"),
            Choice("← 返回", data="back"),
        ]
        
        edit_choice = ListPrompt(
            f"选择编辑方式 ({file.data.name}):",
            choices=edit_choices
        ).prompt()
        
        if edit_choice.data == "regenerate":
            # 重新生成配置
            builder = ConfigBuilder()
            builder.rebuild_config_from_existing(file.data)
        elif edit_choice.data == "editor":
            # 使用系统编辑器打开
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(file.data)
                elif os.name == 'posix':  # macOS and Linux
                    subprocess.call(['open', file.data])
                logger.info(f"已使用系统编辑器打开 {file.data.name}")
            except Exception as e:
                logger.error(f"打开编辑器失败: {e}")

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
                choice_text = f"{config_file.stem} (配置文件损坏)"
                choices.append(Choice(choice_text, data=config_file))
        
        choices.append(Choice("← 返回", data="back"))
        
        file = ListPrompt(
            "请选择要删除的配置文件:",
            choices=choices
        ).prompt()
        
        if file.data == "back":
            return
        
        # 确认删除
        confirm = ConfirmPrompt(
            f"确定要删除配置文件 \"{file.data.name}\" 吗？此操作不可恢复！"
        ).prompt()
        
        if confirm:
            try:
                file.data.unlink()
                logger.success(f"配置文件 {file.data.name} 已删除")
            except Exception as e:
                logger.error(f"删除配置文件失败: {e}")
        else:
            pass 