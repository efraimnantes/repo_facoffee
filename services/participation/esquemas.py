import pydantic
from typing import Optional

class requestcriarcota(pydantic.BaseModel):
    name: str
    condition: str
    items: str
    amount: float = pydantic.Field(ge=0)
    active: bool = True

class requestatualizarcota(pydantic.BaseModel):
    name: Optional[str] = None
    condition: Optional[str] = None
    items: Optional[str] = None
    amount: Optional[float] = pydantic.Field(None, ge=0)
    active: Optional[bool] = None

class requestadesao(pydantic.BaseModel):
    userid: str = pydantic.Field(alias="userId")
    quotaid: str = pydantic.Field(alias="quotaId")
    startcycle: str = pydantic.Field(alias="startCycle", pattern=r"^\d{4}-\d{2}$")

class requestcancelamento(pydantic.BaseModel):
    requestedby: str = pydantic.Field(alias="requestedBy")
    reason: str
    effectivecycle: Optional[str] = pydantic.Field(None, alias="effectiveCycle", pattern=r"^\d{4}-\d{2}$")