"""Listar todos los chats/canales de la cuenta."""

import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient


async def main():
    """Connect to Telegram and list all dialogs (chats, channels, groups)."""
    load_dotenv()

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]

    client = TelegramClient("list_chats_session", api_id, api_hash)
    await client.start()

    print(f"\nConectado como: {await client.get_me()}\n")
    print(f"{'ID':<15} {'Tipo':<12} {'Título':<40} {'Username'}")
    print("-" * 100)

    async for dialog in client.iter_dialogs():
        tipo = ""
        username = ""
        if dialog.is_channel:
            tipo = "Canal"
            username = dialog.entity.username or ""
        elif dialog.is_group:
            tipo = "Grupo"
            username = dialog.entity.username or ""
        else:
            tipo = "Privado"
            username = dialog.entity.username or ""

        print(f"{dialog.id:<15} {tipo:<12} {dialog.name:<40} {username}")

    await client.disconnect()


asyncio.run(main())
