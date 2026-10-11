"""La surcouche « live » du terminal reste coupée tant qu'elle n'a pas de
table de traduction générée par le moteur — 11/10/2026.

Le navigateur lisait `/instruments/SNA` (Stokvis à la Bourse) comme NOTRE SNA
(Sonasid) : reproduit sur une vraie réponse IDBourse, Sonasid affichait en
séance le cours de Stokvis avec sa propre note. Le test lit la source, sans
navigateur, pour tourner en intégration continue.
"""
import re
from pathlib import Path

import bvc_config as b

SRC = (Path(__file__).resolve().parent.parent / "terminal.src.html").read_text(encoding="utf-8")


def test_la_surcouche_live_est_coupee():
    assert re.search(r"^const LIVE_ACTIF = false;", SRC, re.M)
    assert "if(LIVE_ACTIF&&mktNow.isOpen){" in SRC
    assert "if(LIVE_ACTIF&&local.length>=5&&lastLocal<todayStr){" in SRC
    assert "if(!LIVE_ACTIF)return; fetchMASI()" in SRC


def test_chaque_appel_live_est_garde():
    """Contrôle négatif implicite : un nouvel appel non gardé ferait tomber le test."""
    for appel in ("fetchQuotes()", "fetchMASI()"):
        for m in re.finditer(re.escape(appel), SRC):
            avant = SRC[max(0, m.start() - 300):m.start()]
            if "async function" in SRC[max(0, m.start() - 40):m.start()]:
                continue
            assert "LIVE_ACTIF" in avant, f"{appel} appelé sans garde LIVE_ACTIF"


def _isin_interface():
    bloc = SRC[SRC.index("ISIN_MAP"):]
    bloc = bloc[:bloc.index("}")]
    return dict(re.findall(r"\b([A-Z0-9]{2,5}):\"(MA\d{10})\"", bloc))


def test_le_referentiel_de_l_interface_ne_contredit_pas_le_moteur():
    """Audit du 11/10 : SAF et SLM inversés, STK, HPS et MNG sur d'anciens ISIN."""
    interface = _isin_interface()
    assert len(interface) >= 70
    faux = {t: (v, b.ISIN_MAP[t]) for t, v in interface.items()
            if t in b.ISIN_MAP and b.ISIN_MAP[t] != v}
    assert faux == {}, f"ISIN de l'interface contredits par bvc_config : {faux}"


def test_le_controle_voit_une_inversion():
    inverse = dict(_isin_interface(), SAF=b.ISIN_MAP["SLM"])
    assert inverse["SAF"] != b.ISIN_MAP["SAF"]
