"""Emplacements du projet, resolus une fois pour toutes."""

from __future__ import annotations

from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent

DOSSIER = RACINE / "dossier"
PIECES = DOSSIER / "pieces"
BORDEREAU = DOSSIER / "bordereau.json"
VERITE_TERRAIN = DOSSIER / "verite_terrain.json"

PROJETS = RACINE / "projets"
ACTE_LLM = PROJETS / "conclusions_llm.md"
ACTE_PIEGE = PROJETS / "conclusions_piegees.md"
ERREURS_PLANTEES = PROJETS / "erreurs_plantees.json"
ACTE_COTES = PROJETS / "conclusions_mauvaises_cotes.md"
COTES_DEPLACEES = PROJETS / "cotes_deplacees.json"

CACHE = RACINE / "cache"
RESULTATS = RACINE / "results"
