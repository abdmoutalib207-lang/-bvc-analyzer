#!/usr/bin/env python3
"""Résoudre un conflit sans arbitrer sur la date du fichier.

⚠️ CE QUE CES TESTS PROTÈGENT
`_updated` dit quand un fichier a été ÉCRIT, pas ce qu'il contient. Arbitrer
dessus paraît raisonnable et ne l'est pas : le 28/08/2026, une source a reculé
d'une séance et deux fichiers plus récents portaient des cours plus anciens.
La règle doit donc porter sur la dernière séance de CHAQUE entrée.

Le test décisif est le dernier : le fichier « le plus récent » y perd, parce
que pour ce titre il porte une séance plus ancienne.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

from resoudre_historique import resoudre  # noqa: E402


def e(date: str, **kw) -> dict:
    base = {"last_date": date, "last_close": 100.0, "rsi": 50.0, "n_candles": 500}
    base.update(kw)
    return base


def test_la_seance_la_plus_recente_l_emporte():
    r = resoudre({"ADH": e("2026-09-08")}, {"ADH": e("2026-09-10")})
    assert r["resolu"]["ADH"]["last_date"] == "2026-09-10"
    assert r["journal"][0]["cas"] == "seance_plus_recente"


def test_un_titre_absent_d_un_cote_n_est_jamais_perdu():
    """⚠️ Une résolution de conflit ne doit supprimer aucun titre — R1."""
    r = resoudre({"ADH": e("2026-09-08"), "CSR": e("2026-09-08")},
                 {"ADH": e("2026-09-10")})
    assert set(k for k in r["resolu"]) == {"ADH", "CSR"}
    assert r["decisions_par_cas"]["present_d_un_seul_cote"] == 1


def test_un_extremum_glissant_n_est_pas_un_desaccord():
    """h52w dépend de la date d'ancrage de la fenêtre, pas de la séance :
    deux runs séparés d'un jour donnent deux valeurs également justes."""
    r = resoudre({"AFM": e("2026-09-09", h52w=1367.0)},
                 {"AFM": e("2026-09-09", h52w=1360.0)})
    assert r["resolu"]["AFM"]["h52w"] == 1360.0
    assert r["journal"][0]["cas"] == "fenetre_glissante"
    assert not r["non_arbitres"]


def test_un_desaccord_sur_un_cours_n_est_PAS_arbitre():
    """⚠️ Aucune règle ne dit laquelle des deux clôtures est juste. Trancher
    au hasard fabriquerait une donnée ; on conserve et on signale."""
    r = resoudre({"MSA": e("2026-09-09", last_close=822.6)},
                 {"MSA": e("2026-09-09", last_close=231.0)})
    assert r["journal"][0]["cas"] == "NON_ARBITRE"
    assert r["non_arbitres"][0]["champs"] == ["last_close"]
    assert r["resolu"]["MSA"]["last_close"] == 822.6, "l'existant a été écrasé"


def test_le_fichier_le_plus_recent_PEUT_perdre_sur_un_titre():
    """⚠️ LE TEST QUI INTERDIT L'ARBITRAGE GLOBAL.

    Ici le fichier de droite est globalement le plus frais — il porte la
    séance du 10 pour ADH. Mais pour CSR il a reculé au 05, exactement comme
    le 28/08/2026. Un arbitrage « au fichier le plus récent » ferait reculer
    CSR de quatre séances sans que rien ne le signale.
    """
    gauche = {"ADH": e("2026-09-08"), "CSR": e("2026-09-09", last_close=194.5)}
    droite = {"ADH": e("2026-09-10"), "CSR": e("2026-09-05", last_close=190.0)}
    r = resoudre(gauche, droite, "branche", "main")

    assert r["resolu"]["ADH"]["last_date"] == "2026-09-10"
    assert r["resolu"]["CSR"]["last_date"] == "2026-09-09", \
        "un titre a reculé : l'arbitrage s'est fait sur le fichier, pas sur l'entrée"
    assert r["resolu"]["CSR"]["last_close"] == 194.5
    retenus = {d["titre"]: d["retenu"] for d in r["journal"]}
    assert retenus == {"ADH": "main", "CSR": "branche"}


def test_la_date_du_fichier_n_est_lue_nulle_part():
    """La consigne est structurelle : le programme ne doit pas même y accéder.

    ⚠️ Une première version de ce test cherchait la chaîne « _updated » dans le
    code. Elle échouait sur la phrase qui DÉCLARE la règle — une mention n'est
    pas une lecture. On examine donc les accès réels : indexation et `.get()`.
    """
    import ast

    src = (RACINE / "pipeline" / "resoudre_historique.py").read_text(encoding="utf-8")
    acces = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) \
                and n.slice.value == "_updated":
            acces.append(("indexation", n.lineno))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == "get" and n.args \
                and isinstance(n.args[0], ast.Constant) \
                and n.args[0].value == "_updated":
            acces.append(("get", n.lineno))
    assert not acces, f"la date du fichier est lue par le code : {acces}"


