"""Räumt private (ephemeral) Antworten automatisch auf.

Der Bot kann ephemere Nachrichten nicht nachträglich auflisten — wohl aber die
Antwort einer Interaktion löschen, solange deren Token gültig ist (15 Minuten).
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

import discord

# Menüs bleiben so lange offen (unter dem 15-Minuten-Limit der Interaktion).
MENU_TTL = 600
# Kurze Bestätigungen („Rolle hinzugefügt“) verschwinden fast sofort.
CONFIRM_TTL = 10

_pending: set[asyncio.Task[Any]] = set()


def _delete_later(delete: Callable[[], Awaitable[Any]], delay: float) -> None:
    async def _run() -> None:
        await asyncio.sleep(delay)
        try:
            await delete()
        except discord.HTTPException:
            # Schon geschlossen/gelöscht, Token abgelaufen oder gar keine
            # Nachricht (z. B. Modal) — alles egal.
            pass

    task = asyncio.get_running_loop().create_task(_run())
    _pending.add(task)
    task.add_done_callback(_pending.discard)


def schedule_response_cleanup(
    interaction: discord.Interaction, delay: float = MENU_TTL
) -> None:
    """Löscht die Antwort auf ``interaction`` nach ``delay`` Sekunden."""
    _delete_later(interaction.delete_original_response, delay)


def schedule_message_cleanup(message: Any, delay: float = CONFIRM_TTL) -> None:
    """Löscht eine per ``followup.send(..., wait=True)`` gesendete Nachricht."""
    _delete_later(message.delete, delay)
