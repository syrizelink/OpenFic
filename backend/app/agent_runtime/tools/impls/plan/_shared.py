from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlanTodoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, description="任务的简短描述")
    status: Literal["pending", "in_progress", "completed"] = Field(description="当前状态")
    priority: Literal["low", "medium", "high"] = Field(description="优先级")

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content 不能为空")
        return normalized


class WritePlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    todos: list[PlanTodoInput] = Field(description="更新后的完整 Todo 列表")
