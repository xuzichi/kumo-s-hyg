import sys
import os    

from noneprompt import CancelledError
from .utils.log import init_log, logger
from app.screen import Main
from .client import Client
# from .gaia import GaiaCaptchaManager  # 已删除

__versions__ = "0.5.5"


if __name__ == "__main__" or __name__ == "app.__main__":
    # 读取启动命令行参数
    argv_list = sys.argv[1:]
    if '--debug' in argv_list or '-d' in argv_list:
        init_log("DEBUG")
        logger.debug("DEBUG MODE")
    else:
        init_log("INFO")
        
    if '--version' in argv_list or '-v' in argv_list:
        print(__versions__)
        exit(0)
        
    if '--help' in argv_list or '-h' in argv_list:
        print("可用参数:")
        print("  --version, -v    显示版本号")
        print("  --help, -h       显示帮助信息")
        # print("  --config <file>, -c <file>  指定配置文件, 直接启动.")
        print("  --debug, -d       启用调试模式")
        exit(0)
        
    try:
        logger.opt(colors=True).info(f'We1c0me <green>khyg</green> v{__versions__}')
        # 如果没有 models 文件夹，提示用户等待初始化模型
        if not os.path.exists("models"):
            logger.warning("验证码模型初始化中...")
        
        Main().run()
    except CancelledError:
        logger.info("program exit.")
    except KeyboardInterrupt:
        logger.info("program exit.")
    except Exception as e:
        logger.error(f"程序发生异常：{e}")
        logger.debug("异常详情:", exc_info=True)
        
    
