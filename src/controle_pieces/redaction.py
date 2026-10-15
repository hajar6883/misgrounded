"""Generation de l'acte a verifier.

Le prompt exige l'exactitude et la citation systematique : les erreurs
observees sont donc de vraies defaillances, pas l'effet d'une consigne molle.
"""

from __future__ import annotations

from .chemins import ACTE_LLM
from .dossier import bordereau_lisible, corpus_complet
from .llm import MODELE_REDACTION, generer

# Gabarit en francais accentue a dessein : le modele calque le registre de la
# consigne. Un prompt sans accents produit un acte sans accents.
GABARIT = """Tu es avocat au barreau de Lyon. Tu rédiges des conclusions en défense et \
reconventionnelles pour la société NOVERIA DISTRIBUTION (défenderesse), \
assignée en paiement par la société ALTIMEO CONSEIL (demanderesse) devant le \
Tribunal de commerce de Lyon.

# Bordereau des pièces communiquées

{bordereau}

# Pièces du dossier

{corpus}

# Ta mission

Rédige les conclusions en français juridique soutenu, au format Markdown.

Structure attendue :

1. Un en-tête (juridiction, parties, avocat).
2. `PLAISE AU TRIBUNAL`
3. `I. RAPPEL DES FAITS` : la chronologie du litige.
4. `II. DISCUSSION`, en trois sous-parties :
   - A. La recette du lot 2 n'est pas acquise
   - B. Les pénalités de retard sont dues
   - C. Aucun avenant n'est intervenu
5. `PAR CES MOTIFS` : les demandes chiffrées.

# Règles impératives

- **Cite systématiquement tes sources.** Chaque affirmation de fait doit être \
suivie de la cote de la pièce qui l'établit, au format exact `(pièce n° X)` \
où X est le numéro du bordereau. Exemple : `Le contrat a été signé le 2 avril 2024 \
(pièce n° 1).`
- **N'invente aucun fait.** Chaque date, chaque montant, chaque nom doit \
provenir des pièces ci-dessus.
- Sois précis sur les chiffres : montants en euros avec la mention HT ou TTC, \
dates complètes.
- Respecte l'orthographe et les accents du français.
- Longueur : entre 1 500 et 2 500 mots.
- Ne commente pas ta production : renvoie uniquement les conclusions.
"""


def construire_prompt() -> str:
    return GABARIT.format(bordereau=bordereau_lisible(), corpus=corpus_complet())


def generer_acte(*, ecrire: bool = True) -> str:
    """Produit l'acte a partir du dossier. Passe par le cache si deja genere."""
    acte = generer(
        construire_prompt(),
        modele=MODELE_REDACTION,
        etiquette="acte",
        temperature=0.0,
    ).strip()

    if ecrire:
        ACTE_LLM.parent.mkdir(parents=True, exist_ok=True)
        ACTE_LLM.write_text(acte + "\n", encoding="utf-8")
    return acte
