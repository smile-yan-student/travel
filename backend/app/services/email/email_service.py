"""
邮箱验证码服务（SMTP）

功能：
- 发送邮箱验证码
- 验证邮箱验证码
- 发送频率限制（同一邮箱60秒内只能发一次）
- 每日发送次数限制
- 验证码有效期管理

使用个人邮箱的SMTP服务，免费且接入简单。
支持QQ邮箱、163邮箱、Gmail等。
"""

import random
import re
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Dict, Optional, Tuple

from ...config import settings
from ...infrastructure.logger import get_logger

_email_logger = get_logger("email")


class EmailService:
    """邮箱验证码服务"""

    def __init__(self):
        self.enabled = settings.email.email_enabled
        self.smtp_host = settings.email.smtp_host
        self.smtp_port = settings.email.smtp_port
        self.smtp_user = settings.email.smtp_user
        self.smtp_password = settings.email.smtp_password
        self.sender_name = settings.email.sender_name
        self.code_expire = settings.email.email_code_expire
        self.send_interval = settings.email.email_send_interval
        self.daily_limit = settings.email.email_daily_limit

        # 内存存储验证码（生产环境建议使用Redis）
        # 格式：{email: {"code": "123456", "expire_at": timestamp, "send_count": 0, "last_send_time": timestamp}}
        self._code_store: Dict[str, Dict] = {}

    def _validate_email(self, email: str) -> bool:
        """验证邮箱格式是否正确"""
        if not email:
            return False
        # 简单的邮箱格式验证
        return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))

    def _generate_code(self) -> str:
        """生成6位随机验证码"""
        return str(random.randint(100000, 999999))

    def _get_today_str(self) -> str:
        """获取今天的日期字符串"""
        return datetime.now().strftime("%Y-%m-%d")

    def _get_email_data(self, email: str) -> Dict:
        """获取邮箱的存储数据，自动清理过期数据"""
        data = self._code_store.get(email)
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
            self._code_store[email] = data

        return data

    def _send_email(self, to_email: str, subject: str, content: str) -> Tuple[bool, str]:
        """
        发送邮件

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            content: 邮件内容（HTML格式）

        Returns:
            (success, message): 是否成功，提示信息
        """
        try:
            # 创建邮件
            from email.utils import formataddr
            msg = MIMEMultipart()
            # 使用formataddr格式化发件人地址（名称会自动编码，邮箱地址保持原样）
            msg['From'] = formataddr((self.sender_name, self.smtp_user))
            msg['To'] = to_email
            msg['Subject'] = Header(subject, 'utf-8')

            # 添加邮件正文
            msg.attach(MIMEText(content, 'html', 'utf-8'))

            # 连接SMTP服务器并发送
            if self.smtp_port == 465:
                # SSL连接
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
            else:
                # 普通连接或TLS连接
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
                if self.smtp_port == 587:
                    server.starttls()

            server.login(self.smtp_user, self.smtp_password)
            server.sendmail(self.smtp_user, [to_email], msg.as_string())
            server.quit()

            return True, "邮件发送成功"

        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP认证失败：请检查邮箱地址和授权码是否正确。错误详情：{str(e)}"
            _email_logger.error("email_auth_failed", extra={"fields": {
                "to_email": to_email,
                "error": str(e),
            }})
            return False, error_msg
        except smtplib.SMTPException as e:
            error_msg = f"邮件发送失败：{str(e)}"
            _email_logger.error("email_send_smtp_error", extra={"fields": {
                "to_email": to_email,
                "error": str(e),
            }})
            return False, error_msg
        except Exception as e:
            error_msg = f"邮件发送异常：{str(e)}"
            _email_logger.error("email_send_exception", extra={"fields": {
                "to_email": to_email,
                "error": str(e),
            }})
            return False, error_msg

    async def send_code(self, email: str, scene: str = "login") -> Tuple[bool, str]:
        """
        发送邮箱验证码

        Args:
            email: 邮箱地址
            scene: 场景（register/login/reset）

        Returns:
            (success, message): 是否成功，提示信息
        """
        # 检查服务是否启用
        if not self.enabled:
            return False, "邮箱验证码服务未启用"

        # 验证邮箱格式
        if not self._validate_email(email):
            return False, "邮箱格式不正确"

        # 获取邮箱数据
        data = self._get_email_data(email)
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

        # 构建邮件内容
        if scene == "register":
            subject = f"{self.sender_name} - 注册验证码"
            content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                    <h2 style="color: white; margin: 0;">{self.sender_name}</h2>
                    <p style="color: rgba(255,255,255,0.8); margin: 10px 0 0 0;">注册验证码</p>
                </div>
                <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 16px; color: #333;">您好，</p>
                    <p style="font-size: 16px; color: #333;">您正在注册 {self.sender_name} 账号，验证码是：</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <span style="font-size: 36px; font-weight: bold; color: #667eea; letter-spacing: 8px;">{code}</span>
                    </div>
                    <p style="font-size: 14px; color: #666;">验证码有效期为 {int(self.code_expire/60)} 分钟，请勿泄露给他人。</p>
                    <p style="font-size: 14px; color: #999; margin-top: 30px;">如果这不是您的操作，请忽略此邮件。</p>
                </div>
            </div>
            """
        elif scene == "login":
            subject = f"{self.sender_name} - 登录验证码"
            content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                    <h2 style="color: white; margin: 0;">{self.sender_name}</h2>
                    <p style="color: rgba(255,255,255,0.8); margin: 10px 0 0 0;">登录验证码</p>
                </div>
                <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 16px; color: #333;">您好，</p>
                    <p style="font-size: 16px; color: #333;">您正在登录 {self.sender_name}，验证码是：</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <span style="font-size: 36px; font-weight: bold; color: #667eea; letter-spacing: 8px;">{code}</span>
                    </div>
                    <p style="font-size: 14px; color: #666;">验证码有效期为 {int(self.code_expire/60)} 分钟，请勿泄露给他人。</p>
                    <p style="font-size: 14px; color: #999; margin-top: 30px;">如果这不是您的操作，请忽略此邮件。</p>
                </div>
            </div>
            """
        else:
            subject = f"{self.sender_name} - 验证码"
            content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                    <h2 style="color: white; margin: 0;">{self.sender_name}</h2>
                    <p style="color: rgba(255,255,255,0.8); margin: 10px 0 0 0;">验证码</p>
                </div>
                <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 16px; color: #333;">您好，</p>
                    <p style="font-size: 16px; color: #333;">您的验证码是：</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <span style="font-size: 36px; font-weight: bold; color: #667eea; letter-spacing: 8px;">{code}</span>
                    </div>
                    <p style="font-size: 14px; color: #666;">验证码有效期为 {int(self.code_expire/60)} 分钟，请勿泄露给他人。</p>
                    <p style="font-size: 14px; color: #999; margin-top: 30px;">如果这不是您的操作，请忽略此邮件。</p>
                </div>
            </div>
            """

        # 发送邮件
        success, msg = self._send_email(email, subject, content)
        if not success:
            return False, msg

        # 发送成功，保存验证码
        data["code"] = code
        data["expire_at"] = now + self.code_expire
        data["send_count"] = data.get("send_count", 0) + 1
        data["last_send_time"] = now

        _email_logger.info("email_code_sent", extra={"fields": {
            "email": email,
            "scene": scene,
            "send_count": data["send_count"],
        }})

        return True, "验证码发送成功，请注意查收邮件"

    def verify_code(self, email: str, code: str) -> Tuple[bool, str]:
        """
        验证邮箱验证码

        Args:
            email: 邮箱地址
            code: 验证码

        Returns:
            (success, message): 是否验证成功，提示信息
        """
        # 验证邮箱格式
        if not self._validate_email(email):
            return False, "邮箱格式不正确"

        # 验证验证码格式
        if not code or len(code) != 6 or not code.isdigit():
            return False, "验证码格式不正确"

        # 获取邮箱数据
        data = self._get_email_data(email)
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

        _email_logger.info("email_code_verified", extra={"fields": {
            "email": email,
        }})

        return True, "验证码验证成功"

    def get_remaining_count(self, email: str) -> int:
        """获取邮箱今日剩余发送次数"""
        if not self._validate_email(email):
            return 0
        data = self._get_email_data(email)
        return max(0, self.daily_limit - data.get("send_count", 0))

    def can_send(self, email: str) -> Tuple[bool, str]:
        """检查是否可以发送验证码"""
        # 验证邮箱格式
        if not self._validate_email(email):
            return False, "邮箱格式不正确"

        # 获取邮箱数据
        data = self._get_email_data(email)
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
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """获取邮箱服务单例"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
