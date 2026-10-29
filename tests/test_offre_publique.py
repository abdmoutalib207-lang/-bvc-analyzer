"""Offres publiques établies sur pièce (registre OFFRES_PUBLIQUES, 29/10/2026).

CMT sortait n°1 du classement à ~3 800 DH alors qu'une OPA obligatoire à
2 217 DH allait s'ouvrir ; le fait ne paraissait que dans le fil d'actualités.

  · chaque offre porte ses pièces, présentes dans le dépôt, à l'empreinte
    annoncée, et chaque citation se relit à la page dite (R11, R12) ;
  · `_meta.offre_publique` la publie pour CMT seulement, None ailleurs, et
    disparaît après le règlement-livraison ;
  · AUCUN effet sur la note ni sur le signal : le registre n'est lu que pour
    `_meta` ;
  · le terminal (source ET compilation) affiche le bandeau et le marqueur ;
    le bulletin courriel porte la mention quand le titre est parmi les notes
    vertes. Aucun mot d'action.
"""
import hashlib
import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import bvc_config as C  # noqa: E402

SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
COMPILE = (RACINE / "index.html").read_text(encoding="utf-8")


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("’", "'")).strip()


def test_le_registre_porte_ses_pieces_a_l_empreinte_annoncee():
    assert set(C.OFFRES_PUBLIQUES) == {"CMT"}
    for t, o in C.OFFRES_PUBLIQUES.items():
        assert t in C.TICKERS_ALL, t
        assert o["ouverture"] <= o["cloture"] < o["resultats"] <= o["reglement_livraison"], t
        assert o["prix"] > 0 and o["titres_vises"] > 0 and o["initiateurs"] and o["visa"], t
        assert len(o["pieces"]) >= 1
        for p in o["pieces"]:
            f = RACINE / p["fichier"]
            assert f.exists(), f"pièce absente du dépôt : {p['fichier']}"
            assert hashlib.sha256(f.read_bytes()).hexdigest() == p["sha256"], p["fichier"]
            assert p["url"].startswith("https://")
            assert p["citations"]


def test_chaque_citation_se_relit_a_sa_page():
    pdfplumber = pytest.importorskip("pdfplumber")  # déclaré dans requirements.txt
    for o in C.OFFRES_PUBLIQUES.values():
        for p in o["pieces"]:
            with pdfplumber.open(RACINE / p["fichier"]) as pdf:
                for c in p["citations"]:
                    page = _norm(pdf.pages[c["page"] - 1].extract_text() or "")
                    assert _norm(c["texte"]) in page, (p["fichier"], c["page"], c["texte"])


def test_l_opa_cmt_telle_que_les_pieces_l_etablissent():
    o = C.OFFRES_PUBLIQUES["CMT"]
    assert o["prix"] == 2217.0
    # Le prix de l'offre est celui de la recevabilité du 15/09 (SUSPENSIONS).
    assert o["prix"] == C.SUSPENSIONS["CMT"][0]["reference_impliquee"]
    assert (o["ouverture"], o["cloture"]) == ("2026-11-03", "2026-11-17")
    assert (o["resultats"], o["reglement_livraison"]) == ("2026-11-26", "2026-12-01")
    assert o["titres_vises"] == 611898
    # 611 898 ÷ 1 681 233 actions (recevabilité du 15/09, section 1).
    assert round(o["titres_vises"] / 1681233 * 100, 2) == o["part_capital_pct"]
    assert o["visa"].startswith("VI/EM/032/2026") and o["avis_bourse"].startswith("AV-2026-134")


def test_phase_et_disparition_apres_reglement():
    f = C.offre_publique
    assert f("CMT", "2026-10-29")["phase"] == "a_venir"
    assert f("CMT", "2026-11-03")["phase"] == "ouverte"
    assert f("CMT", "2026-11-17")["phase"] == "ouverte"
    assert f("CMT", "2026-11-18")["phase"] == "close"
    assert f("CMT", "2026-12-01")["phase"] == "close"
    assert f("CMT", "2026-12-02") is None
    assert f("ATW", "2026-10-29") is None


