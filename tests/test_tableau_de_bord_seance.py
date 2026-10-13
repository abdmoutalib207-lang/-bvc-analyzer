"""Le tableau de bord de la séance (13/10/2026) — ce qu'il affiche, et quand.

Demande d'Abd Moutalib : refaire « DÉTAIL DE LA SÉANCE » dans le style d'un
tableau de bord Power BI, sans Power BI ni dépendance nouvelle. Ce qui doit
tenir, au-delà de l'apparence :

- les visuels PAR TITRE lisent `data.json`, le reste lit le briefing. Ils ne
  s'affichent que si les deux décrivent le même relevé (même séance, somme des
  montants = volume CDG à 0,5 % près). Sinon : retirés et DÉCLARÉS ;
- le nombre de titres échangés n'est publié que dans `data.json` : affiché
  seulement si la séance ET le nombre de transactions concordent ;
- les tranches de l'histogramme forment une partition (un titre, une tranche,
  et « 0,00 % » jamais compté en hausse) ;
- le treemap conserve les surfaces (une tuile = son montant) et reste dans
  son cadre ;
- aucune bibliothèque ajoutée.

Les fonctions pures sont extraites de la source et exécutées par node — le
même moteur que le navigateur — plutôt que relues comme du texte.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def _const(nom: str) -> str:
    """Le texte d'une déclaration `const nom=...;` de premier niveau."""
    i = SRC.index(f"\nconst {nom}=") + 1
    # fin = première ligne suivante qui commence une nouvelle déclaration ou un
    # commentaire de premier niveau
    m = re.compile(r"\n(?=const |// |function |/\*)").search(SRC, i + 1)
    return SRC[i:m.start() if m else len(SRC)]


FONCTIONS = ["meta", "nfr", "jm", "montantCourt", "VARC", "sgp", "mediane", "entier", "jma",
             "titresDuReleve", "titresEchanges", "TRANCHES", "squarify", "absencesTableau"]


