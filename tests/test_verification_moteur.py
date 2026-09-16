#!/usr/bin/env python3
"""Le contrôle d'avant-fusion : le moteur entier, hors réseau, sur 80 titres.

⚠️ D'OÙ VIENT CETTE MÉTHODE, ET POURQUOI JE L'ADOPTE
────────────────────────────────────────────────────
Elle est reprise de `pipeline/verifier_candidat_msa.py`, écrit pour le lot MSA.
Ma méthode à moi s'arrêtait plus tôt : je recalculais le cache du titre
corrigé, je lançais la suite, je rejouais le moteur EN LIGNE. Trois faiblesses
que la journée du 15/09 a rendues concrètes :

  · la comparaison portait sur le CACHE, pas sur ce que le moteur REND ;
  · rien ne prouvait que les 79 autres titres étaient intacts À LA SORTIE ;
  · le réseau rendait le contrôle non reproductible — deux exécutions à cinq
    minutes d'écart ne donnent pas le même fichier, et j'ai passé la journée à
    démêler « est-ce mon correctif ou le marché ? ».

`pipeline/verifier_correction.py` généralise la méthode à n'importe quel titre
portant un lot dans `datasets/corrections_acceptees/`.

⚠️ CE QUE CE CONTRÔLE N'ÉTABLIT PAS
Les cotations sont reconstituées depuis le `data.json` publié, pas rejouées
depuis les réponses brutes des fournisseurs. C'est un contrôle d'INTÉGRATION
hors réseau — ni une preuve que la collecte du jour était juste, ni qu'un run
GitHub Actions se comportera à l'identique.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

CORRECTIONS = RACINE / "datasets" / "corrections_acceptees"


def _lots():
    return sorted(f.stem for f in CORRECTIONS.glob("*.json"))


def test_chaque_lot_permet_de_reconstruire_l_etat_d_avant():
    """⚠️ LE POINT QUI REND LA COMPARAISON HONNÊTE.

    Le contrôle compare la série corrigée à la série SANS corrections, et cette
    dernière est reconstruite en réappliquant les `remplace` du lot — pas
    relue dans un souvenir. Si un lot décrivait mal l'état antérieur, la
    reconstruction ne retomberait pas dessus et le contrôle le dirait.
    """
    from verifier_correction import serie_sans_corrections
    for t in _lots():
        f = RACINE / "pipeline" / "candles" / f"{t}.json"
        if not f.exists():
            continue
        serie = json.loads(f.read_text(encoding="utf-8"))
        avant, doc = serie_sans_corrections(t, serie)
        assert len(avant) == len(serie)
        dates = {l["d"] for l in doc["lignes"]}
        bouges = [a["d"] for a, b in zip(avant, serie) if a != b]
        assert set(bouges) == dates, (
            f"{t} : la reconstruction ne retombe pas sur les séances du lot")


def test_le_controle_refuse_une_serie_qui_ne_porte_pas_la_correction(tmp_path):
    """⚠️ Un contrôle qui accepterait une série non corrigée mesurerait le
    vide. Il doit s'arrêter, pas conclure."""
    from verifier_correction import serie_sans_corrections
    t = _lots()[0]
    serie = json.loads((RACINE / "pipeline" / "candles" / f"{t}.json")
                       .read_text(encoding="utf-8"))
    doc = json.loads((CORRECTIONS / f"{t}.json").read_text(encoding="utf-8"))
    d = doc["lignes"][0]["d"]
    sale = [({**b, "c": 1.0} if b["d"] == d else b) for b in serie]
    with pytest.raises(SystemExit, match="ne porte pas la correction"):
        serie_sans_corrections(t, sale)


def test_le_reseau_est_interdit_et_son_absence_verifiee():
    """⚠️ Interdire ne suffit pas : il faut CONSTATER qu'aucun appel n'a eu
    lieu. Un repli qui rattraperait un appel en silence ferait passer le
    contrôle pour bon alors qu'il aurait mesuré autre chose.

    Lu sur l'ARBRE SYNTAXIQUE — une mention en commentaire ne compte pas.
    """
    import ast
    src = (RACINE / "pipeline" / "verifier_correction.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    attrs = {getattr(n.func, "attr", "") for n in ast.walk(arbre)
             if isinstance(n, ast.Call)}
    assert "assert_not_called" in attrs, (
        "le contrôle n'exige pas l'absence effective d'appel réseau")
    assert src.count("assert_not_called") >= 2, (
        "les deux voies — requests et socket — doivent être constatées")


def test_le_bac_est_jetable_et_rien_n_y_est_ecrit():
    """Le dry-run ne doit rien écrire ; le contrôle compare les empreintes
    avant et après, et refuse si elles diffèrent."""
    src = (RACINE / "pipeline" / "verifier_correction.py").read_text(encoding="utf-8")
    assert "TemporaryDirectory" in src
    assert "le dry-run a écrit dans le bac" in src


