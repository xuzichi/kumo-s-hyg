"""
验证码测试屏幕 - 用于测试验证码过码功能
"""

import traceback
import time
import requests
from typing import Optional
import io

from noneprompt import (
    ListPrompt,
    Choice,
    CancelledError,
    InputPrompt,
    ConfirmPrompt
)

from ..utils.log import logger
from ..client import Client
from ..utils.file_utils import file_utils
from ..utils.push_manager import push_manager
from ..screen.push_screen import PushScreen

class TestScreen:
    def __init__(self):
        self.client = Client()
        
    def run(self):
        while True:
            try:
                _ = ListPrompt(
                    "功能测试:",
                    choices=[
                        Choice("T 过码自动测试 (使用bili_ticket_gt_python)", data="auto"),
                        Choice("M 过码手动测试 (已弃用)", data="manual"),
                        Choice("I 输入文本测试", data="input"),
                        Choice("P 图片弹出测试", data="image"),
                        Choice("N 推送通知测试", data="push"),
                        Choice("← 返回", data="back"),
                    ],
                ).prompt()
            except CancelledError:
                break

            if _.data == "back":
                break
            elif _.data == "auto":
                self._auto_test()
            elif _.data == "manual":
                self._manual_test()
            elif _.data == "input":
                self._input_test()
            elif _.data == "image":
                self._image_test()
            elif _.data == "push":
                self._push_test()

    def _auto_test(self):
        """自动测试验证码过码"""
        logger.info("开始自动验证码测试...")
        
        # 检查是否有验证码处理器
        if not self.client.click:
            logger.error("bili_ticket_gt_python 未安装或初始化失败")
            logger.info("请安装依赖: pip install bili_ticket_gt_python")
            return
            
        try:
            # 获取测试用的GT和Challenge
            gt, challenge = self._get_geetest_params()
            if not gt or not challenge:
                logger.error("无法获取测试用的GT和Challenge参数")
                return
                
            logger.info(f"测试参数:")
            logger.info(f"GT: {gt}")
            logger.info(f"Challenge: {challenge}")
            
            # 开始自动过码
            logger.info("正在尝试自动过码...")
            start_time = time.time()
            
            try:
                validate = self.client.click.simple_match_retry(gt, challenge)
                end_time = time.time()
                
                if validate:
                    logger.success(f"自动过码成功!")
                    logger.success(f"耗时: {end_time - start_time:.2f}秒")
                    logger.success(f"Validate: {validate}")
                    
                else:
                    logger.error("❌ 自动过码失败 - 返回结果为空")
                    
            except Exception as e:
                end_time = time.time()
                logger.error(f"❌ 自动过码失败")
                logger.error(f"耗时: {end_time - start_time:.2f}秒")
                logger.error(f"错误: {e}")
                
        except Exception as e:
            logger.error(f"自动测试过程中发生异常: {e}")
            logger.debug(traceback.format_exc())

    def _manual_test(self):
        """手动测试验证码过码"""
        logger.info("开始手动验证码测试...")
        
        try:
            # 自动获取验证码参数
            logger.info("正在获取验证码参数...")
            gt, challenge = self._get_geetest_params()
            
            if not gt or not challenge:
                logger.error("无法获取验证码参数，请检查网络连接")
                return
                
            logger.info(f"GT: {gt}")
            logger.info(f"Challenge: {challenge}")
            logger.info("请打开以下网站进行手动验证:")
            logger.info("https://kuresaru.github.io/geetest-validator/")
                
        except CancelledError:
            logger.info("用户取消了手动测试")
        except Exception as e:
            logger.error(f"手动测试过程中发生异常: {e}")
            logger.debug(traceback.format_exc())

    def _get_geetest_params(self) -> tuple[Optional[str], Optional[str]]:
        """获取极验验证码的GT和Challenge参数"""
        try:
            session = requests.Session()
            resp = session.get(
                'https://passport.bilibili.com/x/passport-login/captcha?source=main_web',
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://passport.bilibili.com/login",
                },
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    captcha_data = data.get("data", {})
                    geetest_data = captcha_data.get("geetest", {})
                    return geetest_data.get("gt"), geetest_data.get("challenge")
                    
        except Exception as e:
            logger.debug(f"获取验证码参数失败: {e}")
            
        return None, None

    def _input_test(self):
        """输入文本测试"""
        logger.info("开始输入文本测试...")
        logger.info("部分 Windows 用户如遇不能粘贴问题, 请使用 Ctrl+V 粘贴, 或通过 顶部菜单栏->编辑->粘贴 完成")
        text = InputPrompt("请输入文本: ").prompt()
        logger.info(f"输入文本: {text}")
        

    def _image_test(self):
        """图片保存测试"""
        logger.info("开始图片保存测试...")
        
        try:
            # 创建一个简单的彩色渐变测试图像
            width, height = 320, 240
            def _generate_test_image(width, height):
                # 生成一个带彩色渐变的测试图片
                # 使用 io.BytesIO 和简单的图片数据生成
                import struct
                
                # PNG 文件头
                png_signature = b'\x89PNG\r\n\x1a\n'
                
                # IHDR chunk (图片头信息)
                ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)  # RGB, 8bit
                ihdr_crc = __import__('zlib').crc32(b'IHDR' + ihdr_data) & 0xffffffff
                ihdr_chunk = struct.pack('>I', len(ihdr_data)) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
                
                # 图片数据 (简单的彩色渐变)
                image_data = bytearray()
                for y in range(height):
                    image_data.append(0)  # 每行开始的过滤器类型
                    for x in range(width):
                        # 简单的彩色渐变: 红色从左到右渐变，绿色从上到下渐变
                        r = int((x / width) * 255)
                        g = int((y / height) * 255)
                        b = 128  # 固定蓝色值
                        image_data.extend([r, g, b])
                
                # 压缩图片数据
                compressed_data = __import__('zlib').compress(bytes(image_data))
                idat_crc = __import__('zlib').crc32(b'IDAT' + compressed_data) & 0xffffffff
                idat_chunk = struct.pack('>I', len(compressed_data)) + b'IDAT' + compressed_data + struct.pack('>I', idat_crc)
                
                # IEND chunk (文件结束)
                iend_crc = __import__('zlib').crc32(b'IEND') & 0xffffffff
                iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
                
                return png_signature + ihdr_chunk + idat_chunk + iend_chunk
            
            image_data = _generate_test_image(width, height)
            # 保存图片并打开文件夹
            logger.info(f"正在保存 {width}x{height} 彩色渐变测试图片...")
            file_path = file_utils.save_image_and_open_folder(image_data, "test_image")
            
            if file_path:
                logger.success(f"测试图片已保存: {file_path}")
            else:
                logger.error("保存测试图片失败")
            # 等待用户确认
            # 使用 noneprompt
            input = InputPrompt("按下回车释放缓存").prompt()
        except Exception as e:
            logger.debug(traceback.format_exc())
        finally:
            # 释放缓存图片
            file_utils.clean_temp_files("test_image")


    def _push_test(self):
        """推送通知测试"""
        logger.info("实际运行时, 重要通知会同时推送到所有配置")
        
        # 获取所有配置
        configs = push_manager.get_configs()
        
        if not configs:
            logger.warning("没有找到推送配置，请先添加配置")
            return
        
        try:
            # 构建选择菜单
            choices = []
            # choices = [Choice(f"【{c.provider.capitalize()}】{c.name}", data=c) for c in configs]
            for c in configs:
                choices.append(Choice(f"[{c.provider.capitalize()}] {c.name}", data=c))
            choices.append(Choice("← 返回", data="back"))
            
            # 选择配置
            action = ListPrompt("请选择要测试的推送配置:", choices=choices).prompt()
            if action.data == "back":
                return
                
            # 发送测试消息
            config = action.data
            title = "测试通知"
            content = f"这是来自 kumo-s-hyg 的测试消息，发送时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            
            logger.info(f"正在向【{config.provider.capitalize()}】{config.name} 发送测试消息...")
            result = push_manager.push(title, content, config.config_id)
            
            # 显示结果
            if config.name in result and result[config.name]["success"]:
                logger.success("推送成功!")
            else:
                msg = result.get(config.name, {}).get("message", "未知错误")
                logger.error(f"推送失败: {msg}")
        except CancelledError:
            pass
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"推送测试失败: {e}")
            logger.debug(traceback.format_exc())