def _node(script: str):
    if not shutil.which("node"):
        if os.environ.get("GITHUB_ACTIONS"):
            pytest.fail("la CI doit installer node")
        pytest.skip("node absent en local")
    code = "\n".join(_const(n) for n in FONCTIONS) + "\n" + script
    r = subprocess.run(["node", "-"], input=code, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _ligne(sym, chg, dh, asof="2026-10-13", sector="Banque", susp=False):
    return {"symbol": sym, "chg": chg, "echange_dh": dh, "sector": sector,
            "_meta": {"prix_asof": asof, "suspendu": susp, "confidence": 5}}


BRIEF = {"seance": "2026-10-13", "veille": {"jour": {"volume_mad": 300.0, "transactions": 12}},
         "trajectoire": {"n_points": 678}, "secteurs": [{"code": "B"}], "matieres": [{"ticker": "X"}],
         "depots": {"titres": []}}


def _releve(rows, b=BRIEF):
    return _node(f"const r=titresDuReleve({json.dumps(b)},{json.dumps(rows)});"
                 "console.log(JSON.stringify({ok:r.ok,n:r.l.length}));")


# ── 1. Le recoupement qui autorise les visuels par titre ───────────────────

def test_les_visuels_par_titre_exigent_le_meme_releve():
    rows = [_ligne("A", 1.0, 100), _ligne("B", -1.0, 200)]
    assert _releve(rows) == {"ok": True, "n": 2}


def test_un_autre_moment_de_la_meme_seance_est_refuse():
    """Mi-journée relue le soir : même date, montants différents."""
    rows = [_ligne("A", 1.0, 500), _ligne("B", -1.0, 900)]
    assert _releve(rows)["ok"] is False


def test_une_autre_seance_est_refusee_et_les_suspendus_ecartes():
    rows = [_ligne("A", 1.0, 100, asof="2026-10-12"), _ligne("B", -1.0, 200, asof="2026-10-12")]
    assert _releve(rows) == {"ok": False, "n": 0}
    rows = [_ligne("A", 1.0, 100), _ligne("B", -1.0, 200), _ligne("C", 0.0, 0, susp=True)]
    assert _releve(rows) == {"ok": True, "n": 2}


def test_controle_negatif_un_ecart_de_un_pour_cent_refuse():
    """Le seuil est 0,5 % : 1 % d'écart doit refuser. Un contrôle jamais vu
    rouge ne prouve rien."""
    assert _releve([_ligne("A", 1.0, 303)])["ok"] is False
    assert _releve([_ligne("A", 1.0, 301)])["ok"] is True


def test_le_releve_publie_se_recoupe_reellement():
    """Sur les fichiers du dépôt : si data.json et briefing.json portent la
    même séance et le même nombre de transactions, la somme doit recouper."""
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    b = json.loads((RACINE / "briefing.json").read_text(encoding="utf-8"))
    j = (b.get("veille") or {}).get("jour") or {}
    m = d.get("masi") or {}
    if m.get("asof") != b.get("seance") or m.get("transactions") != j.get("transactions"):
        pytest.skip("data.json et briefing.json ne décrivent pas le même relevé")
    r = _releve(d["tickers"], b)
    assert r["ok"], "même relevé annoncé, mais les montants par titre ne recoupent pas le volume CDG"


# ── 2. Les titres échangés ─────────────────────────────────────────────────

def test_les_titres_echanges_exigent_les_memes_transactions():
    masi = {"asof": "2026-10-13", "transactions": 12, "titres_echanges": 4567}
    ok = _node(f"console.log(JSON.stringify(titresEchanges({json.dumps(BRIEF)},{json.dumps(masi)})))")
    assert ok == 4567
    masi["transactions"] = 13
    assert _node(f"console.log(JSON.stringify(titresEchanges({json.dumps(BRIEF)},{json.dumps(masi)})))") is None


# ── 3. Les tranches de l'histogramme ───────────────────────────────────────

def test_les_tranches_forment_une_partition():
    valeurs = [-9.99, -4.0, -3.99, -3.0, -2.5, -1.0, -0.99, -0.01, 0.0, 0.01, 0.99, 1.0, 2.0, 3.0, 3.99, 4.0, 9.99]
    res = _node(f"console.log(JSON.stringify({json.dumps(valeurs)}.map(x=>TRANCHES.filter(t=>t.t(x)).map(t=>t.id))))")
    for x, ids in zip(valeurs, res):
        assert len(ids) == 1, f"{x} tombe dans {ids}"
    assert res[valeurs.index(0.0)] == ["z"], "0,00 % doit être « inchangé », ni hausse ni baisse"


# ── 4. Le treemap ─────────────────────────────────────────────────────────

def test_le_treemap_conserve_les_surfaces_et_reste_dans_son_cadre():
    items = [{"nom": str(i), "v": v} for i, v in enumerate([51.7, 32.3, 12.4, 8.8, 3.6, 1.6, 1.5, .47, .44, .3, .18, .15, .15, .12, .08, .06, .04])]
    tuiles = _node(f"console.log(JSON.stringify(squarify({json.dumps(items)},0,0,900,340)))")
    assert len(tuiles) == len(items)
    total = sum(i["v"] for i in items)
    for t in tuiles:
        assert t["x"] >= -1e-6 and t["y"] >= -1e-6
        assert t["x"] + t["w"] <= 900 + 1e-6 and t["y"] + t["h"] <= 340 + 1e-6
        assert abs(t["w"] * t["h"] - t["v"] / total * 900 * 340) < 1e-3
    assert abs(sum(t["w"] * t["h"] for t in tuiles) - 900 * 340) < 1e-3


# ── 5. Les absences sont déclarées ─────────────────────────────────────────

def test_ce_qui_manque_est_declare():
    a = _node(f"console.log(JSON.stringify(absencesTableau({json.dumps(BRIEF)},[],null)))")
    texte = " ".join(a)
    assert "capitalisation" in texte
    assert "courbe intrajournalière" in texte, "seuls les repères du MASI sont publiés : il faut le dire"
    assert "titres échangés" in texte
    assert "par titre" in texte, "visuels par titre retirés sans le dire"
    assert "dépôts" in texte


def test_les_absences_rejoignent_ce_que_la_lecture_ne_dit_pas():
    i = SRC.index("const nonDit=")
    assert "absencesTableau(src,rows,masi)" in SRC[i:i + 200]
    j = SRC.index("Ce que cette lecture ne dit pas :")
    assert "nonDit.map(" in SRC[j:j + 400]


# ── 6. Câblage, filtre, dépendances ────────────────────────────────────────

def test_le_tableau_recoit_les_cours_et_le_masi():
    assert '<Briefing rows={rows} masi={masi} ouvrir=' in SRC
    assert "<SeanceDetail key=" in SRC and "rows={rows} masi={masi}" in SRC


def test_le_filtre_croise_se_voit_et_se_retire():
    i = SRC.index("const SeanceDetail=")
    corps = SRC[i:SRC.index("// ⚠️ « À SURVEILLER AUJOURD'HUI »", i)]
    assert "x&&x.type===f.type&&x.v===f.v?null:f" in corps, "un second clic doit réinitialiser"
    assert "filtre actif :" in corps and "onClick={()=>setFiltre(null)}" in corps
    assert 'e.key==="Escape"' in corps
    assert "aria-pressed" in corps


def test_chaque_panneau_porte_sa_source():
    i = SRC.index("const SeanceDetail=")
    corps = SRC[i:SRC.index("// ⚠️ « À SURVEILLER AUJOURD'HUI »", i)]
    panneaux = re.findall(r"<Panneau\b(.*?)>", corps, flags=re.S)
    assert len(panneaux) >= 7
    for p in panneaux:
        assert "source=" in p, f"panneau sans source : {p[:80]}"
    for k in re.findall(r"<Kpi\b(.*?)/>", corps, flags=re.S):
        assert "src=" in k, f"carte sans source : {k[:80]}"


def test_aucune_bibliotheque_ajoutee():
    assert len(re.findall(r"<script src=", SRC)) == 4
