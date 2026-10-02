"""La lecture rédigée et son contrôle des chiffres — 01/10/2026.

Le cas d'école est réel : le briefing de GPT du 30/09 annonçait RDS
« 173,90 DH, +3,45 % » (le plus haut ; la clôture valait 171,00, +1,73 %) et
des scénarios « 45 / 30 / 25 % ». Le contrôle doit refuser ces nombres.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import redaction as R  # noqa: E402

FAITS = {
    "seance": "2026-09-30", "moment": "cloture",
    "constats": ["MASI : clôture 17 733,06 pour une veille à 17 754,91."],
    "a_surveiller": {"a_publie": [{"symbol": "RDS", "chg": 1.73, "volume_rapport": 1.45,
                                   "chiffres": {"rnpg_s1_2026": 19.747, "rnpg_s1_2025": 6.465,
                                                "ca_s1_2026": 208.787, "var_ca_pct": 28.8}}],
                     "a_bouge": []},
    "concentration": {"total_dh": 171_700_000},
}


def test_lecture_des_nombres_a_la_francaise():
    vals = [(v, d) for _, v, d in R.nombres("17 733,06 points, +1,73 %, 2026, 19,7")]
    assert vals == [(17733.06, 2), (1.73, 2), (2026.0, 0), (19.7, 1)]


def test_les_dates_et_heures_ne_sont_pas_des_mesures():
    assert R.nombres("le 30/09/2026 à 15h30, ou 09:30:05, séance 2026-09-30") == []


def test_le_texte_de_gpt_est_refuse():
    texte = ("RDS termine à 173,90 DH, +3,45 %. Scénarios : neutre 45 % "
             "| haussier 30 % | baissier 25 %.")
    c = R.controler(texte, FAITS)
    assert not c["ok"]
    assert {"173,90", "3,45", "45"} <= set(c["refuses"])


def test_un_texte_fidele_aux_faits_passe():
    texte = ("Le MASI clôture à 17 733,06, contre 17 754,91 la veille. RDS a "
             "terminé à +1,73 %, volume 1,45 fois sa médiane ; résultat part du "
             "groupe 19,7 MDH contre 6,5 ; chiffre d'affaires 208,8 MDH (+28,8 %). "
             "Le marché a traité 171,7 MDH.")
    c = R.controler(texte, FAITS)
    assert c["ok"], c["refuses"]


def test_un_arrondi_faux_est_refuse():
    # 19,747 MDH s'arrondit à 19,7 ou 19,75 — jamais à 19,8.
    assert not R.controler("résultat 19,8 MDH", FAITS)["ok"]


def test_la_version_seche_passe_son_propre_controle():
    texte = R.redaction_seche(FAITS)
    assert "RDS" in texte
    assert R.controler(texte, FAITS)["ok"]


def test_une_redaction_claude_est_gardee_si_elle_passe_encore():
    ancien = dict(FAITS, redaction={"texte": "RDS a terminé à +1,73 %.", "auteur": "claude"})
    b = R.rediger(json.loads(json.dumps(FAITS)), ancien)
    assert b["redaction"]["auteur"] == "claude"


def test_une_redaction_claude_perimee_cede_la_place():
    # Les faits ont changé (nouveau passage) : +1,73 % n'existe plus.
    nouveaux = json.loads(json.dumps(FAITS))
    nouveaux["a_surveiller"]["a_publie"][0]["chg"] = 1.20
    ancien = dict(FAITS, redaction={"texte": "RDS a terminé à +1,73 %.", "auteur": "claude"})
    b = R.rediger(nouveaux, ancien)
    assert b["redaction"]["auteur"] == "seche"


def test_appliquer_refuse_sans_rien_ecrire(tmp_path):
    (tmp_path / "briefing_cloture.json").write_text(json.dumps(FAITS), encoding="utf-8")
    c = R.appliquer("RDS +3,45 %", "claude", tmp_path)
    assert not c["ok"]
    assert "redaction" not in json.loads((tmp_path / "briefing_cloture.json").read_text())


def test_appliquer_ecrit_et_archive(tmp_path):
    (tmp_path / "briefing_cloture.json").write_text(json.dumps(FAITS), encoding="utf-8")
    c = R.appliquer("RDS a terminé à +1,73 %.", "claude", tmp_path)
    assert c["ok"]
    b = json.loads((tmp_path / "briefing_cloture.json").read_text())
    assert b["redaction"]["auteur"] == "claude"
    a = json.loads((tmp_path / "briefings" / "2026-09-30.json").read_text())
    assert a["cloture"]["redaction"]["texte"] == "RDS a terminé à +1,73 %."


# ── Lisibilité — 02/10/2026 ───────────────────────────────────────────────

def test_un_nombre_ecrit_deux_fois_est_refuse():
    l = R.lisibilite("Le MASI clôture à 17 733,06. Clôture : 17733,06.")
    assert not l["ok"] and l["repetes"] == ["17733,06"]


def test_trop_de_nombres_est_refuse():
    texte = " ".join(f"{i} %" for i in range(1, 14))  # 13 nombres distincts
    l = R.lisibilite(texte)
    assert l["n_nombres"] == 13 and not l["ok"]
    assert R.lisibilite(" ".join(f"{i} %" for i in range(1, 13)))["ok"]


def test_appliquer_refuse_un_texte_illisible_sans_rien_ecrire(tmp_path):
    (tmp_path / "briefing_cloture.json").write_text(json.dumps(FAITS), encoding="utf-8")
    c = R.appliquer("RDS a terminé à +1,73 %, oui, +1,73 %.", "claude", tmp_path)
    assert not c["ok"] and c["lisibilite"]["repetes"]
    assert "redaction" not in json.loads((tmp_path / "briefing_cloture.json").read_text())


def test_la_version_seche_dit_en_mots_ce_que_les_chiffres_montrent():
    b = dict(FAITS, accord={"ratio": -0.61},
             trajectoire={"veille": 100, "ouverture": 101, "plus_haut": 102,
                          "plus_bas": 98, "cloture": 98})
    texte = R.redaction_seche(b)
    assert "La grande majorité des valeurs a reculé." in texte
    assert "au plus bas de la séance, après avoir effacé son gain d'ouverture" in texte
    assert "RDS a publié ses comptes : résultat semestriel en hausse, et le titre termine en hausse." in texte
    assert R.lisibilite(texte)["ok"]