def test_le_conflit_reel_est_resolu_sans_titre_perdu_ni_seance_reculee():
    """Le cas du dépôt, rejoué sur les deux versions réelles."""
    import json
    import subprocess

    def version(ref: str) -> dict:
        try:
            return json.loads(subprocess.check_output(
                ["git", "show", f"{ref}:pipeline/historical_data.json"],
                text=True, cwd=RACINE, stderr=subprocess.DEVNULL))
        except subprocess.CalledProcessError:
            return {}

    b = version("f803a370b9eab4cbce629f34dbeef75bbf9d2934")
    m = version("27228f46e89aa4f6ad519ff6fdd1466c848412da")
    if not b or not m:
        import pytest
        pytest.skip("commits absents de ce clone")

    r = resoudre(b, m, "branche", "main")
    titres = {k for k in b if not k.startswith("_")} | {k for k in m if not k.startswith("_")}
    assert set(r["resolu"]) == titres
    for t in titres:
        attendu = max((b.get(t, {}).get("last_date") or ""),
                      (m.get(t, {}).get("last_date") or ""))
        assert (r["resolu"][t].get("last_date") or "") == attendu, f"{t} a reculé"
    assert r["non_arbitres"] == [], \
        f"des désaccords restent à trancher : {r['non_arbitres']}"


# ═══ LE DOCUMENT DE FUSION NE DOIT PAS ATTRIBUER AU MAUVAIS CÔTÉ ══════════

def _compter_chandelles(depuis: str, vers: str) -> int:
    import subprocess
    try:
        s = subprocess.check_output(
            ["git", "diff", "--name-only", depuis, vers, "--", "pipeline/candles/"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return -1
    return len([l for l in s.splitlines() if l.strip()])


def test_la_branche_n_introduit_aucune_chandelle():
    """⚠️ L'ERREUR D'ATTRIBUTION, FIGÉE EN TEST.

    J'avais écrit « la branche modifie 66 fichiers de chandelles ». Le 66 est
    réel, mais il mesure `branche ↔ main` — une DIFFÉRENCE, pas un apport. Du
    côté de la branche, l'ancêtre commun donne zéro.
    """
    import subprocess
    try:
        ancetre = subprocess.check_output(
            ["git", "merge-base", "HEAD", "origin/main"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        import pytest
        pytest.skip("origin/main absent de ce clone")

    apportees = _compter_chandelles(ancetre, "HEAD")
    assert apportees == 0, (
        f"la branche introduit {apportees} chandelle(s) — le document de "
        f"fusion affirme le contraire, l'un des deux doit être corrigé")


def test_le_document_ne_reattribue_pas_les_66_chandelles():
    """La phrase fautive ne doit pas revenir, même reformulée."""
    doc = (RACINE / "docs" / "PROPOSITION_FUSION.md").read_text(encoding="utf-8")
    fautif = "La branche modifie **66 fichiers de chandelles**"
    # ⚠️ La phrase figure dans le tableau des erreurs reconnues, précédée du
    # guillemet ouvrant. Elle ne doit apparaître que là, comme citation.
    assert doc.count("66 fichiers de chandelles") <= 1
    assert f"« {fautif} »" in doc or fautif not in doc, \
        "l'affirmation fautive est reprise comme si elle était juste"
    assert "ancêtre → **branche**" in doc, \
        "le document ne distingue plus différence et apport"


def test_la_resolution_conserve_la_mise_en_forme_du_producteur(tmp_path):
    """⚠️ Une résolution ne doit pas reformater le fichier.

    La première version écrivait du JSON compacté là où le collecteur écrit
    `indent=2` : 103 836 lignes de différence sans qu'une seule valeur bouge.
    Un tel diff cache les vrais changements au lieu de les montrer.
    """
    import json
    import subprocess
    import sys

    g = tmp_path / "g.json"; d = tmp_path / "d.json"; s = tmp_path / "s.json"
    g.write_text(json.dumps({"_updated": "x", "ADH": e("2026-09-08")}), encoding="utf-8")
    d.write_text(json.dumps({"_updated": "y", "ADH": e("2026-09-10")}), encoding="utf-8")
    subprocess.run([sys.executable, str(RACINE / "pipeline" / "resoudre_historique.py"),
                    "--notre", str(g), "--leur", str(d), "--ecrire", str(s)],
                   check=True, capture_output=True)
    lignes = s.read_text(encoding="utf-8").splitlines()
    assert len(lignes) > 5, "le fichier a été écrit compacté"
    assert lignes[1].startswith("  "), "l'indentation du producteur n'est pas conservée"
