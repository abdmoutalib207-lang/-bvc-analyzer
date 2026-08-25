#!/usr/bin/env python3
"""Contrôle qu'une séance cotée a bien été enregistrée, et alerte sinon.

Le critère de succès du projet est « un run J+1 réussi chaque soir, publié
avant 8h00, trente jours consécutifs sans échec ». Ce critère n'était pas
mesurable : rien ne prévenait quand un run manquait. Il fallait que quelqu'un
regarde.

Ce script est ce quelqu'un. Il tourne après le filet de sécurité de 18h, et
sort en code 1 si la séance du jour n'est pas correctement gravée — ce qui
fait échouer le workflow, et GitHub envoie alors un courriel au propriétaire
du dépôt. Pas de service tiers, pas de secret à gérer : l'alerte passe par le
seul canal déjà en place.

⚠️ Il ne commite rien. Le quota de publication de GitHub Pages est la
ressource rare du projet — un contrôle qui produirait un commit par jour
consommerait ce qu'il est censé protéger.

Un jour sans séance — week-end ou férié à date fixe — n'est pas un échec :
le script sort alors en 0 sans rien dire.
"""

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).parent))

from bvc_config import TICKERS_ACTIFS, est_ferie_fixe   # noqa: E402

# Casablanca est à UTC+1 toute l'année.
TZ_CA = timezone(timedelta(hours=1))

# En deçà, la séance n'a pas été collectée : un jour coté normal grave une
# bougie pour environ soixante-dix titres. Le seuil laisse la marge d'une
# source partiellement défaillante sans laisser passer un run à vide.
MIN_BOUGIES = 50
MIN_PRIX_DU_JOUR = 50


# Heure à partir de laquelle la séance du jour doit être gravée. La clôture
# est à 15h30 et le run qui la fixe part à 15h45, mais GitHub décale ses
# tâches programmées de 30 à 50 minutes — mesuré trois fois le 24/08 : 34, 49
# et 39 minutes. Avant 17h, une séance absente ne prouve donc rien.
HEURE_SEANCE_GRAVEE = 17


def _est_cote(jour):
    return jour.weekday() < 5 and not est_ferie_fixe(jour.strftime("%Y-%m-%d"))


def _seance_de_reference():
    """Dernière séance qui DEVRAIT être enregistrée, ou None s'il n'y en a pas.

    Viser « aujourd'hui » ne marche pas : lancé le matin, le contrôle
    échouerait sur une séance qui n'a pas encore eu lieu. On remonte donc à la
    dernière séance échue — celle du jour si la clôture est passée et gravée,
    sinon le jour coté précédent.
    """
    maintenant = datetime.now(TZ_CA)
    candidat = maintenant
    if not (_est_cote(candidat) and maintenant.hour >= HEURE_SEANCE_GRAVEE):
        candidat = candidat - timedelta(days=1)
        # Remonter jusqu'au précédent jour coté. La borne de dix jours couvre
        # le plus long enchaînement de fériés et de week-end possible.
        for _ in range(10):
            if _est_cote(candidat):
                break
            candidat = candidat - timedelta(days=1)
        else:
            return None, "aucune séance cotée dans les dix derniers jours"
    return candidat.strftime("%Y-%m-%d"), ""


def _controles(jour):
    """Liste de (intitulé, réussi, détail). Aucun effet de bord."""
    resultats = []

    def ajouter(intitule, ok, detail=""):
        resultats.append((intitule, bool(ok), detail))

    # ── data.json ────────────────────────────────────────────────────────
    try:
        data = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    except Exception as e:
        ajouter("data.json lisible", False, str(e))
        return resultats

    lignes = data.get("tickers") or []
    if isinstance(lignes, dict):
        lignes = list(lignes.values())
    titres = {x.get("symbol"): x for x in lignes if x.get("symbol")}
    ajouter("data.json lisible", True, f"{len(titres)} titres")

    horodatage = str(data.get("updated") or "")
    ajouter("horodatage du jour", horodatage[:10] == jour,
            horodatage or "absent")

    asof = Counter((x.get("_meta") or {}).get("prix_asof") for x in titres.values())
    du_jour = asof.get(jour, 0)
    ajouter(f"prix de la séance ({MIN_PRIX_DU_JOUR} minimum)",
            du_jour >= MIN_PRIX_DU_JOUR, f"{du_jour} titres au {jour}")

    sources = Counter((x.get("_meta") or {}).get("source_prix") for x in titres.values())
    replis = sources.get("static", 0) + sources.get("data_json_precedent", 0)
    ajouter("sources de prix réelles", replis <= 5,
            f"{sources.get('idbourse', 0)} idbourse · {sources.get('medias24', 0)} "
            f"medias24 · {replis} replis muets")

    absents = [t for t in TICKERS_ACTIFS if not (titres.get(t, {}).get("price") or 0) > 0]
    ajouter("les 19 titres MASI 1 ont un prix", not absents, absents or "tous présents")

    hors = [t for t, x in titres.items()
            if x.get("v53") is not None and not 0 <= x["v53"] <= 10]
    ajouter("score v5.3 dans [0, 10]", not hors, hors or "conforme")

    # Règle R10 : la BVC plafonne la variation à ±10 % par séance.
    aberrantes = [(t, x.get("chg")) for t, x in titres.items()
                  if abs(x.get("chg") or 0) > 10]
    ajouter("aucune variation au-delà de ±10 %", not aberrantes,
            aberrantes or "conforme")

    sans_meta = [t for t, x in titres.items() if not x.get("_meta")]
    ajouter("chaque titre porte son bloc _meta", not sans_meta,
            sans_meta or "tous")

    masi = data.get("masi") or {}
    ajouter("MASI daté de la séance",
            str(masi.get("asof") or "")[:10] == jour and not masi.get("stale"),
            f"{masi.get('value')} au {masi.get('asof')} · périmé={masi.get('stale')}")

    # ── chandelles ───────────────────────────────────────────────────────
    dossier = RACINE / "pipeline" / "candles"
    n = 0
    for f in dossier.glob("*.json"):
        try:
            serie = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(serie, list) and serie and serie[-1].get("d") == jour:
            n += 1
    ajouter(f"bougies de la séance ({MIN_BOUGIES} minimum)",
            n >= MIN_BOUGIES, f"{n} titres")

    return resultats


def main():
    jour, raison = _seance_de_reference()
    if jour is None:
        print(f"Aucun contrôle : {raison}.")
        return 0

    resultats = _controles(jour)
    echecs = [r for r in resultats if not r[1]]

    largeur = max(len(i) for i, _, _ in resultats)
    print(f"Contrôle de la séance du {jour}\n")
    for intitule, ok, detail in resultats:
        print(f"  {'OK   ' if ok else 'ÉCHEC'}  {intitule.ljust(largeur)}  {detail}")

    # Résumé dans l'interface GitHub Actions, pour n'avoir pas à ouvrir le log.
    import os
    resume = os.environ.get("GITHUB_STEP_SUMMARY")
    if resume:
        with open(resume, "a", encoding="utf-8") as fh:
            fh.write(f"## Séance du {jour}\n\n")
            fh.write("| | Contrôle | Détail |\n|---|---|---|\n")
            for intitule, ok, detail in resultats:
                fh.write(f"| {'✅' if ok else '❌'} | {intitule} | {detail} |\n")

    if echecs:
        print(f"\n{len(echecs)} contrôle(s) en échec — la séance du {jour} "
              f"n'est pas correctement enregistrée.")
        return 1
    print(f"\nSéance du {jour} enregistrée et conforme.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
