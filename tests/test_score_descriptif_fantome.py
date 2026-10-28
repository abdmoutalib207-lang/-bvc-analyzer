"""Score descriptif en MODE FANTÔME (R8) — 28/10/2026.

Le score est publié À CÔTÉ de la note ; il ne la nourrit pas. Ce fichier garde le
branchement :
  · `annexer` ne modifie AUCUN autre champ (v53, sig, confiance, ordre) et
    s'applique tout ou rien ;
  · aucun autre module ne le lit ; le moteur ne le mentionne qu'une fois, après
    la note par famille ;
  · le data.json publié porte le bloc sur chaque titre, cohérent avec les
    chandelles (famille « données publiées » : si le fichier précède le code,
    le contrôle est ignoré EN LE DISANT, jamais en silence).
La preuve complète — deux essais à blanc simultanés, sur l'arbre d'origine et
sur la branche, 0 différence hors horodatages sur 80 titres — n'est pas rejouable
hors réseau : elle est consignée dans le message du commit.
"""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from pipeline import score_descriptif as sd  # noqa: E402


def _bougies_reelles(t):
    f = RACINE / "pipeline" / "candles" / f"{t}.json"
    return json.loads(f.read_text(encoding="utf-8"))


def _titre(**meta):
    """Un titre minimal, 60 séances échangées, cours au-dessus de ses moyennes."""
    bougies = [{"d": f"2026-{(i // 28) + 7:02d}-{(i % 28) + 1:02d}", "o": 100 + i, "h": 100 + i,
                "l": 100 + i, "c": 100.0 + i, "v": 5000.0 + i} for i in range(60)]
    last = bougies[-1]
    rec = {"symbol": "ZZZ", "price": last["c"], "ma20": 150.0, "ma50": 135.0, "rsi": 60.0,
           "_meta": {"stale": False, "suspendu": False, "prix_asof": last["d"], **meta},
           "ratios_publies": {"roe_2025": {"valeur": 14.0}}}
    return rec, bougies


# ── 5. MODE FANTÔME ─────────────────────────────────────────────────────────

def test_annexer_ne_modifie_aucun_autre_champ(titres):
    """v53, sig, confiance, ordre : identiques avec ou sans le bloc."""
    liste = [copy.deepcopy(t) for t in titres.values()]
    for t in liste:
        t.pop("score_descriptif", None)
    avant = copy.deepcopy(liste)
    sd.annexer(liste, lambda s: _bougies_reelles(s) if (RACINE / "pipeline" / "candles" / f"{s}.json").exists() else [])
    assert [t["symbol"] for t in liste] == [t["symbol"] for t in avant]
    for a, b in zip(avant, liste):
        assert "score_descriptif" in b
        b = {k: v for k, v in b.items() if k != "score_descriptif"}
        assert b == a, a["symbol"]
        assert b.get("v53") == a.get("v53") and b.get("sig") == a.get("sig")
        assert (b.get("_meta") or {}).get("confidence") == (a.get("_meta") or {}).get("confidence")


def test_annexer_tout_ou_rien():
    rec1, b1 = _titre()
    rec2, _ = _titre()
    rec2["symbol"] = "YYY"
    liste = [rec1, rec2]
    avant = copy.deepcopy(liste)

    def bougies_de(s):
        if s == "YYY":
            raise RuntimeError("source illisible")
        return b1

    with pytest.raises(RuntimeError):
        sd.annexer(liste, bougies_de)
    assert liste == avant, "un titre a été modifié alors que le calcul a échoué"


def test_aucun_autre_module_ne_lit_le_score_descriptif():
    """R8 : le score fantôme n'alimente ni la note, ni le signal, ni la confiance, ni le bulletin."""
    autorises = {"score_descriptif.py", "backtest_score_descriptif.py"}
    lecteurs = []
    for p in sorted((RACINE / "pipeline").rglob("*.py")):
        if p.name in autorises:
            continue
        if "score_descriptif" in re.sub(r"#.*", "", p.read_text(encoding="utf-8")):
            lecteurs.append(str(p.relative_to(RACINE)))
    assert not lecteurs, f"modules qui lisent le score descriptif : {lecteurs}"


def test_dans_le_moteur_le_bloc_est_unique_et_apres_la_note():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    code = re.sub(r"#.*", "", src)
    assert len(re.findall(r"score_descriptif", code)) == 1, \
        "le moteur ne doit mentionner le score descriptif qu'à son import"
    assert src.index("note_metier_du_run(tickers_out, passe1") < src.index("_sd_annexer(")
    # jamais une entrée de la note : ni compute_v53, ni _signal_publie, ni la confiance
    for fonction in ("def compute_v53", "def _signal_publie", "def _meta_ticker"):
        i = src.find(fonction)
        if i >= 0:
            corps = src[i:i + 12000]
            suivant = re.search(r"\n(?:def |class )", corps[len(fonction):])
            corps = corps[:len(fonction) + suivant.start()] if suivant else corps
            assert "score_descriptif" not in corps, fonction


# ── publié : le fichier data.json ───────────────────────────────────────────

ETATS = {"CALCULABLE", "PARTIEL", "NON_CALCULABLE"}


def test_publie_chaque_titre_porte_le_bloc(titres):
    porteurs = [s for s, t in titres.items() if "score_descriptif" in t]
    if not porteurs:
        pytest.skip("`score_descriptif` absent de TOUS les titres : le data.json publié est "
                    "antérieur au code qui l'émet. Le contrôle reprendra au premier passage du moteur.")
    assert len(porteurs) == len(titres), f"titres sans bloc : {sorted(set(titres) - set(porteurs))}"
    for s, t in titres.items():
        b = t["score_descriptif"]
        assert set(b) >= {"valeur", "etat", "couverture_pct", "version", "facteurs"}, s
        assert b["etat"] in ETATS and b["version"] == sd.VERSION, s
        if b["valeur"] is not None:
            assert b["etat"] == "CALCULABLE" and 0 <= b["valeur"] <= 100 and b["couverture_pct"] >= 70, s
        if b["etat"] == "CALCULABLE":
            assert b["valeur"] is not None and b["couverture_pct"] >= 70, s
        else:
            assert b["valeur"] is None, s
        meta = t.get("_meta") or {}
        if meta.get("stale", True) or meta.get("suspendu"):
            assert b["etat"] == "NON_CALCULABLE", f"{s} : cours périmé ou suspendu mais noté"
        # la somme des poids couverts est la couverture
        couverts = [f["poids"] for f in b["facteurs"].values() if f["points"] is not None]
        assert sum(couverts) == b["couverture_pct"], s


def test_publie_le_bloc_est_recalculable_depuis_les_chandelles(titres):
    """Les entrées du score (cours, MM, RSI) et les chandelles disent la même chose."""
    porteurs = [t for t in titres.values() if "score_descriptif" in t]
    if not porteurs:
        pytest.skip("data.json antérieur au code qui émet `score_descriptif`.")
    verifies = 0
    for t in porteurs:
        f = RACINE / "pipeline" / "candles" / f"{t['symbol']}.json"
        if not f.exists():
            continue
        b = json.loads(f.read_text(encoding="utf-8"))
        if not b or b[-1]["d"] != (t.get("_meta") or {}).get("prix_asof") or b[-1]["c"] != t.get("price"):
            continue          # chandelles et data.json d'un autre passage : rien à comparer
        rec = {k: v for k, v in t.items() if k != "score_descriptif"}
        assert sd.score_titre(rec, b) == t["score_descriptif"], t["symbol"]
        verifies += 1
    assert verifies >= 20, f"seulement {verifies} titres comparables"
