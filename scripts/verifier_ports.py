"""Contrôle qu'aucune instance ne tourne déjà avant de démarrer.

Deux versions de l'application lancées en même temps produisent le pire des cas :
l'interface neuve dialogue avec l'ancien moteur resté sur le port 8000, sans
qu'aucune erreur ne le signale. On refuse de démarrer dans ce cas.

Code de retour : 0 si la voie est libre, 1 si un port est déjà occupé.
"""

from __future__ import annotations

import socket
import sys

PORTS = {8000: "le moteur", 3000: "l'interface"}


def occupied(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.6)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    busy = {port: role for port, role in PORTS.items() if occupied(port)}
    if not busy:
        return 0

    print()
    for port, role in busy.items():
        print(f"  Le port {port} ({role}) est deja utilise.")
    print()
    print("  Une autre instance de l'application tourne encore.")
    print("  Fermez toutes les fenetres noires « Palab » ainsi que les onglets")
    print("  du navigateur sur localhost:3000, puis relancez ce fichier.")
    print()
    print("  Si vous ne trouvez pas la fenetre : redemarrez l'ordinateur,")
    print("  c'est la facon la plus sure de tout arreter.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
