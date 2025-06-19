"""
文件操作工具类
"""

import os
import subprocess
import time
from pathlib import Path
import segno
from .log import logger
from typing import Optional, List


class FileUtils:
    """文件操作工具类"""
    
    @staticmethod
    def open_folder(folder_path: Path | str) -> bool:
        """
        跨平台打开文件夹
        
        参数:
        -----
        folder_path : Path | str
            要打开的文件夹路径
            
        返回:
        -----
        bool
            是否成功打开
        """
        folder_path = Path(folder_path)
        
        try:
            if os.name == 'nt':  # Windows
                os.startfile(str(folder_path))
            elif os.name == 'posix':  # macOS/Linux
                if os.uname().sysname == 'Darwin':  # macOS
                    subprocess.run(['open', str(folder_path)])
                else:  # Linux
                    subprocess.run(['xdg-open', str(folder_path)])
            logger.info(f"已打开文件夹: {folder_path}")
            return True
        except Exception as e:
            logger.warning(f"请手动打开文件夹: {folder_path}")
            return False
    
    @staticmethod
    def save_image_and_open_folder(image_data: bytes, filename_prefix: str) -> Optional[Path]:
        """
        保存图片数据到temp文件夹并打开文件夹
        
        参数:
        -----
        image_data : bytes
            图片二进制数据
        filename_prefix : str
            文件名前缀
            
        返回:
        -----
        Optional[Path]
            保存的文件路径，失败返回None
        """
        try:
            # 创建temp目录
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            
            # 生成文件名
            timestamp = int(time.time())
            filename = f"{filename_prefix}_{timestamp}.png"
            file_path = temp_dir / filename
            
            # 保存图片数据
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            logger.info(f"图片已保存到: {file_path}")
            
            # 打开文件夹
            FileUtils.open_folder(temp_dir)
            
            return file_path
            
        except Exception as e:
            logger.error(f"保存图片失败: {e}")
            return None
    
    @staticmethod
    def save_qr_and_open_folder(url: str, filename_prefix: str) -> Optional[Path]:
        """
        生成二维码保存到temp文件夹并打开文件夹
        
        参数:
        -----
        url : str
            二维码内容URL
        filename_prefix : str
            文件名前缀
            
        返回:
        -----
        Optional[Path]
            保存的文件路径，失败返回None
        """
        try:
            # 创建temp目录
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            
            # 生成二维码文件名
            timestamp = int(time.time())
            qr_filename = f"{filename_prefix}_{timestamp}.png"
            qr_path = temp_dir / qr_filename
            
            # 生成并保存二维码
            qr = segno.make_qr(url)
            qr.save(str(qr_path), scale=8, border=2)
            
            logger.info(f"二维码已保存到: {qr_path}")
            
            # 打开文件夹
            FileUtils.open_folder(temp_dir)
            
            return qr_path
            
        except Exception as e:
            logger.error(f"保存二维码失败: {e}")
            return None
    
    @staticmethod
    def clean_temp_files(filename_prefix: str) -> int:
        """
        清理temp文件夹中指定前缀的文件
        
        参数:
        -----
        filename_prefix : str
            要清理的文件名前缀
            
        返回:
        -----
        int
            清理的文件数量
        """
        try:
            temp_dir = Path("temp")
            if not temp_dir.exists():
                return 0
            
            # 查找匹配的文件
            pattern = f"{filename_prefix}_*.png"
            files = list(temp_dir.glob(pattern))
            
            deleted_count = 0
            for file_path in files:
                try:
                    file_path.unlink()
                    logger.debug(f"已删除文件: {file_path}")
                    deleted_count += 1
                except Exception as e:
                    logger.debug(f"删除文件失败 {file_path}: {e}")
            
            if deleted_count > 0:
                logger.debug(f"已清理 {deleted_count} 个 {filename_prefix} 相关文件")
            
            return deleted_count
            
        except Exception as e:
            logger.debug(f"清理temp文件失败: {e}")
            return 0


# 全局实例
file_utils = FileUtils() 