from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class QuickPrompt(SQLModel, table=True):
    __tablename__ = "quick_prompts"

    id: str = Field(default_factory=generate_id, primary_key=True)
    command: str
    content: str = ""
    scope: str = "global"
    project_id: str | None = Field(default=None, index=True)
