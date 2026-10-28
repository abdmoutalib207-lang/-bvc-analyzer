"""Fiche lisible (14/10/2026) : l'explication affichée ne lit QUE ce que le
moteur publie, et le détail de la confiance recoupe son total."""
import json
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def test_les_replis_sont_au_toucher_et_dans_la_fiche():
    for x in ("<PourquoiNote r={r}/>", "<DetailConfiance r={r}/>", "heureCours(r)", "<details className=\"repli\""):
        assert x in SRC, x
    assert "note_fond:t.note_fond" in SRC          # le champ traverse la fusion


def test_les_garanties_recoupent_la_confiance():
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    t = d["tickers"]
    t = t if isinstance(t, list) else list(t.values())
    avec = [x for x in t if isinstance((x.get("_meta") or {}).get("garanties"), list)]
    if not avec:
        pytest.skip("data.json produit avant la publication des garanties")
    for x in avec:
        m = x["_meta"]
        assert len(m["garanties"]) == 5
        # Les plafonds (sans comptes, ISIN, note incalculable, liquidité) ne
        # peuvent que BAISSER la confiance sous le nombre de garanties remplies.
        assert m["confidence"] <= sum(g["ok"] for g in m["garanties"]), x.get("symbol")


def test_les_ratios_ont_un_info_au_toucher():
    # grille principale + comptes publiés + ROE DATA+ « sans objet » (22/10/2026 :
    # la raison de l'écart, lue dans note_fond_metier, doit se lire au toucher).
    assert SRC.count("<InfoCellule texte=") == 3
    assert 'cursor:"help"}}>\n                  <div style={{fontSize:8' not in SRC
    for champ in ("bpa_12m:t.bpa_12m", "div_dh:t.div_dh"):  # l'explication lit des champs fusionnés
        assert champ in SRC, champ


def test_favoris_changements_sur_donnees_chargees():
    assert "<ChangementsFavoris rows={rows} fav={fav}" in SRC
    # l'instantané n'est pris que sur les données chargées (avec _meta)
    assert "const charges=suivis.length>0&&suivis.every(r=>r._meta);" in SRC
    assert '},[charges,cle]);' in SRC


def test_sous_la_note_couverture_reserve_liquidite():
    assert "<ResumeNote r={r}/>" in SRC
    assert "du poids de la grille" in SRC              # pas « des critères »
    assert "Fiabilité des données" in SRC
    assert 'titre="Confiance' not in SRC and "`Confiance ${" not in SRC


def test_essais_et_indicateurs_geles_replies_en_analyse_avancee():
    i = SRC.index('<details className="avance carte"')
    j = SRC.index("</details>", i)
    assert "<SignauxTechniques r={r}/>" in SRC[i:j]
    # 28/10/2026 : la carte NLP gelée est retirée avec le corpus.
    assert "{/* NLP */}" not in SRC and "Smart Sentiment" not in SRC
    assert '<Repli titre="Analyse avancée — note par métier' in SRC
