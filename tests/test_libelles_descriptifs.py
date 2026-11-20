"""Libellés descriptifs : le produit décrit, il ne recommande pas.

Deux contrôles :
  1. aucun mot interprétatif (surachat, haussier, pullback, cassure, rebond,
     achat, signal…) dans un champ `libelle` des fichiers publiés ;
  2. les libellés des générateurs (`pipeline/frequences.py`,
     `pipeline/figures_publiees.py`) sont ceux des fichiers publiés ;

Que les chiffres (fréquences, effectifs, périodes) n'ont pas bougé avec le
changement de libellés est une preuve ponctuelle, faite dans la PR (empreinte
sha256 du contenu hors libellés, identique avant et après). Elle n'est pas
figée ici : `figures_publiees.json` est régénéré à chaque passage du moteur, et
une empreinte figée casserait la suite au premier passage légitime.

Les clés techniques (`pullback_on`, `gap_haussier`…) restent des identifiants :
seuls les libellés affichés sont contrôlés.
"""
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import figures_publiees as fp  # noqa: E402
import frequences as fq  # noqa: E402

FREQ = RACINE / "datasets" / "frequences_publiees.json"
FIG = RACINE / "datasets" / "figures_publiees.json"

MOTS = re.compile(
    r"surachat|surachet|survente|survend|haussi|baissi|pullback|rebond|cassure|cass[ée]e?\b|"
    r"\bachat|\bvente|signal|\bbull|\bbear|support|r[ée]sistance|entr[ée]e|sortie",
    re.I)

def _charger(p):
    return json.loads(p.read_text(encoding="utf-8"))


def _libelles(o, chemin=""):
    """Tous les champs `libelle` d'un document, avec leur chemin."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "libelle" and isinstance(v, str):
                yield chemin, v
            else:
                yield from _libelles(v, f"{chemin}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _libelles(v, f"{chemin}[{i}]")


# ── 1. aucun mot interprétatif ──────────────────────────────────────────

def test_libelles_publies_sans_mot_interpretatif():
    fautes = []
    for p in (FREQ, FIG):
        ls = list(_libelles(_charger(p)))
        assert ls, f"aucun libellé trouvé dans {p.name} : le test ne contrôlerait rien"
        fautes += [(p.name, ch, lib) for ch, lib in ls if MOTS.search(lib)]
    uniques = sorted({(f, lib) for f, _, lib in fautes})
    assert not uniques, f"libellés interprétatifs publiés : {uniques}"


def test_libelles_des_generateurs_sans_mot_interpretatif():
    gen = [lib for (_, _, lib, _) in fq.DEFS.values()] + list(fp.LIBELLES.values())
    assert [x for x in gen if MOTS.search(x)] == []


# ── 2. libellés générés = libellés publiés ──────────────────────────────

def test_libelles_frequences_generes_egaux_publies():
    pub = _charger(FREQ)["frequences"]
    assert set(pub) == set(fq.DEFS)
    for cle, (_, _, lib, _) in fq.DEFS.items():
        assert pub[cle]["libelle"] == lib, cle


def test_libelles_figures_generes_egaux_publies():
    doc = _charger(FIG)
    vus = {}
    for t in doc["titres"].values():
        for g in (t.get("figures") or []) + (t.get("lignes") or []) + (t.get("gaps") or []):
            vus.setdefault(g["type"], set()).add(g["libelle"])
    assert vus, "aucune figure publiée : le test ne contrôlerait rien"
    for typ, libs in vus.items():
        assert libs == {fp.LIBELLES[typ]}, typ
