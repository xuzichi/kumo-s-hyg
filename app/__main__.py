
import sys
import os    

from noneprompt import CancelledError
from .log import init_log, logger
from app.screen import Main

from .api import Api

__versions__ = "0.0.6"


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
        print("  --config <file>, -c <file>  指定配置文件, 直接启动.")
        print("  --debug          启用调试模式")
        exit(0)
        
    if '--config' in argv_list or '-c' in argv_list:
        try:
            index = argv_list.index('--config') if '--config' in argv_list else argv_list.index('-c')
            config_file = argv_list[index + 1]
            from app.screen import Main
            Main().run_by_config(config_name=config_file)
        except Exception as e:
            if str(e) == "list index out of range":
                logger.error("请指定配置文件")
            else:
                logger.error(f"配置文件错误: {e}")
            exit(1)
        
    try:
        Main().run()
    except CancelledError:
        logger.info("program exit.")
    except KeyboardInterrupt:
        logger.info("program exit.")
    except Exception as e:
        logger.error(f"程序发生异常：{e}")
        
    
