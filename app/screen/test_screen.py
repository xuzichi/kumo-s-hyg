"""
验证码测试屏幕 - 用于测试验证码过码功能
"""

import traceback
import time
import requests
from typing import Optional
import io
import math

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
                        Choice("S 目录弹出测试", data="open"),
                        Choice("P 图片保存测试", data="image"),
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
            elif _.data == "open":
                self._open_test()
            elif _.data == "image":
                self._image_test()

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

    def _open_test(self):
        """目录弹出测试"""
        logger.info("开始目录弹出测试...")
        file_utils.open_folder(".")

    def _image_test(self):
        """图片保存测试"""
        logger.info("开始图片保存测试...")
        
        try:
            # 创建一个简单的彩色渐变测试图像
            width, height = 320, 240
            image_data = self._generate_test_image(width, height)
            
            # 保存图片并打开文件夹
            logger.info(f"正在保存 {width}x{height} 测试图片...")
            file_path = file_utils.save_image_and_open_folder(image_data, "test_image")
            
            if file_path:
                logger.success(f"测试图片已保存: {file_path}")
            else:
                logger.error("保存测试图片失败")
                
        except Exception as e:
            logger.error(f"图片测试过程中发生异常: {e}")
            logger.debug(traceback.format_exc())
            
    def _generate_test_image(self, width=320, height=240):
        """生成一个简单的彩色渐变测试图像
        
        返回:
        -----
        bytes
            PNG格式的图像数据
        """
        try:
            # 尝试使用PIL库创建一个彩色渐变图像
            from PIL import Image
            
            # 创建一个彩色渐变图像
            image = Image.new('RGB', (width, height))
            pixels = image.load()
            
            for i in range(width):
                for j in range(height):
                    r = int(255 * i / width)
                    g = int(255 * j / height)
                    b = int(255 * (i + j) / (width + height))
                    pixels[i, j] = (r, g, b)
            
            # 将图像转换为字节
            img_bytes = io.BytesIO()
            image.save(img_bytes, format='PNG')
            return img_bytes.getvalue()
            
        except ImportError:
            # 如果没有PIL库，创建一个简单的彩色矩形
            logger.warning("未安装PIL库，将生成简单的替代图像")
            
            # 创建一个简单的彩色矩形PNG图像
            # PNG头部和必要的块
            png_data = bytearray([
                0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG签名
                0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR块
                (width >> 24) & 0xFF, (width >> 16) & 0xFF, (width >> 8) & 0xFF, width & 0xFF,  # 宽度
                (height >> 24) & 0xFF, (height >> 16) & 0xFF, (height >> 8) & 0xFF, height & 0xFF,  # 高度
                0x08, 0x02, 0x00, 0x00, 0x00  # 颜色深度等
            ])
            
            # 添加简单数据
            data_size = width * height * 3
            png_data.extend([
                0x00, 0x00, 0x00, 0x00, 0x49, 0x44, 0x41, 0x54,  # IDAT块
                0x78, 0x9C, 0x63, 0x60  # 一些压缩数据
            ])
            
            # 简单填充一些数据
            for i in range(min(100, data_size)):
                png_data.append(i % 256)
                
            # 添加结束标记
            png_data.extend([
                0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82  # IEND块
            ])
            
            return bytes(png_data)


            
            