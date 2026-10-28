import json
from dataclasses import asdict

import anyio

from app.core.config import get_settings
from app.demo.seed import garantir_demonstracao
from app.recursos import abrir_recursos


async def main():
    settings = get_settings().model_copy(update={"seed_demo": False})
    async with abrir_recursos(settings, iniciar_worker=False) as recursos:
        print(json.dumps(asdict(await garantir_demonstracao(recursos)), ensure_ascii=False))


if __name__ == "__main__":
    anyio.run(main)
