

# Kumo’s HYG 

> 本项目仅供学习与交流, 请勿使用.


## 运行

```bash
cd <your_project_path>
python -m app
# python -m app -d # 开启 debug 模式
```

## 作者的话
> 这次 bw/bml 我对这个项目是否有信心呢? 

A: 有, 但是不多, 因为每个人使用的环境不同, 很多人可能一个账号和购票人被多处使用, b站的策略变更也日新月异, 我尽力了, 但我毕竟只是一个普通人, 和隔壁项目的天才少年与专业团队无可比拟.

> 写这个项目的初衷或起源?

1.有一个朋友有一天想去一个同人 live 的现场, 但是现场票开票时间他在上班, 顶多做一下支付操作, 如果可以自动抢票, 他在上班的就可以不会被骂.
2.回忆相对论vol.2的时候我睡过了, 为了捡到回流, 我临时从我以前写过的 api sdk 构建了一个运行的脚本, 逐渐发展为今天的样子.   

> 想说的?

我会继续写的, 而且这个项目的完成离不开各位开源精神的支持, 感谢各位.


## 免责声明
本项目仅供学习与交流, 请勿使用.本项目不用于 "抢票", 下单逻辑**努力**与正常购票并无二致, 本项目不对任何账号产生的任何后果负任何责任, 本项目不收取任何赞助, 本人所有项目都不收取赞助.

## 须知
**必须**先为账号至少设置一个**实名制购票人**, 一个**地址**, 记名票 | 纸质票 | 等重要信息都将使用**地址**中存储的信息.



## cli 交互设计风格统一
  本项目使用 [Nonebot](https://nonebot.dev/) 附属库 `noneprompt` 交互辅助配置; 支持通过 `Ctrl + C` 返回上一级菜单, 整体开发风格简洁高效, 交互逻辑统一.  

## 配置文件驱动
  本项目基于 `配置文件驱动` 的设计模式, 您完全可以使用同一代码 / 应用程序 多开, 不需要拷贝一份到别的地方.   

> \>3 同时多开 可能会导致 10min 内触发 412 风控
> \>6 同时多开 可能会导致 1min 内触发 412 风控

  本项目生成的配置文件包含大量信息注释, 所有的票种、地址、购票人等相关构建信息都包含在配置文件中, 有一定计算机基础的朋友除了使用cli操作以外, 完全以自行修改 yml 文件以配置程序抢票.  


## 票种
  - [x] 实名制票
  - [x] 记名票
  - [x] 邮寄
  - [x] 选日期票 (支持的很有限, 因为某个日期卖完了就会从返回值中消失, 目前没有做更好的方案)
  - [ ] 选座票

# 推送
推送的作用是抢到票后通知你, 毕竟要在10min内完成下单.
  - [x] bark (ios应用商店下载)
  - [ ] pushplus (等有缘人 pr )


## 验证码
实在不知道怎么弄出验证码, 没有测试环境只能盲写了.

```py
def _init_handlers(self):
    """
    初始化所有验证码处理器
    - 自动处理器 - [bili_ticket_gt_python](https://github.com/Amorter/biliTicker_gt)
    - 手动处理器 - 不常见的验证码类型
    """
    # 自动处理器 - 常见的验证码类型
    self._handlers["geetest"] = GeetestHandler(self.api)
    self._handlers["click"] = ClickHandler(self.api)
    
    # 手动处理器 - 不常见的验证码类型
    self._handlers[""] = DirectHandler(self.api)  # 空类型，直接验证
    self._handlers["img"] = ImageHandler(self.api)
    self._handlers["sms"] = SmsHandler(self.api)
    self._handlers["phone"] = PhoneHandler(self.api)
    self._handlers["sms_mo"] = SmsOutgoingHandler(self.api)
    self._handlers["biliword"] = BiliwordHandler(self.api)

```


