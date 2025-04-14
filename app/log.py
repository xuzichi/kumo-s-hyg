from loguru import logger


# 检查是否存在日志文件夹
import os
import sys
if not os.path.exists("logs"):
    os.makedirs("logs")
# 设置日志文件
log_file = "logs/bhyg.log"
# 设置日志格式
log_format = "<green>{time:HH:mm:ss.S}</green> <level>[{level}]</level> {message}"
# 设置日志级别
log_level = "DEBUG"
# 添加日志文件
logger.remove()  
# 设置日志文件格式
logger.add(
    sink=log_file,
    format=log_format,
    level=log_level,
    rotation="1 MB",
    compression="zip",
)

# 设置控制台日志格式
logger.add(
    sink=sys.stderr,
format=log_format,
)

