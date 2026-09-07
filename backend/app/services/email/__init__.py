"""
邮箱验证码服务模块（SMTP）

支持邮箱验证码发送、验证、限流等功能。
使用个人邮箱的SMTP服务，免费且接入简单。
"""

from .email_service import EmailService, get_email_service

__all__ = ["EmailService", "get_email_service"]
