"""
自动验证码处理器 - 优化版本
处理滑块和点选验证码，采用多步骤处理以提高成功率
"""
import json
import time
from typing import Dict, Optional, Tuple, Any

import requests
from ..utils.log import logger
from .base import BaseCaptchaHandler

try:
    import bili_ticket_gt_python
    GEETEST_AVAILABLE = True
except ImportError:
    GEETEST_AVAILABLE = False
    logger.warning("bili_ticket_gt_python 库未安装，本地验证码处理将受限")


class GeetestHandler(BaseCaptchaHandler):
    """极验滑块验证码处理器 - 优化版本"""
    
    def __init__(self, api_instance):
        super().__init__(api_instance)
        self.slide = None
        self._initialized = False
        
    def _init_handler(self):
        """延迟初始化滑块处理器"""
        if self._initialized:
            return
            
        self._initialized = True
        if GEETEST_AVAILABLE:
            try:
                self.slide = bili_ticket_gt_python.SlidePy()
                logger.success("滑块验证码处理器初始化成功")
            except Exception as e:
                logger.error(f"滑块验证码处理器初始化失败: {str(e)}", exc_info=True)
                self.slide = None
        else:
            logger.warning("bili_ticket_gt_python 库未安装，本地滑块验证将无法使用")
            self.slide = None
    
    def handle(self, token: str, register_data: Dict) -> bool:
        """处理极验滑块验证码 - 增强版"""
        start_time = time.time()
        try:
            # 提取验证码数据
            geetest_data = register_data.get("geetest", {})
            gt = geetest_data.get("gt", "")
            challenge = geetest_data.get("challenge", "")
            
            if not gt or not challenge:
                logger.error("极验验证码数据不完整")
                return False
                
            # 初始化滑块处理器
            self._init_handler()
            if not self.slide:
                logger.error("滑块处理器未初始化，无法处理极验验证码")
                return False
                
            # 获取验证码类型，确保是滑块类型
            try:
                _type = self.slide.get_type(gt, challenge)
                logger.info(f"验证码类型: {_type}")
                if _type != "slide":
                    logger.warning(f"预期滑块验证码，但检测到类型为: {_type}")
            except Exception as e:
                logger.warning(f"验证码类型识别失败: {str(e)}")
            
            # 使用多步骤方法处理验证码（更高成功率）
            try:
                # 获取c和s参数
                (_, _) = self.slide.get_c_s(gt, challenge)
                # 获取新的参数
                (c, s, args) = self.slide.get_new_c_s_args(gt, challenge)
                # 刷新challenge（避免过期）
                if args and isinstance(args, list) and len(args) > 0:
                    new_challenge = args[0]
                    if new_challenge and new_challenge != challenge:
                        logger.info(f"已刷新challenge: {new_challenge[:10]}...")
                        challenge = new_challenge
                
                # 计算关键参数并生成w
                key = self.slide.calculate_key(args)
                w = self.slide.generate_w(key, gt, challenge, str(list(c)), s, "abcdefghijklmnop")
                
                # 验证
                msg, validate = self.slide.verify(gt, challenge, w)
                if not validate:
                    logger.error(f"滑块验证失败: {msg}")
                    # 尝试简化方法（备选）
                    validate_json = self.slide.validate(gt, challenge)
                    if validate_json:
                        result_dict = json.loads(validate_json)
                        validate = result_dict.get("validate", "")
                        seccode = result_dict.get("seccode", "")
                    else:
                        return False
                else:
                    # 从验证结果中提取validate和seccode
                    seccode = validate + "|jordan"
            except Exception as e:
                # 尝试简化方法验证
                logger.warning(f"多步骤验证失败，尝试简化方法: {str(e)}")
                validate_json = self.slide.validate(gt, challenge)
                if not validate_json:
                    logger.error("滑块验证失败")
                    return False
                
                # 解析结果
                result_dict = json.loads(validate_json)
                validate = result_dict.get("validate", "")
                seccode = result_dict.get("seccode", "")
            
            if not validate or not seccode:
                logger.error("滑块验证结果不完整")
                return False
            
            # 从cookie中提取bili_jct值
            csrf = self.get_csrf()
            if not csrf:
                logger.error("无法获取CSRF令牌，滑块验证码处理失败")
                return False
            
            # 构造表单数据
            form_data = {
                "token": token,
                "geetest": json.dumps({
                    "challenge": challenge,
                    "validate": validate,
                    "seccode": seccode
                })
            }
            if csrf:
                form_data["csrf"] = csrf
                
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            logger.info(f"提交滑块验证结果 (处理耗时: {time.time() - start_time:.2f}秒)")
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success(f"滑块验证通过！(总耗时: {time.time() - start_time:.2f}秒)")
                return True
            else:
                logger.error(f"滑块验证码验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"滑块验证码处理异常 (耗时: {time.time() - start_time:.2f}秒): {str(e)}", exc_info=True)
            return False


class ClickHandler(BaseCaptchaHandler):
    """点选验证码处理器 - 优化版本"""
    
    def __init__(self, api_instance):
        super().__init__(api_instance)
        self.click: Optional[Any] = None
        self._initialized: bool = False
        
    def _init_handler(self):
        """延迟初始化点选处理器"""
        if self._initialized:
            return
        
        self._initialized = True
        if GEETEST_AVAILABLE:
            try:
                self.click = bili_ticket_gt_python.ClickPy()
                logger.success("点选验证码处理器初始化成功")
            except Exception as e:
                logger.error(f"点选验证码处理器初始化失败: {str(e)}", exc_info=True)
                self.click = None
        else:
            logger.warning("bili_ticket_gt_python 库未安装，本地点选验证将无法使用")
            self.click = None
    
    def handle(self, token: str, register_data: Dict) -> bool:
        """处理点选验证码 - 增强版"""
        start_time = time.time()
        try:
            # 提取验证码数据
            click_data = register_data.get("click", {})
            gt = click_data.get("gt", "")
            challenge = click_data.get("challenge", "")
            
            if not gt or not challenge:
                logger.error("点选验证码数据不完整")
                return False
                
            # 初始化点选处理器
            self._init_handler()
            if not self.click:
                logger.error("点选处理器未初始化，无法处理点选验证码")
                return False
                
            # 获取验证码类型，确保是点选类型
            try:
                _type = self.click.get_type(gt, challenge)
                logger.info(f"验证码类型: {_type}")
                if _type != "click":
                    logger.warning(f"预期点选验证码，但检测到类型为: {_type}")
            except Exception as e:
                logger.warning(f"验证码类型识别失败: {str(e)}")
            
            validate_json = ""
            
            # 尝试使用simple_match_retry方法（含自动重试）
            try:
                validate_json = self.click.simple_match_retry(gt, challenge)
            except Exception as e:
                logger.warning(f"简化重试方法失败: {str(e)}，尝试多步骤方法")
                
                # 尝试使用多步骤方法
                try:
                    # 获取c和s参数
                    (_, _) = self.click.get_c_s(gt, challenge)
                    # 获取新参数
                    (c, s, args) = self.click.get_new_c_s_args(gt, challenge)
                    
                    # 计算关键参数
                    before_calculate_key = time.time()
                    key = self.click.calculate_key(args)
                    
                    # 生成点击坐标列表并构造w
                    point_list = self._generate_points(key)
                    w = self.click.generate_w(
                        ",".join(point_list) if isinstance(point_list, list) else point_list,
                        gt, challenge, str(list(c)), s, "abcdefghijklmnop"
                    )
                    
                    # 点选验证码需要模拟人工操作时间
                    w_use_time = time.time() - before_calculate_key
                    # if w_use_time < 2:
                    #     time.sleep(2 - w_use_time)
                        
                    # 验证
                    msg, validate = self.click.verify(gt, challenge, w)
                    if validate:
                        validate_json = json.dumps({
                            "validate": validate,
                            "seccode": validate + "|jordan"
                        })
                    else:
                        # 最后尝试简单验证方法
                        validate_json = self.click.validate(gt, challenge)
                except Exception as inner_e:
                    logger.warning(f"多步骤方法失败: {str(inner_e)}，尝试最简单的验证方法")
                    validate_json = self.click.validate(gt, challenge)
            
            if not validate_json:
                logger.error("点选验证失败，所有方法都已尝试")
                return False
                
            # 解析结果
            result_dict = json.loads(validate_json)
            validate = result_dict.get("validate", "")
            seccode = result_dict.get("seccode", "")
            
            if not validate or not seccode:
                logger.error("点选验证结果不完整")
                return False
                
            # 从cookie中提取bili_jct值
            csrf = self.get_csrf()
            if not csrf:
                logger.error("无法获取CSRF令牌，点选验证码处理失败")
                return False
            
            # 构造表单数据
            form_data = {
                "token": token,
                "click": json.dumps({
                    "challenge": challenge,
                    "validate": validate,
                    "seccode": seccode
                })
            }
            if csrf:
                form_data["csrf"] = csrf
                
            # 使用requests直接调用，确保使用表单格式
            headers = self.api.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            
            logger.info(f"提交点选验证结果 (处理耗时: {time.time() - start_time:.2f}秒)")
            
            response = requests.post(
                "https://api.bilibili.com/x/gaia-vgate/v1/validate",
                data=form_data,
                headers=headers
            ).json()
            
            if response.get("code") == 0:
                logger.success(f"点选验证通过！(总耗时: {time.time() - start_time:.2f}秒)")
                return True
            else:
                logger.error(f"点选验证码验证失败: {response.get('message')} (错误码: {response.get('code')})")
                return False
                
        except Exception as e:
            logger.error(f"点选验证码处理异常 (耗时: {time.time() - start_time:.2f}秒): {str(e)}", exc_info=True)
            return False
            
    def _generate_points(self, key_or_points) -> str:
        """
        根据计算结果生成点击坐标列表
        根据不同的返回格式适配处理
        """
        if isinstance(key_or_points, str) and "," in key_or_points:
            return key_or_points
            
        # 如果已经是点列表，直接返回
        if isinstance(key_or_points, list):
            point_list = []
            for point in key_or_points:
                if isinstance(point, tuple) and len(point) == 2:
                    left = str(round((point[0] + 30) / 333 * 10000))
                    top = str(round((point[1] + 30) / 333 * 10000))
                    point_list.append(f"{left}_{top}")
            return ",".join(point_list)
            
        # 如果是其他格式，尝试直接返回
        return key_or_points 