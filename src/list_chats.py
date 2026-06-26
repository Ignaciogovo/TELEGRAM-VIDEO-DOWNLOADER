"""Listar todos los chats/canales de la cuenta.

Uso:
    python src/list_chats.py                    # Lista todos los chats en formato tabla
    python src/list_chats.py --search NOMBRE    # Busca por nombre y devuelve solo el ID
"""

import argparse
import asyncio
import os
import sys
from dotenv import load_dotenv
from telethon import TelegramClient


async def list_chats_main(search: str | None, session_name: str) -> int:
    """Lista chats o busca uno por nombre.

    Args:
        search: Texto a buscar en el nombre (case-insensitive). Si es None, lista todos.
        session_name: Nombre/ruta de la sesion telethon (ej. "session_data/telegram_downloader").

    Returns:
        Codigo de salida (0 = ok, 1 = error de busqueda).
    """
    if not os.environ.get("TELEGRAM_API_ID"):
        load_dotenv()

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]

    async with TelegramClient(session_name, api_id, api_hash) as client:
        me = await client.get_me()
        dialogs = [d async for d in client.iter_dialogs()]

        if search is not None:
            needle = search.lower()
            matches = [d for d in dialogs if needle in d.name.lower()]
            if len(matches) == 1:
                print(matches[0].id)
                return 0
            if len(matches) > 1:
                print(
                    f"Multiples coincidencias para '{search}':",
                    file=sys.stderr,
                )
                for d in matches:
                    print(f"  {d.id}\t{d.name}", file=sys.stderr)
                return 1
            print(f"Ningun chat coincide con: {search}", file=sys.stderr)
            return 1

        print(f"\nConectado como: {me}\n")
        print(f"{'ID':<15} {'Tipo':<12} {'Título':<40} {'Username'}")
        print("-" * 100)
        for dialog in dialogs:
            if dialog.is_channel:
                tipo = "Canal"
            elif dialog.is_group:
                tipo = "Grupo"
            else:
                tipo = "Privado"
            username = getattr(dialog.entity, "username", None) or ""
            print(f"{dialog.id:<15} {tipo:<12} {dialog.name:<40} {username}")
        return 0


async def main() -> None:
    parser = argparse.ArgumentParser(description="Listar chats de Telegram")
    parser.add_argument(
        "--search",
        type=str,
        default=None,
        help="Buscar chat por nombre (coincidencia parcial) e imprimir su ID",
    )
    args = parser.parse_args()
    rc = await list_chats_main(args.search, "telegram_downloader")
    sys.exit(rc)


if __name__ == "__main__":
    asyncio.run(main())
