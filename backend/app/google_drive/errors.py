# -*- coding: utf-8 -*-
"""
Google Drive 同步异常。
"""


class DriveError(Exception):
    """Google Drive 同步基础异常。"""


class DriveNotConfiguredError(DriveError):
    """未配置 Google OAuth 客户端凭据。"""


class DriveNotConnectedError(DriveError):
    """尚未完成 Google 授权。"""


class DriveAuthError(DriveError):
    """token 失效或授权被撤销。"""


class DriveApiError(DriveError):
    """Google Drive API 调用失败。"""
