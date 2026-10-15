"""Resumes du bordereau : generation puis verification.

Generes par un modele qui a la piece sous les yeux, ils sont une surface de
controle a part entiere, passee au meme `checks.py` que l'acte.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .checks import controler, extraire_valeurs
from .chemins import BORDEREAU
from .dossier import Piece, charger_bordereau
from .llm import MODELE_REDACTION, generer

GABARIT = """Voici une pièce d'un dossier de contentieux commercial français.

# La pièce

{texte}

# Ta mission

Rédige le résumé qui figurera en regard de cette pièce au bordereau.

- **Deux à trois lignes**, pas davantage.
- En français, style de bordereau : nominal, sans « ce document » ni « cette pièce ».
- **Charge-le de chiffres précis** tirés de la pièce : montants avec la mention HT \
ou TTC, dates, numéros de référence, articles du contrat, quantités, lieux.
- N'avance aucun fait qui ne figure pas dans la pièce ci-dessus.

Ne renvoie que le résumé, sans titre ni commentaire.
"""


@dataclass(frozen=True)
class ResumeControle:
    """Un resume genere, confronte a la piece dont il est tire."""

    doc_id: str
    cote: int
    resume: str
    valeurs: int
    confirmees: int
    contredites: tuple[str, ...]
    indecidables: int

    @property
    def fiable(self) -> bool:
        return not self.contredites


def generer_resume(piece: Piece) -> str:
    """Un resume par piece, mis en cache comme tout appel au modele."""
    return generer(
        GABARIT.format(texte=piece.texte),
        modele=MODELE_REDACTION,
        etiquette=f"resume_{piece.doc_id}",
        temperature=0.0,
    ).strip()


def generer_tous(*, ecrire: bool = True, trace: bool = False) -> dict[str, str]:
    """Genere les dix resumes et les ecrit dans le bordereau."""
    resumes = {}
    for piece in charger_bordereau():
        resumes[piece.doc_id] = generer_resume(piece)
        if trace:
            print(f"  n° {piece.cote:<2} {piece.doc_id} : "
                  f"{len(resumes[piece.doc_id].split())} mots", flush=True)

    if ecrire:
        brut = json.loads(BORDEREAU.read_text(encoding="utf-8"))
        for entree in brut["pieces"]:
            entree["resume"] = resumes[entree["doc_id"]]
        BORDEREAU.write_text(
            json.dumps(brut, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        charger_bordereau.cache_clear()
    return resumes


def controler_resume(piece: Piece, resume: str | None = None) -> ResumeControle:
    """Confronte chaque valeur du resume a la piece dont il est tire."""
    resume = resume if resume is not None else piece.resume
    valeurs = extraire_valeurs(resume)

    confirmees, indecidables, contredites = 0, 0, []
    for v in valeurs:
        verdict = controler(v, piece.texte)
        if verdict.verdict == "confirme":
            confirmees += 1
        elif verdict.verdict == "contredit":
            contredites.append(f"{v.brut} — {verdict.motif}")
        else:
            indecidables += 1

    return ResumeControle(
        doc_id=piece.doc_id,
        cote=piece.cote,
        resume=resume,
        valeurs=len(valeurs),
        confirmees=confirmees,
        contredites=tuple(contredites),
        indecidables=indecidables,
    )


def controler_tous() -> list[ResumeControle]:
    return [controler_resume(p) for p in charger_bordereau() if p.resume]
