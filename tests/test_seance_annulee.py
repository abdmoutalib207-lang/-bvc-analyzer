#!/usr/bin/env python3
"""Une séance peut avoir lieu, puis ne plus avoir existé.

CE QUI S'EST PASSÉ LE 17/09/2026
────────────────────────────────
    09h30   la Bourse de Casablanca ouvre, les échanges démarrent
    10h39   Alphabourse : « la séance suspendue », incident technique
    11h18   dernier échange, tous titres confondus
    11h47   toujours rien — 47 484 titres au total, contre 216,3 MDH
            pour la séance complète de la veille
    le soir la Bourse arrête DÉFINITIVEMENT la séance : toutes les
            transactions, saisies, modifications et annulations d'ordres
            de la journée sont annulées. La reprise se fera sur la base des
            carnets d'ordres arrêtés à la clôture du 16 septembre.

⚠️ AUCUN DES DEUX GARDE-FOUS EXISTANTS NE POUVAIT LA VOIR
─────────────────────────────────────────────────────────
Un FÉRIÉ se connaît d'avance : `est_ferie_fixe` le lit dans un calendrier.

Une séance FANTÔME se déduit des données : `_recaler_seance_fantome` reconnaît
la signature d'une source qui rediffuse la veille — au moins 95 % de clôtures
identiques. Mesuré ce jour-là : **17 %**. Rien à voir.

Une séance ANNULÉE ne ressemble à ni l'une ni l'autre. Les cours étaient
authentiques, les volumes réels, les heures d'échange échelonnées de 09h30 à
11h18. **C'est leur existence juridique qui a été retirée, pas leur
vraisemblance.**

⚠️ ET AUCUNE DE NOS TROIS SOURCES NE PUBLIE LE STATUT D'UNE SÉANCE. Elles
servent des cours. BMCE a continué de servir 55 titres datés du 17/09 après
l'annulation. La seule défense possible est une déclaration écrite à la main.

C'est Abd Moutalib qui a signalé l'information — aucun contrôle du dépôt ne
l'aurait trouvée.
"""

from __future__ import annotations

import glob
import importlib.util
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))
CANDLES = RACINE / "pipeline" / "candles"


