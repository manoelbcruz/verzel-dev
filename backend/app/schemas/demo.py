from app.schemas.auth import Papel
from app.schemas.comum import Schema


class ContaDemo(Schema):
    papel: Papel
    email: str
    rotulo: str


class ContasDemo(Schema):
    contas: list[ContaDemo]
    senha: str | None
