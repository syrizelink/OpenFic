from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


PLAN_STATUSES = ("pending", "in_progress", "completed")


class PlanTodoTextInput(BaseModel):
    title: str = Field(min_length=1, description="Todo 标题")
    content: str = Field(min_length=1, description="Todo 内容")

    @classmethod
    def _normalize_text(cls, value: str, *, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} 不能为空")
        return normalized

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return cls._normalize_text(value, field_name="title")

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return cls._normalize_text(value, field_name="content")


class PlanTodoCreateInput(PlanTodoTextInput):
    pass


class CreatePlanInput(BaseModel):
    topic: str = Field(min_length=1, description="计划主题")
    description: str = Field(min_length=1, description="计划描述")
    todos: list[PlanTodoCreateInput] = Field(description="初始 Todo 列表")

    @field_validator("todos")
    @classmethod
    def validate_todos(cls, value: list[PlanTodoCreateInput]) -> list[PlanTodoCreateInput]:
        if not value:
            raise ValueError("todos 至少需要 1 项")
        return value


class PlanTodoMatchInput(PlanTodoTextInput):
    id: str = Field(min_length=1, description="Todo ID")
    status: Literal["pending", "in_progress", "completed"] = Field(description="Todo 状态")


class PlanTodoEditInput(PlanTodoTextInput):
    id: str | None = Field(default=None, description="Todo ID；新 Todo 可省略")
    status: Literal["pending", "in_progress", "completed"] | None = Field(
        default=None,
        description="Todo 状态；新 Todo 会被强制置为 pending",
    )


class UpdatePlanInput(BaseModel):
    plan_id: str = Field(min_length=1, description="计划ID")
    old_todos: list[PlanTodoMatchInput] = Field(description="要被替换的旧 Todo 切片")
    new_todos: list[PlanTodoEditInput] = Field(default_factory=list, description="替换后的 Todo 列表")

    @field_validator("old_todos")
    @classmethod
    def validate_old_todos(cls, value: list[PlanTodoMatchInput]) -> list[PlanTodoMatchInput]:
        if not value:
            raise ValueError("old_todos 至少需要 1 项")
        return value


class GetPlanInput(BaseModel):
    plan_id: str = Field(min_length=1, description="计划ID")


class ListPlanInput(BaseModel):
    pass
