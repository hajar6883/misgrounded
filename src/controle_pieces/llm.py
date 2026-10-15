"""Client Gemini : un appel, un cache disque, une reprise sur erreur transitoire.

Le cache est commite avec le prompt a cote de la reponse : le depot se rejoue
entierement hors ligne, et un relecteur voit ce qui a ete demande.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

from .chemins import CACHE, RACINE

load_dotenv(RACINE / ".env")

# Erreurs de transport. Le nom de la classe suffit : httpx n'est qu'une
# dependance transitive du SDK.
ERREURS_TRANSITOIRES = frozenset({
    "ConnectError", "ConnectTimeout", "ReadTimeout", "ReadError", "WriteError",
    "PoolTimeout", "RemoteProtocolError", "SSLError", "SSLEOFError",
})

TENTATIVES_MAX = 8
ATTENTE_INITIALE = 4.0  # secondes, doublee a chaque essai
ATTENTE_MAX = 60.0  # au-dela, doubler ne sert plus qu'a dormir

# Deux modeles distincts : un juge qui evalue sa propre production valide ses
# erreurs. Aucun modele "pro" n'etant accessible, l'ecart reste mince (README).
MODELE_REDACTION = os.environ.get("GEMINI_MODELE_REDACTION", "gemini-3.1-flash-lite")
MODELE_JUGE = os.environ.get("GEMINI_MODELE_JUGE", "gemini-3.5-flash-lite")


def hors_ligne() -> bool:
    return os.environ.get("CONTROLE_PIECES_OFFLINE", "0") == "1"


class CacheManquant(RuntimeError):
    """Mode hors ligne, et la reponse n'est pas dans le cache."""


@dataclass(frozen=True)
class Appel:
    """Tout ce qui determine une reponse. Deux appels identiques -> meme cle."""

    modele: str
    prompt: str
    temperature: float
    schema_json: str | None

    def empreinte(self) -> str:
        brut = json.dumps(
            {
                "modele": self.modele,
                "prompt": self.prompt,
                "temperature": self.temperature,
                "schema": self.schema_json,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(brut.encode("utf-8")).hexdigest()[:16]


def _fichier_cache(etiquette: str, empreinte: str):
    CACHE.mkdir(parents=True, exist_ok=True)
    prefixe = etiquette or "appel"
    return CACHE / f"{prefixe}__{empreinte}.json"


def _appeler_gemini(appel: Appel, schema: Any | None) -> str:
    """Le seul endroit du projet qui parle a un fournisseur."""
    from google import genai
    from google.genai import types

    cle = os.environ.get("GEMINI_API_KEY")
    if not cle:
        raise RuntimeError(
            "GEMINI_API_KEY absente. Copier .env.example en .env et la renseigner, "
            "ou lancer en mode hors ligne (CONTROLE_PIECES_OFFLINE=1)."
        )

    config: dict[str, Any] = {"temperature": appel.temperature}
    if schema is not None:
        config["response_mime_type"] = "application/json"
        config["response_schema"] = schema

    # On desactive l'appel de fonction automatique : on ne fournit aucun outil,
    # et le SDK emet sinon un avertissement a chaque appel.
    config["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
        disable=True
    )

    client = genai.Client(api_key=cle)

    # Saturation (503) et limitation de debit (429) sont la norme : sans
    # reprise, un run de plusieurs dizaines d'appels echoue presque a coup sur.
    derniere: Exception | None = None
    for tentative in range(TENTATIVES_MAX):
        try:
            reponse = client.models.generate_content(
                model=appel.modele,
                contents=appel.prompt,
                config=types.GenerateContentConfig(**config),
            )
            texte = reponse.text
            if not texte:
                raise RuntimeError(f"reponse vide du modele {appel.modele}")
            return texte
        except Exception as erreur:  # noqa: BLE001 - on filtre juste apres
            code = getattr(erreur, "code", None)
            transitoire = (
                code in (429, 503)
                or type(erreur).__name__ in ERREURS_TRANSITOIRES
            )
            if not transitoire or tentative == TENTATIVES_MAX - 1:
                raise
            derniere = erreur
            attente = min(ATTENTE_INITIALE * (2**tentative), ATTENTE_MAX)
            motif = f"code {code}" if code else type(erreur).__name__
            print(
                f"  [{appel.modele}] {motif}, nouvelle tentative "
                f"dans {attente:.0f} s "
                f"({tentative + 1}/{TENTATIVES_MAX - 1})",
                flush=True,
            )
            time.sleep(attente)

    raise RuntimeError(f"echec apres {TENTATIVES_MAX} tentatives") from derniere


def generer(
    prompt: str,
    *,
    modele: str | None = None,
    etiquette: str = "",
    temperature: float = 0.0,
    schema: Any | None = None,
) -> str:
    """Renvoie la reponse du modele, depuis le cache si elle y est deja.

    `etiquette` sert uniquement a nommer le fichier de cache lisiblement.
    `schema` active la sortie structuree : la reponse est alors du JSON valide.
    """
    appel = Appel(
        modele=modele or MODELE_REDACTION,
        prompt=prompt,
        temperature=temperature,
        schema_json=repr(schema) if schema is not None else None,
    )
    chemin = _fichier_cache(etiquette, appel.empreinte())

    if chemin.exists():
        return json.loads(chemin.read_text("utf-8"))["reponse"]

    if hors_ligne():
        raise CacheManquant(
            f"mode hors ligne et cache vide pour {chemin.name}.\n"
            "Relancer avec une cle API, ou verifier que cache/ est bien present."
        )

    reponse = _appeler_gemini(appel, schema)
    chemin.write_text(
        json.dumps(
            {
                "modele": appel.modele,
                "temperature": appel.temperature,
                "empreinte": appel.empreinte(),
                "horodatage": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "prompt": appel.prompt,
                "reponse": reponse,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return reponse


def generer_json(prompt: str, schema: Any, **kwargs: Any) -> Any:
    """Comme generer(), mais renvoie l'objet Python deja decode."""
    return json.loads(generer(prompt, schema=schema, **kwargs))
