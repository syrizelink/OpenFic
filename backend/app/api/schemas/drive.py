"""Google Drive 同步 API 数据模型。"""

from pydantic import BaseModel, Field


class DriveConfigResponse(BaseModel):
    """同步面板全局状态。"""

    has_credentials: bool
    connected: bool
    email: str | None = None
    folder_id: str | None = None
    interval_minutes: int
    redirect_uri: str


class DriveConfigUpdate(BaseModel):
    """更新 Google 客户端凭据或同步间隔。"""

    client_id: str | None = Field(default=None)
    client_secret: str | None = Field(default=None)
    interval_minutes: int | None = Field(default=None, ge=1, le=1440)


class DriveAuthUrlResponse(BaseModel):
    """授权链接。"""

    auth_url: str
    redirect_uri: str


class DriveProjectStatus(BaseModel):
    """单个项目的同步状态。"""

    project_id: str
    project_title: str
    connected: bool
    enabled: bool
    file_id: str | None = None
    doc_url: str | None = None
    last_synced_at: str | None = None
    chapter_count: int = 0
    word_count: int = 0
    error_message: str | None = None


class DriveProjectUpdate(BaseModel):
    """开启/关闭项目的自动同步。"""

    enabled: bool


class DriveSyncResult(BaseModel):
    """一次同步的结果。"""

    project_id: str
    status: str  # "synced" | "unchanged" | "error"
    file_id: str | None = None
    doc_name: str | None = None
    doc_url: str | None = None
    chapter_count: int = 0
    word_count: int = 0
    synced_at: str | None = None
    message: str | None = None
