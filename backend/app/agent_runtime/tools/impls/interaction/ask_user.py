import json

from pydantic import BaseModel, Field, field_validator
from langgraph.types import interrupt

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry


class QuestionOption(BaseModel):
    label: str = Field(description="选项标签")
    description: str = Field(description="该选项对应的简短说明")


class Question(BaseModel):
    title: str = Field(description="问题文本")
    description: str = Field(description="具体详细的问题说明")
    options: list[QuestionOption] = Field(
        description="可选项列表，数量必须为2-3个；如有建议选项，将其放在首位",
    )

    @field_validator("options")
    @classmethod
    def validate_options_count(cls, v):
        if len(v) < 2 or len(v) > 3:
            raise ValueError("可选项数量必须为 2-3 个")
        return v


class AskUserInput(BaseModel):
    questions: list[Question] = Field(
        description="问题列表，数量必须为1-5个；同一批问题之间不得存在答案依赖关系",
    )

    @field_validator("questions")
    @classmethod
    def validate_questions_count(cls, v):
        if len(v) < 1 or len(v) > 5:
            raise ValueError("questions 数量必须为 1-5 个")
        return v


@ToolRegistry.register
class AskUserTool(AgentTool):
    name: str = "ask_user"
    description: str = """向用户提问，这是你向用户提出任何问题的唯一方式，不要在正文里直接发问。

    一次最多提出5个问题，问题之间不得存在答案依赖（有依赖时分批提问）。
    每个问题可给2-3个选项以引导回答，建议选项放在首位。
    无论是否给出选项，用户都可以自行作答，因此也适用于开放式问题。"""
    access_level: str = "readonly"
    args_schema: type[BaseModel] = AskUserInput

    async def _execute(self, questions: list[dict]) -> str:
        payload = {
            "type": "ask_user",
            "questions": questions,
        }
        response = interrupt(payload)
        return json.dumps(response, ensure_ascii=False)
