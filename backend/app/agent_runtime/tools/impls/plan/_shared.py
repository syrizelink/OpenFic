from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlanTodoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, description="Deskripsi singkat tugas")
    status: Literal["pending", "in_progress", "completed"] = Field(
        description="Status saat ini"
    )
    priority: Literal["low", "medium", "high"] = Field(description="Prioritas")

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content tidak boleh kosong")
        return normalized


class WritePlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    todos: list[PlanTodoInput] = Field(
        description="Daftar Todo lengkap setelah diperbarui"
    )
