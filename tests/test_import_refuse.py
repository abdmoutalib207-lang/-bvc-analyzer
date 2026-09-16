#!/usr/bin/env python3
"""Un refus arrête le geste. Sinon ce n'est pas un contrôle, c'est un journal.

CE QUI S'EST PASSÉ LE 16/09/2026 À 19h21
────────────────────────────────────────
`generate_candles.py` a rechargé l'XLSX de Sothema, a soumis le résultat à la
couche des corrections réceptionnées, et celle-ci a refusé les 191 séances :
« l'état actuel n'est ni l'ancien ni le corrigé — la série a changé depuis la
réception ». Le refus est parti dans le journal, ligne après ligne.

Puis le programme a écrit sa série par-dessus.

Les 220 ruptures de l'ancienne échelle sont revenues dans `candles/SOT.json`,
les contrôles bloquants ont rougi, et plus rien ne pouvait être publié — y
compris la reprise de cotation de Minière Touissit, qui n'a rien à voir.

⚠️ LE CONTRÔLE AVAIT RAISON. C'est le seul point rassurant de l'affaire : il a
vu que la série ne correspondait plus à ce qui avait été réceptionné, et il l'a
dit. Personne ne l'écoutait.

LE SECOND DÉFAUT, PLUS SILENCIEUX ENCORE
────────────────────────────────────────
`appliquer()` ne renvoie PAS de clé `refus` quand aucun lot n'existe pour le
titre — et c'est le cas ordinaire, soixante et un titres sur soixante-treize.
L'indexer levait `KeyError('refus')`, l'exception remontait dans le
`except Exception` de l'appelant, et le titre sortait sur :

    ✗ SRM: 'refus'

Un message qui a toutes les apparences d'un refus motivé, et qui est un
plantage. Ces titres n'ont simplement pas eu de chandelles ce jour-là.

LA RÈGLE, ÉNONCÉE PAR ABD MOUTALIB
──────────────────────────────────
« Conservez les données et indicateurs antérieurs valides lorsqu'un nouvel
import est refusé. » Ce qui est sur le disque a été réceptionné ; ce qui arrive
ne l'a pas été.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))


@pytest.fixture()
def gc():
    import generate_candles as G
    return G


# ── Le premier défaut : un titre sans lot ne doit pas planter ────────────────

def test_un_titre_sans_correction_traverse_sans_planter(gc, tmp_path):
    """⚠️ C'est le cas ORDINAIRE, pas le cas limite.

    Soixante et un titres sur soixante-treize n'ont aucune correction
    réceptionnée. Si ce chemin lève, c'est la collecte entière qui s'arrête —
    et elle s'arrête en affichant un mot, « refus », qui fait croire à une
    décision.
    """
    bougies = [{"d": "2026-09-16", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]
    sortie, refus = gc._reimposer("TICKER_SANS_LOT", bougies)
    assert sortie == bougies, "les bougies ont été altérées sans instruction"
    assert refus == [], "un titre sans lot ne peut pas produire de refus"


def test_un_titre_avec_lot_applicable_est_corrige(gc):
    """Contre-épreuve : la couche doit continuer d'imposer ce qu'elle doit."""
    import json as j
    lot = j.loads((RACINE / "datasets" / "corrections_acceptees" / "SOT.json")
                  .read_text(encoding="utf-8"))
    ligne = lot["lignes"][0]
    avant = [dict({"d": ligne["d"]}, **ligne["remplace"])]
    sortie, refus = gc._reimposer("SOT", avant)
    assert refus == []
    assert sortie[0]["c"] == ligne["corrige"]["c"], (
        "la correction réceptionnée n'a pas été imposée")


# ── Le défaut principal : un refus doit arrêter l'écriture ───────────────────

def test_un_refus_conserve_le_fichier_existant(gc, tmp_path, monkeypatch):
    """⚠️ LE CŒUR DE L'AFFAIRE, éprouvé sur le chemin d'écriture réel.

    On place sur le disque une série réceptionnée, on fait arriver un import
    qui la contredit, et on exige que le fichier ne bouge pas d'un octet.
    """
    candles = tmp_path / "candles"; candles.mkdir()
    xlsx_dir = tmp_path / "xlsx"; xlsx_dir.mkdir()
    (xlsx_dir / "SOT.xlsx").write_bytes(b"factice")

    recu = [{"d": "2026-09-15", "o": 200.0, "h": 200.0, "l": 200.0,
             "c": 200.0, "v": 5}]
    cible = candles / "SOT.json"
    cible.write_text(json.dumps(recu, separators=(",", ":")))
    empreinte = cible.read_bytes()

    monkeypatch.setattr(gc, "CANDLES_DIR", candles)
    monkeypatch.setattr(gc, "XLSX_DIR", xlsx_dir)
    monkeypatch.setattr(gc, "_xlsx_to_candles", lambda p: [
        {"d": "2026-09-15", "o": 43.0, "h": 43.0, "l": 43.0, "c": 43.0, "v": 5}])
    monkeypatch.setattr(gc, "adjust_splits", lambda t, c, date_key="d": c)
    # La couche refuse : l'état proposé n'est ni l'ancien ni le corrigé.
    monkeypatch.setattr(gc, "_reimposer", lambda t, c: (
        c, [{"seance": "2026-09-15", "motif": "essai"}]))

    gc.generate_from_xlsx()
    assert cible.read_bytes() == empreinte, (
        "le fichier a été réécrit malgré un refus — c'est exactement ce qui a "
        "ramené les 220 ruptures de Sothema le 16/09")


def test_sans_refus_l_import_ecrit_normalement(gc, tmp_path, monkeypatch):
    """⚠️ Contre-épreuve indispensable.

    Une garde qui bloquerait tout bloquerait aussi la collecte. Sans refus, le
    fichier DOIT être mis à jour — sinon on aurait remplacé une contamination
    par un gel général.
    """
    candles = tmp_path / "candles"; candles.mkdir()
    xlsx_dir = tmp_path / "xlsx"; xlsx_dir.mkdir()
    (xlsx_dir / "SOT.xlsx").write_bytes(b"factice")
    cible = candles / "SOT.json"
    cible.write_text(json.dumps(
        [{"d": "2026-09-15", "o": 200.0, "h": 200.0, "l": 200.0,
          "c": 200.0, "v": 5}], separators=(",", ":")))

    neuf = [{"d": "2026-09-16", "o": 205.0, "h": 205.0, "l": 205.0,
             "c": 205.0, "v": 7}]
    monkeypatch.setattr(gc, "CANDLES_DIR", candles)
    monkeypatch.setattr(gc, "XLSX_DIR", xlsx_dir)
    monkeypatch.setattr(gc, "_xlsx_to_candles", lambda p: neuf)
    monkeypatch.setattr(gc, "adjust_splits", lambda t, c, date_key="d": c)
    monkeypatch.setattr(gc, "_reimposer", lambda t, c: (c, []))

    gc.generate_from_xlsx()
    ecrit = json.loads(cible.read_text())
    assert [b["d"] for b in ecrit] == ["2026-09-15", "2026-09-16"], (
        "la séance du jour n'est pas entrée — la garde bloque trop")


# ── Ce que le dépôt doit montrer ────────────────────────────────────────────

def test_les_deux_chemins_d_ecriture_portent_la_garde():
    """⚠️ Trois programmes écrivent dans `pipeline/candles/`, et celui-ci a
    DEUX portes : XLSX et Médias24. En garder une seule ne garde rien — c'est
    la leçon du 14/09, reprise mot pour mot.
    """
    s = (RACINE / "pipeline" / "generate_candles.py").read_text(encoding="utf-8")
    assert s.count("candles, refus = _reimposer(") == 2, (
        "les deux portes n'appellent pas la garde")
    assert s.count("if refus:") == 2, "une porte écrit sans consulter les refus"
    # Et la garde précède l'écriture, elle ne la suit pas.
    for bloc in s.split("out.write_text")[1:3]:
        pass
    avant = [s.index("if refus:"), s.rindex("if refus:")]
    ecrit = [s.index("out.write_text"), s.rindex("out.write_text")]
    assert avant[0] < ecrit[0] and avant[1] < ecrit[1], (
        "la garde est posée APRÈS l'écriture qu'elle doit empêcher")