def test_l_instant_doit_porter_son_fuseau():
    """⚠️ Deux runs comparés doivent partager le MÊME instant. Un horodatage
    sans fuseau se lirait différemment selon la machine."""
    from verifier_correction import executer
    with pytest.raises(ValueError, match="fuseau"):
        executer("SOT", [], {}, "2026-09-15T21:00:00")


# ── Le lot HPS ─────────────────────────────────────────────────────────────

def test_hps_le_lot_couvre_les_deux_causes():
    """89 séances : 83 à la base d'avant le fractionnement, 6 rediffusées."""
    doc = json.loads((CORRECTIONS / "HPS.json").read_text(encoding="utf-8"))
    assert doc["ticker"] == "HPS" and doc["seances"] == 89
    serie = {b["d"]: b for b in json.loads(
        (RACINE / "pipeline" / "candles" / "HPS.json").read_text(encoding="utf-8"))}
    for l in doc["lignes"]:
        assert {k: serie[l["d"]][k] for k in ("o", "h", "l", "c", "v")} == l["corrige"]
    # ⚠️ `remplace` de ces six lignes porte l'état INTERMÉDIAIRE — le nombre de
    # titres que j'avais écrit avant de constater qu'il rompait la convention
    # de HPS. Le volume nul d'origine est dans `_remplace_initial`.
    rediff = [l for l in doc["lignes"] if "rediffusé" in l["motif"]]
    assert len(rediff) == 6
    for l in rediff:
        assert serie[l["d"]]["v"] > 0
        assert l.get("_remplace_initial", l["remplace"])["v"] == 0


def test_le_fractionnement_de_2023_ne_coupe_plus_le_graphique():
    """⚠️ LE DÉFAUT, ET MA PREMIÈRE LECTURE FAUSSE.

    Le journal du 01/08/2026 signalait un fractionnement 1:10 du 09/10/2023
    « non déclaré ». Ma confrontation à l'export a d'abord conclu qu'il
    « n'apparaissait pas » : je cherchais un ÉCART entre notre série et celle
    de l'opérateur, et il n'y en a pas — l'opérateur publie lui aussi les cours
    BRUTS. Les deux séries portent la même marche.

    C'est ce test-ci, qui regarde la SÉRIE et non l'écart, qui l'a retrouvée :
    6 400,00 le 06/10, 658,00 le 09/10. Un contrôle qui ne regarde qu'une
    différence ne voit pas ce qui est faux des deux côtés.

    Le ratio est mesuré : 740 619 puis 7 406 190 titres (capitalisation ÷
    cours) sur les deux séances qui encadrent la date d'effet — exactement ×10.
    """
    serie = json.loads((RACINE / "pipeline" / "candles" / "HPS.json")
                       .read_text(encoding="utf-8"))
    sauts = [(a["d"], b["d"], a["c"], b["c"]) for a, b in zip(serie, serie[1:])
             if a["c"] and (b["c"] / a["c"] > 5 or b["c"] / a["c"] < 0.2)]
    assert sauts == [], f"le graphique porte encore une marche : {sauts[:3]}"
    doc = json.loads((CORRECTIONS / "HPS.json").read_text(encoding="utf-8"))
    assert "740 619" in doc["_le_ratio_est_MESURÉ_pas_supposé"]
    assert "7 406 190" in doc["_le_ratio_est_MESURÉ_pas_supposé"]


def test_le_registre_des_splits_n_est_pas_touche_et_c_est_dit():
    """⚠️ La procédure prévoit d'ajouter l'entrée dans `SPLITS`. Ce lot ne le
    fait pas — cela changerait le traitement des données FRAÎCHEMENT
    téléchargées, un effet qu'il ne mesure pas. Le dire vaut mieux que le
    laisser croire."""
    import re
    import subprocess
    doc = json.loads((CORRECTIONS / "HPS.json").read_text(encoding="utf-8"))
    assert "SPLITS" in doc["_pourquoi_le_registre_SPLITS_n_est_pas_touche"]

    # ⚠️ CE TEST COMPARAIT LE FICHIER ENTIER. Il est passé au rouge le 16/09
    # parce que le registre des SUSPENSIONS — qui vit dans le même fichier — a
    # dû enregistrer la reprise de cotation de Minière Touissit, constatée sur
    # le bulletin de l'opérateur. Aucun split n'avait bougé.
    #
    # Un contrôle qui interdit de toucher AU FICHIER quand la règle porte sur
    # UN REGISTRE finit par interdire des corrections légitimes — ou par être
    # désactivé, ce qui est pire. On compare donc le bloc `SPLITS`, et lui seul.
    def _bloc_splits(texte):
        m = re.search(r"^SPLITS[^=]*=\s*\{.*?^\}", texte, re.S | re.M)
        assert m, "le registre SPLITS est introuvable"
        return m.group(0)

    avant = subprocess.run(["git", "show", "origin/main:bvc_config.py"],
                           capture_output=True, text=True, cwd=RACINE)
    if avant.returncode == 0:
        actuel = (RACINE / "bvc_config.py").read_text(encoding="utf-8")
        assert _bloc_splits(avant.stdout) == _bloc_splits(actuel), (
            "le registre des splits a changé : il est hors du périmètre de ce lot")
