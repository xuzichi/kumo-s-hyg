#!/usr/bin/env python
# -*- coding: utf-8 -*-

from app.utils.push_manager import push_manager, NtfyConfig

def main():
    # 获取所有配置
    configs = push_manager.get_configs()
    print(f"找到 {len(configs)} 个推送配置")
    
    # 测试发送
    push_manager.push("测试中文标题", "这是一条带有中文字符的测试内容\n换行和特殊字符: !@#$%^&*()")
    print("推送消息已发送，请检查您的设备")

if __name__ == "__main__":
    main() 