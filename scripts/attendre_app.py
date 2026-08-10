"""Attend que l'interface réponde et écrit son adresse sur la sortie standard.

Le serveur de développement bascule automatiquement sur le port suivant quand
3000 est déjà occupé. Ouvrir une adresse figée enverrait alors l'utilisateur sur
une page vide, ou pire sur l'application d'un autre logiciel. On sonde donc les
ports candidats et on ne retient que celui qui répond *notre* application.

Sortie : l'URL trouvée, ou rien du tout si l'application n'a pas démarré.
Code de retour : 0 si trouvée, 1 sinon.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

PORTS = range(3000, 3011)
TIMEOUT_SECONDS = 90.0
SIGNATURE = "openai_configured"


def responds(port: int) -> bool:
    """Vrai seulement si ce port sert bien notre interface.

    On interroge l'API de santé à travers le proxy du serveur de développement :
    aucune autre application ne renverra cette signature.
    """
    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}/api/health", timeout=1.5
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return False
    return SIGNATURE in payload


def main() -> int:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        for port in PORTS:
            if responds(port):
                print(f"http://localhost:{port}")
                return 0
        time.sleep(0.5)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
