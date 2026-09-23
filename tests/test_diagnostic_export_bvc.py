#!/usr/bin/env python3
"""Le diagnostic doit nommer chaque défaut, et surtout ne pas les confondre.

⚠️ CE QUE CES TESTS DÉFENDENT
─────────────────────────────
Trois défauts cohabitent dans nos séries et **appellent des lectures
opposées** :

  1. un volume en DIRHAMS — l'unité est fausse, la séance a bien eu lieu ;
  2. un volume valant le COURS une séance SANS ÉCHANGE — le titre n'a pas
     échangé, et nous prétendons le contraire ;
  3. une CLÔTURE fausse — ce n'est pas un défaut de volume du tout, et il
     tombe sous R1.

Un diagnostic qui les mélangerait rendrait un total juste et une conclusion
fausse. D'où un test par famille, chacun sur un cas où les deux autres ne se
produisent PAS.

⚠️ Aucun attendu n'est calculé par le code testé : les fixtures sont écrites
à la main, colonne par colonne, depuis le format réel de l'export.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import diagnostiquer_export_bvc as diag  # noqa: E402

EN_TETE = ("Séance;Ticker;Instrument;Ouverture;Dernier Cours;Plus Haut;"
           "Plus Bas;Volume (MAD);Titres Échangés;Nb Transactions;"
           "Capitalisation")


def _export(tmp_path, code, lignes, instrument="UN TITRE"):
    """Un export au format reçu de l'opérateur, BOM compris.

    `lignes` : (JJ/MM/AAAA, cours, volume_mad, titres_echanges).
    """
    corps = [EN_TETE]
    for seance, cours, mad, titres in lignes:
        corps.append(f"{seance};{code}  ;{instrument};{cours};{cours};{cours};"
                     f"{cours};{mad};{titres};10;1000000.00")
    f = tmp_path / f"Cours_{code}.csv"
    f.write_text("﻿" + "\n".join(corps) + "\n", encoding="utf-8")
    return f


def _candles(monkeypatch, tmp_path, ticker, bougies):
    """Nos chandelles, telles qu'elles sont stockées : d/o/h/l/c/v."""
    d = tmp_path / "candles"
    d.mkdir(exist_ok=True)
    (d / f"{ticker}.json").write_text(json.dumps(bougies), encoding="utf-8")
    monkeypatch.setattr(diag, "CANDLES", d)


# ── L'identité ─────────────────────────────────────────────────────────────

def test_l_identite_vient_du_code_lu_dans_le_fichier(tmp_path, monkeypatch):
    """⚠️ `TGC` est le code de l'OPÉRATEUR ; notre ticker est `TGCC`. Résoudre
    par le nom du fichier, ou prendre le code tel quel, viserait une série qui
    n'existe pas — ou pire, celle d'un autre titre."""
    _candles(monkeypatch, tmp_path, "TGCC",
             [{"d": "2026-09-22", "o": 1, "h": 1, "l": 1, "c": 700.0, "v": 50}])
    f = _export(tmp_path, "TGC", [("22/09/2026", "700.00", "35000.00", "50")])
    assert diag.diagnostiquer(f)["ticker"] == "TGCC"


def test_un_code_inconnu_est_refuse_et_non_devine(tmp_path, monkeypatch):
    """Mieux vaut un refus qu'une attribution muette : c'est ainsi que Sonasid
    a hérité des cotations de Stokvis."""
    _candles(monkeypatch, tmp_path, "AAA", [])
    f = _export(tmp_path, "ZZZ", [("22/09/2026", "700.00", "35000.00", "50")])
    assert diag.diagnostiquer(f)["refus"] == "identité non résolue"


