from pathlib import Path

# 全局临时目录，统一管理所有临时文件/子目录
BASE_TEMP_DIR = Path("temp")
# 确保目录存在
BASE_TEMP_DIR.mkdir(exist_ok=True) 