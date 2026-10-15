"""Derive de renumerotation, et la parade par identifiant stable.

Une cote est un rang d'affichage, pas une identite : inserer une piece decale
toutes les suivantes, sans qu'aucune erreur ne soit levee. L'acte reference
donc `{{doc:D-xxx}}`, et la cote n'est calculee qu'a l'export.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .dossier import Piece, charger_bordereau

# Le formatage du modele varie : pluriel, majuscule, espaces insecables.
# Groupe 1 : le mot « pièce(s) ». Groupe 2 : la cote.
CITATION = re.compile(r"(pièces?)\s*n\s*°\s*(\d+)", re.IGNORECASE)
JETON_STABLE = re.compile(r"\{\{doc:([A-Z0-9-]+)\}\}")

# La piece qu'on insere : un constat d'huissier, posterieur a la redaction de
# l'acte. Cas parfaitement ordinaire -- c'est ce qui le rend dangereux.
PIECE_INSEREE = Piece(
    cote=3,
    doc_id="D-CST-011",
    fichier="P11_constat_huissier.md",
    titre="Constat d'huissier du 25/11/2024 sur l'état du module stocks",
    nature="constat",
    date_piece="2024-11-25",
)


@dataclass(frozen=True)
class Derive:
    """Resultat d'une mesure de derive sur un acte."""

    citations: int
    cassees: int
    details: tuple[tuple[int, str, str], ...]  # (cote citee, doc attendu, doc obtenu)

    @property
    def taux(self) -> float:
        return self.cassees / self.citations if self.citations else 0.0


def inserer_piece(
    bordereau: tuple[Piece, ...] | None = None,
    nouvelle: Piece = PIECE_INSEREE,
) -> tuple[Piece, ...]:
    """Insere une piece a sa cote et decale toutes les suivantes de +1."""
    bordereau = bordereau or charger_bordereau()
    decalees = [
        replace(p, cote=p.cote + 1) if p.cote >= nouvelle.cote else p
        for p in bordereau
    ]
    return tuple(sorted([*decalees, nouvelle], key=lambda p: p.cote))


def cotes_citees(acte: str) -> list[int]:
    """Toutes les cotes citees par l'acte, dans l'ordre d'apparition."""
    return [int(n) for _, n in CITATION.findall(acte)]


def _index_par_cote(bordereau: tuple[Piece, ...]) -> dict[int, str]:
    return {p.cote: p.doc_id for p in bordereau}


def _index_par_doc_id(bordereau: tuple[Piece, ...]) -> dict[str, int]:
    return {p.doc_id: p.cote for p in bordereau}


# --- Version naive : la cote est ecrite en dur dans l'acte -------------------


def derive_naive(
    acte: str,
    avant: tuple[Piece, ...] | None = None,
    apres: tuple[Piece, ...] | None = None,
) -> Derive:
    """Compte les citations qui designent un autre document apres insertion.

    L'acte n'est pas modifie : c'est tout le probleme. Le texte « pièce n° 6 »
    reste identique, mais la piece n° 6 n'est plus la meme.
    """
    avant = avant or charger_bordereau()
    apres = apres if apres is not None else inserer_piece(avant)

    doc_avant = _index_par_cote(avant)
    doc_apres = _index_par_cote(apres)

    details = []
    for cote in cotes_citees(acte):
        attendu = doc_avant.get(cote, "<cote inexistante>")
        obtenu = doc_apres.get(cote, "<cote inexistante>")
        if attendu != obtenu:
            details.append((cote, attendu, obtenu))

    return Derive(
        citations=len(cotes_citees(acte)),
        cassees=len(details),
        details=tuple(details),
    )


# --- Version protegee : identifiant stable, cote calculee a l'export ---------


def vers_identifiants_stables(
    acte: str, bordereau: tuple[Piece, ...] | None = None
) -> str:
    """Remplace chaque « pièce n° X » par « pièce {{doc:D-XXX}} ».

    C'est la forme interne de l'acte : celle qu'on stocke et qu'on edite.
    """
    bordereau = bordereau or charger_bordereau()
    doc_par_cote = _index_par_cote(bordereau)

    def remplacer(m: re.Match[str]) -> str:
        doc_id = doc_par_cote.get(int(m.group(2)))
        if doc_id is None:
            return m.group(0)  # cote inconnue : on n'invente rien
        return f"{m.group(1)} {{{{doc:{doc_id}}}}}"

    return CITATION.sub(remplacer, acte)


def exporter(acte_stable: str, bordereau: tuple[Piece, ...] | None = None) -> str:
    """Rend l'acte lisible en recalculant les cotes depuis le bordereau donne."""
    bordereau = bordereau or charger_bordereau()
    cote_par_doc = _index_par_doc_id(bordereau)

    def remplacer(m: re.Match[str]) -> str:
        cote = cote_par_doc.get(m.group(1))
        return f"n° {cote}" if cote is not None else m.group(0)

    return JETON_STABLE.sub(remplacer, acte_stable)


def derive_protegee(
    acte: str,
    avant: tuple[Piece, ...] | None = None,
    apres: tuple[Piece, ...] | None = None,
) -> Derive:
    """Meme mesure, mais sur un acte qui reference des identifiants stables."""
    avant = avant or charger_bordereau()
    apres = apres if apres is not None else inserer_piece(avant)

    stable = vers_identifiants_stables(acte, avant)
    reexporte = exporter(stable, apres)

    doc_avant = _index_par_cote(avant)
    doc_apres = _index_par_cote(apres)

    details = []
    for cote_origine, cote_reexportee in zip(
        cotes_citees(acte), cotes_citees(reexporte), strict=True
    ):
        attendu = doc_avant.get(cote_origine, "<cote inexistante>")
        obtenu = doc_apres.get(cote_reexportee, "<cote inexistante>")
        if attendu != obtenu:
            details.append((cote_origine, attendu, obtenu))

    return Derive(
        citations=len(cotes_citees(acte)),
        cassees=len(details),
        details=tuple(details),
    )


def comparer(acte: str) -> dict:
    """Le chiffre du README : naif contre identifiant stable."""
    avant = charger_bordereau()
    apres = inserer_piece(avant)
    naive = derive_naive(acte, avant, apres)
    protegee = derive_protegee(acte, avant, apres)
    return {
        "piece_inseree": {
            "cote": PIECE_INSEREE.cote,
            "doc_id": PIECE_INSEREE.doc_id,
            "titre": PIECE_INSEREE.titre,
        },
        "citations_dans_l_acte": naive.citations,
        "naif": {
            "citations_cassees": naive.cassees,
            "taux": round(naive.taux, 4),
            "details": [
                {"cote_citee": c, "doc_attendu": a, "doc_obtenu": o}
                for c, a, o in naive.details
            ],
        },
        "identifiant_stable": {
            "citations_cassees": protegee.cassees,
            "taux": round(protegee.taux, 4),
        },
    }
