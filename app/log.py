from loguru import logger


# 检查是否存在日志文件夹
import os
import sys
if not os.path.exists("logs"):
    os.makedirs("logs")
    
def init_log(log_level):
# 设置日志文件
    log_file = "logs/khyg.log"
    # 设置日志格式
    log_format = "<green>{time:HH:mm:ss.S}</green> <level>[{level}]</level> {message}"
    # 添加日志文件
    logger.remove()  

    # 文件日志（按 log_level 过滤）
    logger.add(
        sink=log_file,
        format=log_format,
        # level=log_level,  # 文件日志级别
        rotation="1 MB",
    )

    # 控制台日志（同样按 log_level 过滤）
    logger.add(
        sink=sys.stderr,
        format=log_format,
        level=log_level,  # 关键修复：控制台级别同步
    )