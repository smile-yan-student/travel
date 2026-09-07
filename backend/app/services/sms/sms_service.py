"""
短信验证码服务（互亿无线）

功能：
- 发送短信验证码
- 验证短信验证码
- 发送频率限制（同一手机号60秒内只能发一次）
- 每日发送次数限制
- 验证码有效期管理

互亿无线官网：https://www.ihuyi.com/
个人也可注册使用，接入简单，价格便宜。
"""

import random
import re
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import httpx

from ...config import settings
from ...infrastructure.logger import get_logger

_sms_logger = get_logger("sms")


class SMSService:
    """短信验证码服务"""

    def __init__(self):
        self.enabled = settings.sms.sms_enabled
        self.api_url = settings.sms.sms_api_url
        self.api_id = settings.sms.sms_api_id
        self.api_key = settings.sms.sms_api_key
        self.sign = settings.sms.sms_sign
        self.code_expire = settings.sms.sms_code_expire
        self.send_interval = settings.sms.sms_send_interval
        self.daily_limit = settings.sms.sms_daily_limit

        # 内存存储验证码（生产环境建议使用Redis）
        # 格式：{phone: {"code": "123456", "expire_at": timestamp, "send_count": 0, "last_send_time": timestamp}}
        self._code_store: Dict[str, Dict] = {}

    def _validate_phone(self, phone: str) -> bool:
        """验证手机号格式是否正确"""
        if not phone:
            return False
        # 中国大陆手机号格式：1开头，11位数字
        return bool(re.match(r"^1[3-9]\d{9}$", phone))

    def _generate_code(self) -> str:
        """生成6位随机验证码"""
        return str(random.randint(100000, 999999))

    def _get_today_str(self) -> str:
        """获取今天的日期字符串"""
        return datetime.now().strftime("%Y-%m-%d")

    def _get_phone_data(self, phone: str) -> Dict:
        """获取手机号的存储数据，自动清理过期数据"""
        data = self._code_store.get(phone)
        today = self._get_today_str()

        if data is None or data.get("date") != today:
            # 新的一天，重置发送次数
            data = {
                "date": today,
                "code": "",
                "expire_at": 0,
                "send_count": 0,
                "last_send_time": 0,
            }
            self._code_store[phone] = data

        return data

    async def send_code(self, phone: str, scene: str = "register") -> Tuple[bool, str]:
        """
        发送短信验证码

        Args:
            phone: 手机号
            scene: 场景（register/login/reset）

        Returns:
            (success, message): 是否成功，提示信息
        """
        # 检查服务是否启用
        if not self.enabled:
            return False, "短信验证码服务未启用"

        # 验证手机号格式
        if not self._validate_phone(phone):
            return False, "手机号格式不正确"

        # 获取手机号数据
        data = self._get_phone_data(phone)
        now = time.time()

        # 检查发送间隔
        if data.get("last_send_time", 0) > 0:
            interval = now - data["last_send_time"]
            if interval < self.send_interval:
                wait_seconds = int(self.send_interval - interval)
                return False, f"发送过于频繁，请在{wait_seconds}秒后重试"

        # 检查每日发送次数
        if data.get("send_count", 0) >= self.daily_limit:
            return False, f"今日验证码发送次数已达上限（{self.daily_limit}次），请明天再试"

        # 生成验证码
        code = self._generate_code()

        # 构建短信内容
        if scene == "register":
            content = f"{self.sign}您正在注册账号，验证码是{code}，{int(self.code_expire/60)}分钟内有效，请勿泄露给他人。"
        elif scene == "login":
            content = f"{self.sign}您正在登录，验证码是{code}，{int(self.code_expire/60)}分钟内有效，请勿泄露给他人。"
        elif scene == "reset":
            content = f"{self.sign}您正在重置密码，验证码是{code}，{int(self.code_expire/60)}分钟内有效，请勿泄露给他人。"
        else:
            content = f"{self.sign}您的验证码是{code}，{int(self.code_expire/60)}分钟内有效，请勿泄露给他人。"

        # 调用互亿无线API发送短信
        try:
            payload = {
                "account": self.api_id,
                "password": self.api_key,
                "mobile": phone,
                "content": content,
                "format": "json",
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(self.api_url, data=payload)
                response.raise_for_status()
                result = response.json()

            # 解析响应
            code_result = result.get("code", 0)
            if code_result == 2:
                # 发送成功
                data["code"] = code
                data["expire_at"] = now + self.code_expire
                data["send_count"] = data.get("send_count", 0) + 1
                data["last_send_time"] = now

                _sms_logger.info("sms_code_sent", extra={"fields": {
                    "phone": phone,
                    "scene": scene,
                    "send_count": data["send_count"],
                }})

                return True, "验证码发送成功"
            else:
                # 发送失败
                error_msg = result.get("msg", "未知错误")
                _sms_logger.warning("sms_code_send_failed", extra={"fields": {
                    "phone": phone,
                    "scene": scene,
                    "error_code": code_result,
                    "error_msg": error_msg,
                }})
                return False, f"验证码发送失败：{error_msg}"

        except Exception as e:
            _sms_logger.error("sms_code_send_exception", extra={"fields": {
                "phone": phone,
                "scene": scene,
                "error": str(e),
            }})
            return False, f"验证码发送失败：{str(e)}"

    def verify_code(self, phone: str, code: str) -> Tuple[bool, str]:
        """
        验证短信验证码

        Args:
            phone: 手机号
            code: 验证码

        Returns:
            (success, message): 是否验证成功，提示信息
        """
        # 验证手机号格式
        if not self._validate_phone(phone):
            return False, "手机号格式不正确"

        # 验证验证码格式
        if not code or len(code) != 6 or not code.isdigit():
            return False, "验证码格式不正确"

        # 获取手机号数据
        data = self._get_phone_data(phone)
        now = time.time()

        # 检查验证码是否存在
        if not data.get("code"):
            return False, "请先获取验证码"

        # 检查验证码是否过期
        if data.get("expire_at", 0) < now:
            return False, "验证码已过期，请重新获取"

        # 验证验证码
        if data["code"] != code:
            return False, "验证码错误"

        # 验证成功，清除验证码（一次性使用）
        data["code"] = ""
        data["expire_at"] = 0

        _sms_logger.info("sms_code_verified", extra={"fields": {
            "phone": phone,
        }})

        return True, "验证码验证成功"

    def get_remaining_count(self, phone: str) -> int:
        """获取手机号今日剩余发送次数"""
        if not self._validate_phone(phone):
            return 0
        data = self._get_phone_data(phone)
        return max(0, self.daily_limit - data.get("send_count", 0))

    def can_send(self, phone: str) -> Tuple[bool, str]:
        """检查是否可以发送验证码"""
        # 验证手机号格式
        if not self._validate_phone(phone):
            return False, "手机号格式不正确"

        # 获取手机号数据
        data = self._get_phone_data(phone)
        now = time.time()

        # 检查发送间隔
        if data.get("last_send_time", 0) > 0:
            interval = now - data["last_send_time"]
            if interval < self.send_interval:
                wait_seconds = int(self.send_interval - interval)
                return False, f"发送过于频繁，请在{wait_seconds}秒后重试"

        # 检查每日发送次数
        if data.get("send_count", 0) >= self.daily_limit:
            return False, f"今日验证码发送次数已达上限（{self.daily_limit}次），请明天再试"

        return True, "可以发送"


# 单例
_sms_service: Optional[SMSService] = None


def get_sms_service() -> SMSService:
    """获取短信服务单例"""
    global _sms_service
    if _sms_service is None:
        _sms_service = SMSService()
    return _sms_service
