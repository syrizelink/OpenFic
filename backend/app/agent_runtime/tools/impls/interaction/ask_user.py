import json

from pydantic import BaseModel, Field
from langgraph.types import interrupt

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry


class QuestionOption(BaseModel):
    label: str = Field(description="选项显示文本，应简洁明了")
    description: str = Field(description="选项说明")


class Question(BaseModel):
    title: str = Field(description="完整的问题")
    description: str = Field(description="具体详细的问题说明")
    options: list[QuestionOption] = Field(
        description="可选项，如有建议选项，将其放在首位",
    )

class AskUserInput(BaseModel):
    questions: list[Question] = Field(
        description="问题列表，同一批问题之间不得存在答案依赖关系",
    )

@ToolRegistry.register
class AskUserTool(AgentTool):
    name: str = "ask_user"
    description: str = (
        "向用户提问时使用本工具。"
        ""
        "何时使用："
        "- 收集用户偏好或需求"
        "- 澄清含糊的指令"
        "- 在工作过程中，就实现方案做出决策"
        ""
        "使用说明："
        "- 同一批问题之间不得存在依赖（有依赖时分批提问）"
        "- 每个问题可提供选项以引导用户选择，你建议的选项应放在首位，并添加`(推荐)`后缀"
        "- 无论是否给出选项，系统都会自动添加`自行输入答案`的选项提供给用户，因此在提出一个开放式问题时，不要包含`其它`或类似的兜底选项"
    )
    access_level: str = "readonly"
    args_schema: type[BaseModel] = AskUserInput

    async def _execute(self, questions: list[Question]) -> str:
        payload = {
            "type": "ask_user",
            "questions": [question.model_dump(mode="json") for question in questions],
        }
        response = interrupt(payload)
        answers = response.get("answer") if isinstance(response, dict) else None
        return json.dumps(answers if isinstance(answers, list) else [], ensure_ascii=False)
