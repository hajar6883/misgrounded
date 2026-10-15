"""Chargement du bordereau, des pieces et de la verite terrain."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from .chemins import BORDEREAU, PIECES, VERITE_TERRAIN


@dataclass(frozen=True)
class Piece:
    cote: int
    doc_id: str
    fichier: str
    titre: str
    nature: str
    date_piece: str
    # Genere par le modele a partir de la piece, puis verifie : c'est une
    # surface de controle a part entiere, pas une simple etiquette.
    resume: str = ""

    @property
    def texte(self) -> str:
        return (PIECES / self.fichier).read_text(encoding="utf-8")


@dataclass(frozen=True)
class Fait:
    fact_id: str
    doc_id: str
    type: str
    valeur: str
    libelle: str
    extrait: str


@lru_cache(maxsize=1)
def charger_bordereau() -> tuple[Piece, ...]:
    brut = json.loads(BORDEREAU.read_text(encoding="utf-8"))
    pieces = tuple(Piece(**p) for p in brut["pieces"])
    return tuple(sorted(pieces, key=lambda p: p.cote))


@lru_cache(maxsize=1)
def charger_verite_terrain() -> tuple[Fait, ...]:
    brut = json.loads(VERITE_TERRAIN.read_text(encoding="utf-8"))
    return tuple(Fait(**f) for f in brut["faits"])


def par_cote() -> dict[int, Piece]:
    return {p.cote: p for p in charger_bordereau()}


def par_doc_id() -> dict[str, Piece]:
    return {p.doc_id: p for p in charger_bordereau()}


def corpus_complet() -> str:
    """Toutes les pieces concatenees, chacune annoncee par sa cote et son doc_id.

    C'est ce qu'on donne au redacteur de l'acte. Le juge, lui, ne recevra
    jamais cela : il ne voit qu'une piece a la fois.
    """
    blocs = []
    for p in charger_bordereau():
        blocs.append(
            f"=== PIECE N° {p.cote} — {p.titre} "
            f"(identifiant interne : {p.doc_id}) ===\n\n{p.texte}"
        )
    return "\n\n".join(blocs)


def bordereau_lisible() -> str:
    lignes = ["| Cote | Intitulé | Date |", "|---|---|---|"]
    for p in charger_bordereau():
        lignes.append(f"| n° {p.cote} | {p.titre} | {p.date_piece} |")
    return "\n".join(lignes)
