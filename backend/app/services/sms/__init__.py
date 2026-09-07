"""
短信验证码服务模块（互亿无线）

支持手机号验证码发送、验证、限流等功能。
"""

from .sms_service import SMSService, get_sms_service

__all__ = ["SMSService", "get_sms_service"]
