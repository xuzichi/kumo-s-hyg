
from noneprompt import CancelledError
from .log import logger
from app.screen import Main


# from .api import Api
# import json

# api = Api(cookie='''buvid4=792540B3-E23F-F917-C096-800414D3451931794-022123020-dVtQcomzGuS9JSW6TzXqig%3D%3D; buvid_fp_plain=undefined; PVID=1; enable_web_push=DISABLE; buvid3=09695BF1-E74E-FED0-604D-4FB33CC1DC0144035infoc; b_nut=1719429244; header_theme_version=CLOSE; fingerprint=72f7c0ef08f05d44d8bd80017974c7fe; buvid_fp=2dbf1065b2c6e2cd29be54ef91c1afd0; rpdid=|(k|lmR|JYmR0J'u~JluJu|)l; _uuid=EF195977-9CD8-56F7-15A8-833ADDC75B4653502infoc; CURRENT_QUALITY=80; home_feed_column=5; CURRENT_FNVAL=4048; DedeUserID=3546879732222088; DedeUserID__ckMd5=b737c35fbaf9bdf1; msource=pc_web; deviceFingerprint=2d3272b5ecb3b85c7f70b7a14b424483; enable_feed_channel=ENABLE; timeMachine=0; bsource=search_bing; browser_resolution=1648-1264; from=pc_order_detail; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NDQ4NzIxMDIsImlhdCI6MTc0NDYxMjg0MiwicGx0IjotMX0.BgkRJ1UGEqfOLmw1bCRjZo6w-DQ5chwGEreW6M8IWDk; bili_ticket_expires=1744872042; b_lsid=91AAC10DC_19633973861; SESSDATA=3f179399%2C1760179598%2Cc433e%2A42CjDKTwZ1B66azzGdwXDGQHyhxNZ8wN_M1RdYM6yoUzqcWSxyZYsEZ0TUKA4sA2SjU50SVlVNeHNCeHpTVDZqRTNwdk1HSWJvQ1RpVzJGNjFEM2hsd2FwTlJYNkI4MGtqNW9ERGdYZjhSMkVHMGRmMTVQV1dtQ2E2MzZQd19QNTI2ekR3M0FXVU5nIIEC; bili_jct=857ddad271e186bed6eae3e5fd623f1c; sid=pmwpa89e''')
# open("9.json", "w").write(json.dumps(api.project(project_id=99979), ensure_ascii=False, indent=4))
try:
    Main().run()
except CancelledError:
    logger.info("program exit.")
except KeyboardInterrupt:
    logger.info("program exit.")
except Exception as e:
    logger.error(f"程序发生异常：{e}")
    
    