def test_meta_publie_l_offre_pour_cmt_seulement(ud, monkeypatch):
    monkeypatch.setenv("BVC_DATE_ANALYSE", "2026-10-29")
    m = ud._meta_ticker("CMT", "cdg", "2026-10-28", {}, None)["offre_publique"]
    assert m["prix"] == 2217.0 and m["phase"] == "a_venir"
    assert m["source"].endswith("NI_CMT_OPA_032_2026.pdf") and m["pages"] == [1, 41, 80]
    for t in ("ATW", "SMI", "MNG"):
        assert ud._meta_ticker(t, "cdg", "2026-10-28", {}, None)["offre_publique"] is None


def test_aucun_effet_sur_la_note():
    # Le registre n'est lu que pour `_meta` : ni la note par métier, ni la
    # grille, ni la composition de la note dans le moteur.
    for f in ("pipeline/smart_money/fond_score_sectoriel.py", "pipeline/smart_money/fond_score.py",
              "pipeline/collect_financial_data.py"):
        txt = (RACINE / f).read_text(encoding="utf-8")
        assert "OFFRES_PUBLIQUES" not in txt and "offre_publique" not in txt, f
    # Dans le moteur, un seul appel, celui de `_meta`, et le registre brut
    # jamais lu (seul un commentaire le nomme).
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert src.count("offre_publique(") == 1
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "OFFRES_PUBLIQUES" not in code


def test_donnees_publiees_offre_sur_cmt_seulement(titres):
    """Famille « données publiées »."""
    # ⏳ À RETIRER APRÈS LE PREMIER RUN update_bvc SUIVANT LA FUSION (transition
    # du 29/10/2026) : un data.json antérieur ne porte la clé sur AUCUN titre.
    # Une publication partielle (une partie des titres seulement) échoue.
    if not any("offre_publique" in (x.get("_meta") or {}) for x in titres.values()):
        pytest.skip("⏳ À RETIRER APRÈS LE PREMIER RUN update_bvc SUIVANT LA FUSION — "
                    "data.json antérieur au registre OFFRES_PUBLIQUES")
    avec = sorted(s for s, x in titres.items() if (x.get("_meta") or {}).get("offre_publique"))
    assert avec in ([], ["CMT"]) and all("offre_publique" in (x.get("_meta") or {})
                                         for x in titres.values()), avec
    if C.offre_publique("CMT") is not None:
        assert avec == ["CMT"]


@pytest.mark.parametrize("page", [SRC, COMPILE], ids=["source", "compilation"])
def test_le_terminal_affiche_bandeau_et_marqueur(page):
    assert "bandeau-offre" in page and "marqueur-offre" in page
    assert "offre_publique" in page
    assert "écart avec le cours" in page


def test_le_texte_affiche_ne_porte_aucun_mot_d_action():
    i = SRC.index("const jjmmaaaa=")
    bloc = SRC[i:SRC.index("</div>);};", i)]
    for mot in ("vend", "achet", "apport", "conseil", "recommand"):
        assert mot not in bloc.lower(), mot


def _ligne_cmt(prix=3765.0, phase="a_venir"):
    o = dict(C.offre_publique("CMT", "2026-10-29"), phase=phase)
    return {"symbol": "CMT", "name": "Minière Touissit", "price": prix, "chg": -3.46,
            "v53": 7.69, "sig": "ACHETER ★★",
            "_meta": {"confidence": 5, "prix_asof": "2026-10-28", "stale": False,
                      "offre_publique": o}}


def test_le_bulletin_courriel_porte_la_mention():
    import bulletin_mail as B
    x = _ligne_cmt()
    m = B.mention_offre(x)
    assert m == ("Offre publique d'achat obligatoire à 2 217 DH, du 03/11 au 17/11/2026 "
                 "(visa AMMC VI/EM/032/2026 du 26/10/2026 ; avis de la Bourse "
                 "AV-2026-134 du 27/10/2026) — écart avec le cours : −41,1 %")
    autres = [dict(_ligne_cmt(), symbol=f"T{i}", _meta={"confidence": 5, "prix_asof": "2026-10-28",
                                                         "stale": False}) for i in range(40)]
    a = B.analyser({"masi": {}}, [x] + autres)
    assert m in B.texte(a) and "écart avec le cours : −41,1 %" in B.html(a)
    assert B.mention_offre(autres[0]) is None
    assert "close le 17/11/2026" in B.mention_offre(_ligne_cmt(phase="close"))