def test_un_export_melangeant_deux_codes_est_refuse(tmp_path, monkeypatch):
    _candles(monkeypatch, tmp_path, "ATW", [])
    f = tmp_path / "melange.csv"
    f.write_text("﻿" + EN_TETE + "\n"
                 "22/09/2026;ATW;A;1;1;1;1;1.00;1;1;1\n"
                 "21/09/2026;BCP;B;1;1;1;1;1.00;1;1;1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        diag.diagnostiquer(f)


# ── « - » n'est pas zéro ───────────────────────────────────────────────────

def test_le_tiret_n_est_pas_zero():
    """⚠️ La garde centrale du défaut n°2. Si `nombre('-')` rendait 0.0, une
    séance sans échange deviendrait une séance à volume nul, et le cours
    recopié dans le volume passerait pour un simple écart."""
    assert diag.nombre("-") is None
    assert diag.nombre("") is None
    assert diag.nombre("0.00") == 0.0


def test_les_milliers_espaces_sont_lus():
    assert diag.nombre("1 610 624.90") == 1610624.90


# ── Les trois familles, chacune isolée ─────────────────────────────────────

def test_le_volume_en_dirhams_est_reconnu(tmp_path, monkeypatch):
    """Le cours est juste, la séance a échangé : seule l'unité est fausse."""
    _candles(monkeypatch, tmp_path, "ATW",
             [{"d": "2026-09-22", "o": 1, "h": 1, "l": 1,
               "c": 691.0, "v": 23343966}])
    f = _export(tmp_path, "ATW",
                [("22/09/2026", "691.00", "23343966.70", "33778")])
    r = diag.diagnostiquer(f)
    assert len(r["volume_en_dirhams"]) == 1
    assert r["volume_en_dirhams"][0]["titres"] == 33778
    assert not r["cloture_fausse"], "le cours était juste"
    assert not r["volume_vaut_le_cours"]


def test_le_cours_recopie_dans_le_volume_est_reconnu(tmp_path, monkeypatch):
    """⚠️ La séance n'a PAS échangé — l'export écrit « - » sur les deux
    colonnes de volume. Notre `v` vaut le cours."""
    _candles(monkeypatch, tmp_path, "CDM",
             [{"d": "2023-09-25", "o": 1, "h": 1, "l": 1,
               "c": 700.0, "v": 700}])
    f = _export(tmp_path, "CDM", [("25/09/2023", "700.00", "-", "-")])
    r = diag.diagnostiquer(f)
    assert len(r["volume_vaut_le_cours"]) == 1
    assert not r["volume_en_dirhams"]
    assert not r["cloture_fausse"]


def test_une_seance_sans_echange_et_sans_volume_chez_nous_est_conforme(
        tmp_path, monkeypatch):
    """Le pendant du test précédent : `v = 0` un jour sans échange est JUSTE.
    Sans ce cas, le diagnostic accuserait le comportement correct."""
    _candles(monkeypatch, tmp_path, "CDM",
             [{"d": "2023-09-25", "o": 1, "h": 1, "l": 1, "c": 700.0, "v": 0}])
    f = _export(tmp_path, "CDM", [("25/09/2023", "700.00", "-", "-")])
    r = diag.diagnostiquer(f)
    assert not r["volume_vaut_le_cours"]
    assert r["conformes"] == 1


def test_la_cloture_fausse_est_reconnue_comme_telle(tmp_path, monkeypatch):
    """⚠️ Et elle ne doit PAS être comptée comme un défaut de volume : ici le
    volume est parfaitement juste."""
    _candles(monkeypatch, tmp_path, "CDM",
             [{"d": "2026-06-30", "o": 1, "h": 1, "l": 1,
               "c": 1007.0, "v": 479}])
    f = _export(tmp_path, "CDM", [("30/06/2026", "962.00", "460000.00", "479")])
    r = diag.diagnostiquer(f)
    assert len(r["cloture_fausse"]) == 1
    assert r["cloture_fausse"][0]["officiel"] == 962.0
    assert not r["volume_en_dirhams"]
    assert not r.get("volume_inexplique")


def test_une_cloture_qui_est_celle_de_la_veille_est_signalee(
        tmp_path, monkeypatch):
    """Le motif du 18/06→06/08 : la série porte la séance précédente. C'est
    lui qui distingue « donnée fausse » de « collecte en retard »."""
    _candles(monkeypatch, tmp_path, "CDM",
             [{"d": "2026-06-18", "o": 1, "h": 1, "l": 1, "c": 1006.0, "v": 92},
              {"d": "2026-06-19", "o": 1, "h": 1, "l": 1, "c": 1006.0, "v": 92}])
    f = _export(tmp_path, "CDM",
                [("18/06/2026", "1006.00", "3347526.00", "3321"),
                 ("19/06/2026", "1024.00", "93751.00", "92")])
    r = diag.diagnostiquer(f)
    fautives = {x["d"]: x for x in r["cloture_fausse"]}
    assert "2026-06-19" in fautives
    assert fautives["2026-06-19"]["est_la_cloture_de_la_veille"] is True


def test_la_premiere_seance_ne_peut_pas_reculer(tmp_path, monkeypatch):
    """Il n'y a pas de veille avant la première ligne de l'export : le test de
    recul doit rendre False, et non tomber."""
    _candles(monkeypatch, tmp_path, "CDM",
             [{"d": "2026-06-18", "o": 1, "h": 1, "l": 1, "c": 999.0, "v": 3321}])
    f = _export(tmp_path, "CDM", [("18/06/2026", "1006.00", "3347526.00", "3321")])
    r = diag.diagnostiquer(f)
    assert r["cloture_fausse"][0]["est_la_cloture_de_la_veille"] is False


# ── Ce que le relevé doit dire par ailleurs ────────────────────────────────

def test_une_seance_de_l_export_absente_chez_nous_est_signalee(
        tmp_path, monkeypatch):
    """Les 22, 23 et 24 juin manquent aux 27 titres. Un relevé qui ne compare
    que les dates communes ne les verrait jamais."""
    _candles(monkeypatch, tmp_path, "CDM",
             [{"d": "2026-06-25", "o": 1, "h": 1, "l": 1, "c": 970.0, "v": 104}])
    f = _export(tmp_path, "CDM",
                [("22/06/2026", "980.00", "1000.00", "10"),
                 ("25/06/2026", "970.00", "100000.00", "104")])
    assert diag.diagnostiquer(f)["seances_absentes"] == ["2026-06-22"]


def test_nos_seances_anterieures_a_l_export_ne_sont_pas_des_defauts(
        tmp_path, monkeypatch):
    """L'export couvre trois ans. Ce que nous avons avant n'est pas fautif —
    il est seulement hors de portée de cette pièce, et le compter comme un
    écart condamnerait la moitié de nos séries."""
    _candles(monkeypatch, tmp_path, "CDM",
             [{"d": "2020-01-02", "o": 1, "h": 1, "l": 1, "c": 500.0, "v": 9},
              {"d": "2026-06-25", "o": 1, "h": 1, "l": 1, "c": 970.0, "v": 104}])
    f = _export(tmp_path, "CDM", [("25/06/2026", "970.00", "100000.00", "104")])
    r = diag.diagnostiquer(f)
    assert r["hors_periode_export"] == 1
    assert r["conformes"] == 1
    assert not r["cloture_fausse"] and not r["volume_en_dirhams"]


def test_un_volume_sans_rapport_avec_aucune_colonne_est_isole(
        tmp_path, monkeypatch):
    """Ni titres, ni dirhams : ces volumes-là ne se convertissent pas, ils se
    remplacent. Les fondre dans « vol=MAD » ferait croire à une conversion
    possible."""
    _candles(monkeypatch, tmp_path, "CDM",
             [{"d": "2026-06-18", "o": 1, "h": 1, "l": 1,
               "c": 1006.0, "v": 690000}])
    f = _export(tmp_path, "CDM", [("18/06/2026", "1006.00", "3347526.00", "3321")])
    r = diag.diagnostiquer(f)
    assert len(r.get("volume_inexplique") or []) == 1
    assert not r["volume_en_dirhams"]


def test_l_outil_n_ecrit_jamais_dans_les_chandelles():
    """⚠️ Il mesure et il nomme. La réparation passe par une réception
    documentée ; un outil qui écrirait ferait disparaître cette trace.

    ⚠️ Le contrôle passe par l'AST, pas par une recherche de texte. Hier, un
    test écrit à la ligne accusait la CITATION d'un motif dans un commentaire
    explicatif — et ce fichier-ci nomme `write_text` dans sa prose. Un test qui
    rougit sur une explication n'accuse rien.
    """
    import ast
    arbre = ast.parse((RACINE / "pipeline" / "diagnostiquer_export_bvc.py")
                      .read_text(encoding="utf-8"))
    interdits = {"write_text", "write_bytes", "unlink", "mkdir", "rename"}
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call):
            f = n.func
            nom = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            assert nom not in interdits and nom != "open", (
                f"le diagnostic appelle {nom}() — il ne doit rien écrire")
