"""Bus de eventos in-proc. Reemplaza los 3 sets de callbacks y 2 dicts de
clients que existían en `services/notifications.py` del monolito.

Reglas:
- Cada suscriptor tiene una `asyncio.Queue` por cada tipo al que se suscribe.
- `publish` es sync (set/get_item); los suscriptores leen de la queue async.
- Para tests o publishers sin loop, hay `publish_async` que encola en el loop
  activo (si lo hay) o crea un task efímero.
"""

import asyncio
from collections import defaultdict
from typing import Optional

from .tipos import EventoDominio, TODOS_LOS_TIPOS


class Bus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._cerrado = False

    def subscribe(self, tipo: str, *, maxsize: int = 0) -> asyncio.Queue:
        """Crea y registra una Queue para `tipo`. Devuelve la Queue.

        Acepta cualquier string (no solo los de `TODOS_LOS_TIPOS`) para
        permitir tipos ad-hoc como los que emite el polling de MP
        ('pago.confirmado', 'pago.cancelado').
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subs[tipo].add(q)
        return q

    def unsubscribe(self, tipo: str, q: asyncio.Queue) -> None:
        self._subs.get(tipo, set()).discard(q)

    def subscribe_all(self, *, maxsize: int = 0) -> dict[str, asyncio.Queue]:
        """Suscribe a todos los tipos a la vez. Útil para dashboards."""
        return {tipo: self.subscribe(tipo, maxsize=maxsize) for tipo in TODOS_LOS_TIPOS}

    def publish(self, evento: EventoDominio) -> int:
        """Encola el evento en todas las queues del tipo.

        Devuelve cuántos suscriptores recibieron el evento efectivamente.
        Si la queue está llena, el evento se descarta y NO se cuenta como recibido.
        """
        if self._cerrado:
            return 0
        queues = list(self._subs.get(evento.tipo, ()))
        recibidos = 0
        for q in queues:
            try:
                q.put_nowait(evento)
                recibidos += 1
            except asyncio.QueueFull:
                pass
        return recibidos

    async def publish_async(self, evento: EventoDominio) -> int:
        """Variante async. Si la queue está llena, espera.

        Devuelve cuántos suscriptores recibieron efectivamente. Si el bus
        está cerrado o el evento se descarta, no se cuenta.
        """
        if self._cerrado:
            return 0
        queues = list(self._subs.get(evento.tipo, ()))
        for q in queues:
            await q.put(evento)
        return len(queues)

    def stats(self) -> dict[str, int]:
        return {tipo: len(queues) for tipo, queues in self._subs.items()}

    def close(self) -> None:
        """Cierra el bus. Los `publish` posteriores son no-op."""
        self._cerrado = True


# Singleton del proceso. `bootstrap.py` lo inyecta a quien lo necesite
# (en lugar de importarlo directo, lo que facilita tests con buses frescos).
bus = Bus()


def reset_para_tests() -> None:
    """Devuelve el bus a un estado limpio. Solo para pytest."""
    global bus
    bus = Bus()
