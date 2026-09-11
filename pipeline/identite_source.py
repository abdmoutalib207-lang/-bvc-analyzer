#!/usr/bin/env python3
"""L'identité lue DANS les données importées, ligne par ligne.

⚠️ POURQUOI CE FICHIER EXISTE
─────────────────────────────
Le garde-fou d'identité était branché, éprouvé, et ne servait à rien dans le
parcours normal : `main()` appelait `run()` **sans transmettre aucune
identité**, parce que les deux sources réellement utilisées n'en portent
aucune —

  · le fichier XLSX local est nommé d'après NOTRE ticker et ne contient pas
    de colonne d'identité : le nom qu'on lui prête vient de nous ;
  · la bibliothèque d'extension est interrogée PAR NOM et rend un tableau de
    cours sans rien qui identifie l'instrument : la réponse ne peut pas
    contredire la question.

Un contrôle alimenté par la partie contrôlée ne contrôle rien. C'est
exactement la faute de juin : `MANUAL_MAP` disait « MSA = Mutandis », la
source répondait les cours de Mutandis, et tout concordait.

CE QUE CE MODULE FAIT
─────────────────────
Il lit l'identité **dans la même ligne que les cours**, sur la seule source
qui la transporte : l'export de l'opérateur. Ses colonnes `Ticker` et
`Instrument` voyagent avec `Dernier Cours`. Si la ligne ment sur l'identité,
elle ment sur la même ligne que le prix — et cela, nous pouvons le voir.

    Séance;Ticker;Instrument;Ouverture;Dernier Cours;…
    10/09/2026;ADH;DOUJA PROM ADDOHA;35.44;35.75;…

CE QU'IL NE FAIT PAS
────────────────────
⚠️ Il n'établit pas que l'opérateur a raison. Il établit que **le fournisseur
a nommé l'instrument qu'il servait**. C'est tout — mais c'est précisément ce
qui manquait.

⚠️ Il ne couvre que les titres pour lesquels un export existe. Pour les
autres, l'identité reste **inconnue**, et le collecteur refuse d'écrire. Un
refus large est la conséquence assumée : nous ne savons pas nommer ce que nous
importons.

    python pipeline/identite_source.py
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SOURCES = RACINE / "sources"

COLONNE_TICKER = "Ticker"
COLONNE_INSTRUMENT = "Instrument"
COLONNE_PRIX = "Dernier Cours"

# ⚠️ Le tiret marque une valeur NON RENSEIGNÉE, jamais un cours. Une ligne
# sans cours ne témoigne de rien sur l'identité des cours : elle est écartée
# du décompte, dans un sens comme dans l'autre. Registre partagé avec
# l'importateur pour que les deux lectures ne divergent pas.
try:
    from importer_export import ABSENCES
except ImportError:                                   # exécution hors paquet
    ABSENCES = {"", "-", "--", "n/a", "N/A", "ND"}


def identite_de_l_export(chemin: Path) -> dict:
    """Quelle identité ce fichier porte-t-il, et la porte-t-il sur TOUTES ses
    lignes de cours ?

    Le verdict n'est pas « le nom trouvé » mais « le nom trouvé, constant, sur
    les lignes qui portent effectivement un prix ». Un export qui changerait
    d'instrument en cours de route serait justement le défaut qu'on cherche.
    """
    paires: Counter = Counter()
    sans_identite = 0
    lignes = 0

    with chemin.open(encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        colonnes = lecteur.fieldnames or []
        manquantes = [c for c in (COLONNE_TICKER, COLONNE_INSTRUMENT, COLONNE_PRIX)
                      if c not in colonnes]
        if manquantes:
            return {
                "identite_portee": False,
                "motif": f"colonnes d'identité absentes : {manquantes}",
                "colonnes": colonnes,
                "fichier": chemin.name,
            }
        for r in lecteur:
            # ⚠️ Seules les lignes qui portent un cours comptent. Une ligne
            # sans prix ne prouve rien sur l'identité des prix.
            if (r.get(COLONNE_PRIX) or "").strip() in ABSENCES:
                continue
            lignes += 1
            t = (r.get(COLONNE_TICKER) or "").strip()
            i = (r.get(COLONNE_INSTRUMENT) or "").strip()
            if not t and not i:
                sans_identite += 1
                continue
            paires[(t, i)] += 1

    if not lignes:
        return {"identite_portee": False, "motif": "aucune ligne de cours",
                "fichier": chemin.name}
    if sans_identite:
        return {"identite_portee": False, "fichier": chemin.name,
                "motif": f"{sans_identite} ligne(s) de cours sans identité — "
                         f"l'identité ne couvre pas tous les prix"}
    if len(paires) != 1:
        # ⚠️ Ce cas EST la contamination, vue depuis la source.
        return {"identite_portee": False, "fichier": chemin.name,
                "motif": "le fichier mêle plusieurs instruments",
                "paires_vues": {f"{t} / {i}": n for (t, i), n in paires.items()}}

    (ticker, instrument), n = next(iter(paires.items()))
    return {
        "identite_portee": True,
        "fichier": chemin.name,
        "ticker_fournisseur": ticker,
        "instrument": instrument,
        "lignes_de_cours": n,
        "_lecture": "identité constante sur TOUTES les lignes portant un "
                    "cours. Elle voyage avec le prix, dans la même ligne.",
    }


def identites_disponibles(dossier: Path | None = None) -> dict:
    """{notre ticker: nom rendu par le fournisseur} — et rien d'inventé.

    La clé est le nom du sous-dossier (`sources/ADH/`), c'est-à-dire NOTRE
    ticker ; la valeur vient du fichier. Les deux ne sont jamais confondus :
    c'est leur confrontation qui fait le contrôle, dans `autoriser_ecriture`.
    """
    dossier = dossier or SOURCES
    rendu, ecartes = {}, {}
    if not dossier.exists():
        return {"identites": {}, "ecartes": {},
                "_motif": f"{dossier} n'existe pas"}

    for sous in sorted(p for p in dossier.iterdir() if p.is_dir()):
        fichiers = sorted(sous.glob("*.csv"))
        if not fichiers:
            ecartes[sous.name] = "aucun export CSV"
            continue
        # Le plus récent par nom de fichier ; les exports sont horodatés.
        lu = identite_de_l_export(fichiers[-1])
        if not lu["identite_portee"]:
            ecartes[sous.name] = lu["motif"]
            continue
        rendu[sous.name] = {
            "instrument": lu["instrument"],
            "ticker_fournisseur": lu["ticker_fournisseur"],
            "fichier": lu["fichier"],
            "lignes_de_cours": lu["lignes_de_cours"],
        }
    return {"identites": rendu, "ecartes": ecartes}


def pour_le_collecteur(dossier: Path | None = None) -> dict:
    """La forme attendue par `run(identites_recues=…)` : {ticker: nom reçu}.

    ⚠️ On transmet le **nom d'instrument**, pas le code. Le code est le plus
    facile à faire concorder — et c'est justement ce qui rendait le contrôle
    de juin inopérant : il comparait notre ticker à lui-même. Le nom est ce
    que le fournisseur affirme servir.
    """
    d = identites_disponibles(dossier)
    return {t: v["instrument"] for t, v in d["identites"].items()}


def main() -> None:
    d = identites_disponibles()
    print(json.dumps({
        "_quoi": "identité lue dans les données importées, ligne par ligne",
        "_ce_qui_n_est_pas_etabli": (
            "⚠️ Que le fournisseur nomme l'instrument qu'il sert ne prouve pas "
            "que ses cours soient exacts. Cela prouve seulement qu'il ne peut "
            "plus nous servir une autre société en silence."),
        "titres_avec_identite": len(d["identites"]),
        "titres_ecartes": d["ecartes"],
        **d,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
