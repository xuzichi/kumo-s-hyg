from loguru import logger
import os
import sys
from datetime import datetime


# 检查是否存在日志文件夹
if not os.path.exists("logs"):
    os.makedirs("logs")
    
def init_log(log_level):
    # 为每个进程创建独立的日志文件，避免多开竞争
    pid = os.getpid()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    log_file = f"logs/khyg.{timestamp}_{pid}.log"
    
    # 设置日志格式
    log_format = "<green>{time:HH:mm:ss.S}</green> <level>[{level}]</level> {message}"
    
    # 移除默认的控制台输出
    logger.remove()

    # 文件日志 - 每个进程独立文件
    logger.add(
        sink=log_file,
        format=log_format,
        level=log_level,
        rotation="1 MB",
        retention="7 days",
        compression="zip",
    )

    # 控制台日志
    logger.add(
        sink=sys.stderr,
        format=log_format,
        level=log_level,
    )
    
    # 绑定进程ID到日志上下文
    logger.configure(extra={"pid": pid})
    
    # 记录启动信息
    logger.debug(f"日志系统初始化完成，PID: {pid}, 日志文件: {os.path.basename(log_file)}")