@pytest.fixture(scope="module")
def moteur():
    spec = importlib.util.spec_from_file_location("ud_ann", RACINE / "update_data.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["ud_ann"] = m
    spec.loader.exec_module(m)
    return m


# ── Le registre ──────────────────────────────────────────────────────────────

def test_la_seance_annulee_est_inscrite_et_sourcee():
    """Une annulation se constate sur une pièce, elle ne se décrète pas."""
    from bvc_config import SEANCES_ANNULEES, seance_annulee
    assert "2026-09-17" in SEANCES_ANNULEES
    e = SEANCES_ANNULEES["2026-09-17"]
    assert e.get("source"), "l'annulation n'est adossée à aucune pièce"
    assert e.get("motif") and "annul" in e["motif"].lower()
    assert seance_annulee("2026-09-17") is True
    assert seance_annulee("2026-09-16") is False
    # ⚠️ Les entrées nulles ne doivent pas faire tomber le run : `prix_asof`
    # vaut None dès qu'un titre n'a pas de séance connue.
    assert seance_annulee(None) is False
    assert seance_annulee("") is False


# ── Rien dans les données publiées ──────────────────────────────────────────

def test_aucune_bougie_ne_porte_une_seance_annulee():
    """LA RÈGLE, et elle ne nomme aucune date : elle lit le registre."""
    from bvc_config import SEANCES_ANNULEES
    fautifs = []
    for f in sorted(CANDLES.glob("*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        mauvaises = [b["d"] for b in s if str(b.get("d") or "")[:10] in SEANCES_ANNULEES]
        if mauvaises:
            fautifs.append(f"{f.stem} : {mauvaises}")
    assert not fautifs, ("des bougies portent une séance annulée :\n  "
                         + "\n  ".join(fautifs[:10]))


def test_aucun_titre_publie_n_est_date_d_une_seance_annulee():
    from bvc_config import SEANCES_ANNULEES
    from conftest import chemin_data_json
    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    fautifs = [t["symbol"] for t in d["tickers"]
               if str((t.get("_meta") or {}).get("prix_asof") or "")[:10] in SEANCES_ANNULEES]
    assert not fautifs, f"titres datés d'une séance annulée : {fautifs[:10]}"


# ── Le moteur refuse, même si la source insiste ─────────────────────────────

def test_les_lignes_datees_d_une_seance_annulee_sont_ecartees(moteur):
    """⚠️ BMCE a continué de servir la séance annulée APRÈS son annulation.

    Le moteur ne peut pas attendre que la source se ravise : elle ne publie
    pas les statuts.
    """
    lp = {"IAM": {"price": 95.0, "asof": "2026-09-17", "src": "bmce"},
          "ATW": {"price": 700.0, "asof": "2026-09-17", "src": "bmce"},
          "BCP": {"price": 240.0, "asof": "2026-09-16", "src": "cdg"}}
    r = moteur._ecarter_seances_annulees(lp, "2026-09-17")
    assert "IAM" not in lp and "ATW" not in lp, "une ligne annulée a survécu"
    assert "BCP" in lp, "une ligne valide a été emportée"
    assert r == "2026-09-16", f"séance de référence retenue : {r}"


def test_la_reference_se_reprend_aux_chandelles_pas_aux_survivants(moteur):
    """⚠️ MA PREMIÈRE VERSION PRENAIT LE MAXIMUM DES LIGNES SURVIVANTES.

    Presque toutes les sources dataient du jour annulé : il n'en restait que
    trois, et la séance de référence est tombée au 05/08 — six semaines en
    arrière. Les chandelles tiennent la dernière séance réellement valide.
    """
    lp = {"IAM": {"price": 95.0, "asof": "2026-09-17"},
          "VIEUX": {"price": 10.0, "asof": "2026-08-05"}}
    r = moteur._ecarter_seances_annulees(lp, "2026-09-17")
    assert r != "2026-08-05", "la référence est retombée sur une ligne périmée"
    assert r == "2026-09-16"


def test_une_journee_sans_annulation_passe_intacte(moteur):
    """Contre-épreuve : un contrôle qui écarterait tout arrêterait la collecte."""
    lp = {"IAM": {"price": 95.0, "asof": "2026-09-16"},
          "ATW": {"price": 700.0, "asof": "2026-09-16"}}
    avant = dict(lp)
    r = moteur._ecarter_seances_annulees(lp, "2026-09-16")
    assert lp == avant and r == "2026-09-16"


# ── La purge, dirigée par la déclaration ────────────────────────────────────

def test_la_purge_retire_exactement_les_seances_declarees(tmp_path, monkeypatch):
    import seance as S
    from bvc_config import SEANCES_ANNULEES
    d = tmp_path / "candles"; d.mkdir()
    serie = [{"d": "2026-09-16", "o": 1, "h": 1, "l": 1, "c": 100.0, "v": 5},
             {"d": "2026-09-17", "o": 1, "h": 1, "l": 1, "c": 101.0, "v": 7},
             {"d": "2026-09-18", "o": 1, "h": 1, "l": 1, "c": 102.0, "v": 9}]
    (d / "ZZZ.json").write_text(json.dumps(serie), encoding="utf-8")
    dates, n, touches = S.purger_seances_annulees(candles_dir=d)
    assert "2026-09-17" in dates and n == 1 and touches == ["ZZZ"]
    reste = json.loads((d / "ZZZ.json").read_text(encoding="utf-8"))
    assert [b["d"] for b in reste] == ["2026-09-16", "2026-09-18"], (
        "la purge a emporté autre chose que la séance déclarée")


def test_la_purge_a_blanc_n_ecrit_rien(tmp_path):
    import seance as S
    d = tmp_path / "candles"; d.mkdir()
    serie = [{"d": "2026-09-17", "o": 1, "h": 1, "l": 1, "c": 101.0, "v": 7}]
    f = d / "ZZZ.json"; f.write_text(json.dumps(serie), encoding="utf-8")
    avant = f.read_bytes()
    _, n, _ = S.purger_seances_annulees(candles_dir=d, dry_run=True)
    assert n == 1 and f.read_bytes() == avant


# ── La capitalisation ne doit pas retomber sur la table figée ───────────────

def test_la_capitalisation_de_la_veille_passe_avant_la_table_figee():
    """⚠️ CE DÉFAUT EXISTAIT DEPUIS TOUJOURS ; IL A SUFFI QUE LES SOURCES SE TAISENT.

    Écrit `lp.get("cap") or fd.get("cap")`, le moteur sautait par-dessus tout
    ce qu'il savait dès que la ligne vivante disparaissait, pour retomber sur
    `FOND_DATA` — une table où Wafa Assurance vaut 6 500 MDHS contre 18 200 au
    marché, et Taqa 8 500 contre 41 068.

    Le 17/09, la séance annulée a fait disparaître TOUTES les lignes vivantes
    d'un coup, et la capitalisation de la moitié de la cote est retombée sur la
    table. Quatre contrôles ont rougi ensemble.
    """
    s = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '_cap_precedente = (_ex_all.get(ticker) or {}).get("cap")' in s, (
        "la capitalisation publiée la veille n'est plus consultée")
    assert 'lp.get("cap") or _cap_precedente or fd.get("cap")' in s, (
        "l'ordre du repli ne place plus la veille avant la table figée")
    assert '_cap_source = "publiee_la_veille"' in s, (
        "une capitalisation reprise de la veille est annoncée comme « servie »")
