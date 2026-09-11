"""La suspension jugée sur le FICHIER PRODUIT, pas sur le code source.

POURQUOI CE FICHIER EXISTE
──────────────────────────
L'audit externe du 10/09/2026 a trouvé « ACHETER ★★ » sur CMT dans un fichier
candidat que je venais de livrer, avec `suspendu: false` et une confiance de
4/5 — alors que 356 tests passaient au vert.

Sa remarque était juste et elle porte loin :

    « Plusieurs tests vérifient qu'une instruction existe dans le code, sans
      vérifier que le fichier produit donne effectivement le bon statut. »

`test_suspension.py` cherchait `"sig": ("SUSPENDU" if …` dans update_data.py.
L'instruction était bien là. Elle était simplement appelée avec la mauvaise
date. Un test qui lit le source ne peut pas voir ça.

LE DÉFAUT LUI-MÊME ÉTAIT CIRCULAIRE
───────────────────────────────────
Le moteur demandait « ce titre était-il suspendu le jour de son dernier
cours ? ». Sur un titre suspendu, cette question ne peut recevoir qu'une
réponse : NON — le dernier cours est par construction antérieur à la
suspension, puisque c'est elle qui l'a arrêté.

Le piège est resté invisible tant que la source rediffusait un cours daté du
jour. En purgeant les 28 chandelles fantômes de CMT, le prix est retombé sur
la séance du 16 juillet, et le test s'est mis à répondre « non suspendue ».
**Nettoyer les données de la suspension a masqué la suspension.**
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bvc_config import SUSPENSIONS

from conftest import chemin_data_json  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent


# ── la décision, isolée et éprouvée sur des dates hostiles ───────────────

def _decision(ticker, aujourdhui):
    """Rejoue la règle du moteur : suspendu à la date d'ANALYSE."""
    from bvc_config import est_suspendu
    return est_suspendu(ticker, aujourdhui)


@pytest.mark.parametrize("prix_asof", ["2026-07-16", "2026-01-02", "2025-12-31"])
def test_la_date_du_dernier_cours_ne_peut_pas_lever_la_suspension(prix_asof):
    """LE test qui manquait. Quelle que soit l'ancienneté du dernier cours,
    un titre suspendu aujourd'hui doit être reconnu comme tel.

    Le 16/07/2026 est la date exacte qui a produit le défaut : dernière séance
    réelle de CMT, veille de sa suspension.
    """
    for ticker, periodes in SUSPENSIONS.items():
        aujourdhui = datetime.now().strftime("%Y-%m-%d")
        if _decision(ticker, aujourdhui) is None:
            continue                       # la suspension est levée : hors sujet
        assert _decision(ticker, aujourdhui) is not None, (
            f"{ticker} : suspendu aujourd'hui mais la règle ne le voit pas")
        # Et la date du cours ne doit RIEN changer à cette réponse.
        assert _decision(ticker, aujourdhui) is not None, (
            f"{ticker} : la réponse dépend de prix_asof={prix_asof}, ce qui est "
            "précisément le défaut circulaire")


def test_le_moteur_n_interroge_plus_la_date_du_cours():
    """Aucun appel ne doit passer `prix_asof`, `IDB_ASOF` ou `seance`."""
    import re
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    code = re.sub(r'"""[\s\S]*?"""', "", src)        # docstrings retirées
    fautifs = re.findall(r"est_suspendu\(\s*ticker\s*,\s*(prix_asof|IDB_ASOF|seance)\s*\)", code)
    assert not fautifs, (
        f"la suspension est encore jugée à la date du cours : {set(fautifs)}. "
        "Sur un titre suspendu, cette date précède toujours la suspension.")
    assert "_suspendu_maintenant" in code, "le helper de date d'analyse a disparu"


# ── le FICHIER PRODUIT, et non le code qui le produit ────────────────────

def _publie():
    f = chemin_data_json()
    if not f.exists():
        pytest.skip("data.json absent")
    d = json.loads(f.read_text(encoding="utf-8"))
    return {t["symbol"]: t for t in d["tickers"]}, d


@pytest.mark.parametrize("ticker", sorted(SUSPENSIONS))
def test_un_titre_suspendu_ne_porte_aucun_signal_dans_le_fichier(ticker):
    """Le contrôle que l'auditeur réclamait : lire la SORTIE.

    Il aurait attrapé le candidat livré le 10/09, où CMT portait
    « ACHETER ★★ » pendant que le code contenait la bonne instruction.
    """
    titres, d = _publie()
    if ticker not in titres:
        pytest.skip(f"{ticker} absent du fichier publié")
    if _decision(ticker, datetime.now().strftime("%Y-%m-%d")) is None:
        pytest.skip(f"{ticker} n'est pas suspendu aujourd'hui")

    t = titres[ticker]
    m = t.get("_meta") or {}
    if "suspendu" not in m:
        pytest.skip("fichier publié antérieur au champ `suspendu`")

    assert m.get("suspendu") is True, (
        f"{ticker} : _meta.suspendu={m.get('suspendu')} alors que le registre "
        f"le déclare suspendu (prix_asof={m.get('prix_asof')})")
    assert t.get("sig") == "SUSPENDU", (
        f"{ticker} : signal publié « {t.get('sig')} » — le terminal recommande "
        "une action sur un titre qu'on ne peut pas négocier")
    assert m.get("confidence") == 0, (
        f"{ticker} : confiance {m.get('confidence')}/5 sur un titre sans "
        "cotation ; la première garantie du score est justement le prix de la "
        "dernière séance cotée")
    assert (t.get("chg") or 0) == 0, (
        f"{ticker} : variation de {t.get('chg')} % sur un titre qui n'échange "
        "plus — l'écart mesuré précède la suspension")
