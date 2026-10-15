"""Juge LLM en double passe.

Meme prompt, meme affirmation, deux contextes : A = tout le dossier, B = la
seule piece citee. Passer A et echouer B, c'est etre misgrounded -- ce qu'une
metrique de fidelite classique valide.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from .dossier import corpus_complet, par_cote
from .extract import Affirmation
from .llm import MODELE_JUGE, generer

VERDICTS = ("etaye", "contredit", "absent")

PASSE_DOSSIER = "A"  # contexte : tout le dossier
PASSE_PIECE = "B"  # contexte : la seule piece citee

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "citation_justificative": {"type": "string"},
        "explication": {"type": "string"},
    },
    "required": ["verdict", "citation_justificative", "explication"],
}

# Strictement identique dans les deux passes. Seul {contexte} change.
GABARIT = """Tu vérifies une affirmation tirée de conclusions d'avocat.

On te communique ci-dessous un contexte documentaire. Tu ne dois te prononcer \
que sur ce contexte : n'invoque aucune connaissance extérieure, ne suppose rien \
de ce que contiendraient d'autres documents.

# Contexte

{contexte}

# Affirmation à vérifier

{affirmation}

# Ta réponse

Rends un verdict parmi exactement trois valeurs :

- `etaye` : le contexte établit l'affirmation.
- `contredit` : le contexte dit quelque chose d'incompatible avec l'affirmation.
- `absent` : le contexte ne traite pas de ce point, ni dans un sens ni dans l'autre.

Renseigne `citation_justificative` avec un extrait **copié mot pour mot** du \
contexte ci-dessus, qui fonde ton verdict. N'y change rien, pas même la \
ponctuation. Si le verdict est `absent`, laisse ce champ vide.

Renseigne `explication` avec une phrase courte, en français.

Si une valeur avancée est indiquée, ne te prononce que sur elle : le reste du \
texte sert seulement à la situer, une erreur ailleurs dans la phrase ne compte pas.

Sois strict : une affirmation partiellement exacte n'est pas `etaye`. Une date \
qui figure dans le contexte mais s'y rapporte à un autre événement ne l'étaye \
pas davantage.
"""


@dataclass(frozen=True)
class Verdict:
    claim_id: str
    cote_citee: int
    passe: str
    verdict: str
    citation_justificative: str
    explication: str
    citation_verifiee: bool

    @property
    def etaye(self) -> bool:
        return self.verdict == "etaye"


@dataclass(frozen=True)
class Comparaison:
    """Le resultat qui compte : ce que A dit, ce que B dit, et l'ecart."""

    claim_id: str
    cote_citee: int
    texte: str
    valeur_brute: str | None
    a: Verdict
    b: Verdict

    @property
    def classement(self) -> str:
        if self.a.etaye and self.b.etaye:
            return "correctement_cite"
        if self.a.etaye and not self.b.etaye:
            return "misgrounded"  # vrai ailleurs, faux a la cote citee
        if not self.a.etaye and not self.b.etaye:
            return "non_etaye"  # introuvable dans tout le dossier
        return "incoherence_du_juge"  # etaye en B mais pas en A : impossible


def _comparable(texte: str) -> str:
    texte = unicodedata.normalize("NFC", texte).replace("*", "")
    texte = texte.replace("’", "'").replace("«", '"').replace("»", '"')
    return re.sub(r"\s+", " ", texte).strip().lower()


def citation_presente(citation: str, contexte: str) -> bool:
    """La citation du juge figure-t-elle vraiment dans le contexte fourni ?"""
    citation = _comparable(citation)
    if len(citation) < 8:  # trop court pour etre discriminant
        return False
    return citation in _comparable(contexte)


def _enonce(affirmation: Affirmation) -> str:
    lignes = [f"Texte : « {affirmation.texte} »"]
    if affirmation.porte_une_valeur:
        valeur = affirmation.valeur_brute
        if affirmation.qualificatif:
            valeur = f"{valeur} (qualifié {affirmation.qualificatif})"
        lignes.append(f"Valeur avancée ({affirmation.type}) : {valeur}")
    return "\n".join(lignes)


def contexte_de(affirmation: Affirmation, passe: str) -> str | None:
    """Le seul point ou les deux passes different."""
    if passe == PASSE_DOSSIER:
        return corpus_complet()
    piece = par_cote().get(affirmation.cote_citee)
    return piece.texte if piece else None


def juger(affirmation: Affirmation, passe: str) -> Verdict:
    contexte = contexte_de(affirmation, passe)
    if contexte is None:
        return Verdict(
            claim_id=affirmation.claim_id,
            cote_citee=affirmation.cote_citee,
            passe=passe,
            verdict="absent",
            citation_justificative="",
            explication="la cote citée ne figure pas au bordereau",
            citation_verifiee=False,
        )

    reponse = generer(
        GABARIT.format(contexte=contexte, affirmation=_enonce(affirmation)),
        modele=MODELE_JUGE,
        etiquette=f"juge{passe}_{affirmation.claim_id}",
        temperature=0.0,
        schema=SCHEMA,
    )
    brut = json.loads(reponse)

    verdict = brut.get("verdict", "absent")
    if verdict not in VERDICTS:
        verdict = "absent"
    citation = (brut.get("citation_justificative") or "").strip()

    return Verdict(
        claim_id=affirmation.claim_id,
        cote_citee=affirmation.cote_citee,
        passe=passe,
        verdict=verdict,
        citation_justificative=citation,
        explication=(brut.get("explication") or "").strip(),
        citation_verifiee=citation_presente(citation, contexte),
    )


def double_passe(
    affirmations: list[Affirmation], *, trace: bool = False
) -> list[Comparaison]:
    """Les deux passes sur chaque affirmation, et leur comparaison."""
    resultats = []
    for i, aff in enumerate(affirmations, start=1):
        a = juger(aff, PASSE_DOSSIER)
        b = juger(aff, PASSE_PIECE)
        c = Comparaison(
            claim_id=aff.claim_id,
            cote_citee=aff.cote_citee,
            texte=aff.texte,
            valeur_brute=aff.valeur_brute,
            a=a,
            b=b,
        )
        if trace:
            marque = "  <<< MISGROUNDED" if c.classement == "misgrounded" else ""
            print(
                f"  {i:3}/{len(affirmations)}  {c.claim_id}  cote {c.cote_citee:<2} "
                f"A={a.verdict:<9} B={b.verdict:<9} {c.classement}{marque}",
                flush=True,
            )
        resultats.append(c)
    return resultats


def synthese(comparaisons: list[Comparaison]) -> dict:
    total = len(comparaisons)
    classements = Counter(c.classement for c in comparaisons)
    citations = [v for c in comparaisons for v in (c.a, c.b) if v.citation_justificative]
    return {
        "affirmations": total,
        "classements": dict(classements),
        "taux_misgrounded": round(classements["misgrounded"] / total, 4) if total else 0.0,
        "taux_non_etaye": round(classements["non_etaye"] / total, 4) if total else 0.0,
        "etaye_passe_A": sum(1 for c in comparaisons if c.a.etaye),
        "etaye_passe_B": sum(1 for c in comparaisons if c.b.etaye),
        "citations_du_juge_verifiees": (
            round(sum(1 for v in citations if v.citation_verifiee) / len(citations), 4)
            if citations
            else None
        ),
    }
