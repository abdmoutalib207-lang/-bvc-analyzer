"""Passage d'un titre à l'autre DANS la fiche (14/10/2026, diagnostic externe) :
la légende affichait « ATW · O 4 180 … C 4 050 » — les cours de CMT — le
temps du chargement. Reproduit en navigateur avant correction, absent après."""
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")


def test_la_serie_retient_son_titre():
    assert 'const etat=serieDe===sym+"|"+period?etatBrut:"chargement";' in SRC
    assert SRC.count('setSerieDe(sym+"|"+period)') == 3
    # déclarée APRÈS `sym` : sinon « Cannot access 'sym' before initialization »
    assert SRC.index("const sym=r.symbol||r.ticker;") < SRC.index("const etat=serieDe===")


def test_la_legende_est_videe_avant_dessin():
    assert "if(refTooltip.current)refTooltip.current.innerHTML=\"\";" in SRC


def test_les_actualites_sont_videes_au_changement():
    assert "let vivant=true;setArticles([]);setOk(false);" in SRC
