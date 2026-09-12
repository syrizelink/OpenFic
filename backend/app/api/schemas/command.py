from typing import Literal

from pydantic import BaseModel, Field


class CommandCandidateItem(BaseModel):
    kind: Literal["skill"] = Field(description="Tipe perintah")
    id: str = Field(description="ID objek terkait perintah")
    name: str = Field(description="Nama perintah")
    description: str = Field(description="Keterangan perintah")


class CommandSearchResponse(BaseModel):
    items: list[CommandCandidateItem] = Field(description="Kandidat perintah")
