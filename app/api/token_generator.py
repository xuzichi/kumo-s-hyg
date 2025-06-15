import struct
import base64
import hashlib
import random
import time
import re


class XxteaEncrypt:
    """XXTEA加密算法"""
    
    @staticmethod
    def uint32(n):
        return n & 0xFFFFFFFF
    
    @classmethod
    def encrypt(cls, data, key):
        """XXTEA加密"""
        if len(data) == 0:
            return data
            
        # Convert to 32-bit integers
        v = list(struct.unpack('<%dL' % (len(data) // 4), data))
        k = list(struct.unpack('<4L', key))
        
        n = len(v)
        if n <= 1:
            return data
            
        z = v[n - 1]
        y = v[0] 
        sum_val = 0
        delta = 0x9E3779B9
        
        # 加密轮数
        q = 6 + 52 // n
        
        for _ in range(q):
            sum_val = cls.uint32(sum_val + delta)
            e = (sum_val >> 2) & 3
            
            for p in range(n):
                y = v[(p + 1) % n]
                mx = cls.uint32(
                    (cls.uint32(z >> 5) ^ cls.uint32(y << 2)) + 
                    (cls.uint32(y >> 3) ^ cls.uint32(z << 4))
                ) ^ cls.uint32(
                    (sum_val ^ y) + (k[(p & 3) ^ e] ^ z)
                )
                z = v[p] = cls.uint32(v[p] + mx)
        
        return struct.pack('<%dL' % len(v), *v)


class BiliTokenGenerator:    
    def __init__(self, buvid3: str):
        self.encrypt = XxteaEncrypt()
        
        # 使用传入的buvid3或默认值
        self.buvid3 = buvid3
        
        # 初始化用户行为数据
        self._init_behavior_data()
    
    def _init_behavior_data(self):
        """
        初始化用户行为数据 - 基于JS源码c.js行号对应:
        c.js:2544-2556 变量定义:
        f = 0          # touchend事件计数
        d = 0          # visibilitychange事件计数  
        p = 0          # beforeunload事件计数
        h = 0          # 定时器计数(双字节)
        v = 0          # 时间差值(双字节)
        m = window.scrollX         # 滚动X坐标
        y = window.scrollY         # 滚动Y坐标
        g = window.innerWidth      # 窗口内部宽度
        b = window.innerHeight     # 窗口内部高度
        _ = window.outerWidth      # 窗口外部宽度
        w = window.outerHeight     # 窗口外部高度
        A = window.screenX         # 屏幕X坐标
        x = window.screenY         # 屏幕Y坐标  
        C = window.screen.width    # 屏幕宽度
        k = window.screen.height   # 屏幕高度
        E = window.screen.availWidth # 屏幕可用宽度
        """
        self.touch_end_count = 0        # f - touchend事件计数
        self.scroll_x = 0               # m - window.scrollX
        self.visibility_change_count = 0 # d - visibilitychange事件计数  
        self.scroll_y = 0               # y - window.scrollY
        self.inner_width = 390          # g - window.innerWidth
        self.before_unload_count = 0    # p - beforeunload事件计数
        self.inner_height = 844         # b - window.innerHeight
        self.outer_width = 390          # _ - window.outerWidth
        self.timer_count = random.randint(1, 20)  # h - 定时器计数(双字节)
        self.time_diff = 0              # v - 时间差值(双字节)
        self.outer_height = 844         # w - window.outerHeight
        self.screen_x = 0               # A - window.screenX
        self.screen_y = 0               # x - window.screenY  
        self.screen_width = 390         # C - window.screen.width
        # 注意：k和E在JS中定义但未在encode中使用
    
    def generate_ptoken(self) -> str:
        """
        生成ptoken - 基于buvid3种子
        注意：这个实现是基于某个版本的JS逻辑推测的
        具体的ptoken生成算法可能在JS中被混淆或使用不同的实现
        """
        # 使用buvid3作为种子
        seed = hashlib.md5(self.buvid3.encode()).hexdigest()[:8] 
        seed_int = int(seed, 16)
        
        # 基于种子生成8个32位整数
        random.seed(seed_int)
        values = []
        for i in range(8):
            if i == 0:
                values.append(17)  # 固定第一个值
            elif i == 1:
                values.append(4)   # 固定第二个值
            else:
                values.append(random.randint(1, 500))
        
        # 转换为32字节数据（8个32位大端序整数）
        data = b''
        for val in values:
            data += struct.pack('>I', val)  # 大端序32位整数
        
        return base64.b64encode(data).decode('utf-8')
    
    def generate_ctoken(self) -> str:
        """
        生成ctoken - 完全基于JS源码c.js逆向实现
        
        JS源码对应位置:
        c.js:2597 encode函数定义开始
        c.js:2600 var e = new ArrayBuffer(16) - 创建16字节ArrayBuffer
        c.js:2601 var n = new DataView(e) - 创建DataView
        c.js:2604-2620 数据映射定义 - i对象包含位置和数据映射
        c.js:2631-2643 循环填充buffer，处理单字节和双字节数据
        c.js:2647-2649 转换为Uint8Array并转为字符串
        c.js:2650 调用toBinary函数进行最终转换
        """
        # 创建16字节ArrayBuffer（对应JS的new ArrayBuffer(16)）
        buffer = bytearray(16)
        
        # 数据映射 - 完全按照JS源码c.js的encode函数（c.js:2604-2620）
        data_mapping = {
            0: {'data': self.touch_end_count, 'length': 1},      # f
            1: {'data': self.scroll_x, 'length': 1},             # m  
            2: {'data': self.visibility_change_count, 'length': 1}, # d
            3: {'data': self.scroll_y, 'length': 1},             # y
            4: {'data': self.inner_width, 'length': 1},          # g
            5: {'data': self.before_unload_count, 'length': 1},  # p
            6: {'data': self.inner_height, 'length': 1},         # b
            7: {'data': self.outer_width, 'length': 1},          # _
            8: {'data': self.timer_count, 'length': 2},          # h (双字节)
            10: {'data': self.time_diff, 'length': 2},           # v (双字节)  
            12: {'data': self.outer_height, 'length': 1},        # w
            13: {'data': self.screen_x, 'length': 1},            # A
            14: {'data': self.screen_y, 'length': 1},            # x
            15: {'data': self.screen_width, 'length': 1},        # C
        }
        
        # 填充buffer - 模拟JS的DataView.setUint8/setUint16（c.js:2631-2643）
        for pos in range(16):
            if pos in data_mapping:
                item = data_mapping[pos]
                if item['length'] == 1:
                    # setUint8: 单字节，限制在255内（c.js:2635）
                    value = min(item['data'], 255)
                    buffer[pos] = value
                elif item['length'] == 2:
                    # setUint16: 双字节，大端序，限制在65535内（c.js:2638-2639）
                    value = min(item['data'], 65535)
                    buffer[pos] = (value >> 8) & 0xFF     # 高字节
                    buffer[pos + 1] = value & 0xFF        # 低字节
                    # 注意：pos会在下次循环中被跳过
            else:
                # 未定义的位置填充0（对应JS中的E值，通常为0）c.js:2642
                buffer[pos] = 0
        
        # toBinary转换 - 完全复刻JS的toBinary函数（c.js:2691-2695）
        return self._to_binary(bytes(buffer))
    
    def _to_binary(self, data: bytes) -> str:
        """
        toBinary函数 - 完全基于JS源码c.js:2691-2695实现
        
        JS原始代码:
        toBinary: function(t) {
            for (var e = new Uint16Array(t.length), n = 0; n < e.length; n++)
                e[n] = t.charCodeAt(n);                           // c.js:2693
            return btoa(String.fromCharCode.apply(String, i()(new Uint8Array(e.buffer))))  // c.js:2694
        }
        """
        # 创建Uint16Array等价物 (16个16位整数) - c.js:2693
        uint16_array = []
        for i in range(len(data)):
            uint16_array.append(data[i])  # charCodeAt(n)
        
        # 转换为Uint8Array的buffer (32字节) - c.js:2694
        uint8_buffer = bytearray()
        for val in uint16_array:
            uint8_buffer.append(val & 0xFF)        # 低字节
            uint8_buffer.append((val >> 8) & 0xFF) # 高字节
        
        # Base64编码 - c.js:2694 btoa()
        return base64.b64encode(uint8_buffer).decode('utf-8')
    
    def generate_both_tokens(self) -> tuple[str, str]:
        return self.generate_ptoken(), self.generate_ctoken()


def create_token_generator(buvid3: str = None) -> BiliTokenGenerator:
    return BiliTokenGenerator(buvid3)


