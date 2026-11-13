"""En-tête de fiche : l'essentiel AVANT le Score BVC (13/11/2026).

Audit externe du 12/11/2026 : « le gros score coloré attire l'œil avant la
date du cours, le montant échangé et la réserve principale. Je mettrais ces
trois informations en haut de chaque fiche. »

Ce qui est vérifié :
1. dans la fiche, l'en-tête vient après la ligne du cours et AVANT le score ;
2. il rend, dans l'ordre, la date, le montant, la réserve — lus tels que le
   moteur les publie (`_meta.prix_asof`, `echange_dh`, réserves publiées) ;
3. la réserve unique suit l'ordre convenu, exécutée sous node ;
4. le score n'a pas bougé (taille, couleur) et aucun mot d'action n'entre.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def _bloc(src: str, debut: str) -> str:
    i = src.index(debut)
    j = src.index("{", i)
    p = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            p += 1
        elif src[k] == "}":
            p -= 1
            if p == 0:
                return src[i:k + 1]
    raise AssertionError(f"accolade non refermée après {debut!r}")


def _composant(nom: str) -> str:
    """Corps d'un composant fléché `const Nom=(...)=>{ ... };`."""
    # L'accolade des paramètres déstructurés (`({r,seance})`) n'ouvre pas le
    # corps : on part de celle qui suit `=>`.
    i = SRC.index(f"const {nom}=")
    j = SRC.index("=>{", i) + 2
    return SRC[i:j] + _bloc(SRC[j:], "{")


DETAIL = SRC[SRC.index("const Detail=({rows,sel,setSel"):]
DETAIL = DETAIL[:DETAIL.index("\n// ──", 10)] if "\n// ──" in DETAIL[10:] else DETAIL
EN_TETE = _composant("EnTeteEssentiel")


# ── 1. place dans la fiche ───────────────────────────────────────────────────

def test_en_tete_entre_le_cours_et_le_score():
    cours = DETAIL.index('className="fiche-cours"')
    en_tete = DETAIL.index("<EnTeteEssentiel ")
    score = DETAIL.index('className="score-bvc-tete"')
    assert cours < en_tete < score
    # une seule fois, et par titre (son état « lire en entier » ne survit
    # pas à un changement de titre)
    assert DETAIL.count("<EnTeteEssentiel ") == 1
    assert "<EnTeteEssentiel key={sym} r={r} seance={seance}/>" in DETAIL


def test_la_derniere_seance_vient_des_dates_publiees():
    assert "const seance=useMemo(()=>rows.reduce(" in DETAIL
    assert "meta(x).asof" in DETAIL


# ── 2. les trois éléments, dans l'ordre ──────────────────────────────────────

def test_trois_elements_dans_l_ordre():
    i_date = EN_TETE.index('data-essentiel="date"')
    i_montant = EN_TETE.index('data-essentiel="montant"')
    i_reserve = EN_TETE.index('data-essentiel="reserve"')
    assert i_date < i_montant < i_reserve


def test_date_du_cours_et_pastille_reutilisee():
    assert "m.asof" in EN_TETE and "cours du {jjmmaaaa(m.asof)}" in EN_TETE
    # cours ancien : la pastille ⚠ JJ/MM existante, pas une nouvelle
    assert '<Perime r={r} force prefixe="cours du "' in EN_TETE
    assert "const ancien=m.stale||(!!m.asof&&!!seance&&m.asof<seance);" in EN_TETE
    # Perime sans props garde son comportement d'avant : seulement si stale
    assert "if(!m.stale&&!force)return null;" in _composant("Perime")


def test_montant_publie_sinon_non_echange():
    assert "r.echange_dh" in EN_TETE
    assert "non échangé ce jour" in EN_TETE
    assert "montantEntier(dh)" in EN_TETE
    # rien n'est reconstitué : ni cours × volume, ni médiane
    assert "r.vol" not in EN_TETE and "echange_median_dh" not in EN_TETE


def test_reserve_longue_lisible_au_toucher():
    assert 'aria-expanded={ouvert}' in EN_TETE and "title={res.texte}" in EN_TETE
    assert "minHeight:44" in EN_TETE                  # cible tactile
    assert "WebkitLineClamp:2" in EN_TETE             # tronquée proprement


# ── 3. la réserve unique, exécutée ───────────────────────────────────────────

def _reserves(rows):
    node = shutil.which("node")
    if not node:                                    # pragma: no cover
        pytest.skip("node absent de cette machine")
    meta = _bloc(SRC, "const meta=r=>")
    rp = _bloc(SRC, "const reservePrincipale=r=>")
    res = _bloc(SRC, "const reserveEnTete=r=>")
    jj = SRC[SRC.index("const jjmm=d=>"):].split("\n", 1)[0]
    script = (jj + "\n" + meta + ";\n" + rp + ";\n"
              + res + ";\nconsole.log(JSON.stringify(%s.map(reserveEnTete)));"
              % json.dumps(rows))
    r = subprocess.run([node, "-"], input=script, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_ordre_des_reserves():
    pb, bpa = "fonds propres sans la levée", "BPA sur le nombre d'actions actuel"
    rows = [
        {"_meta": {"confidence": 0, "suspendu": True, "pb_reserve": pb}, "bpa_reserve": bpa},
        {"_meta": {"confidence": 1, "pb_reserve": pb}, "bpa_reserve": bpa},
        {"_meta": {"confidence": 4, "pb_reserve": pb}, "bpa_reserve": bpa},
        {"_meta": {"confidence": 4}, "bpa_reserve": bpa},
        {"_meta": {"confidence": 4}, "score_bvc": {"facteurs": {"moyennes_mobiles": {"rupture":
            {"reprise": "2026-09-16", "seances": 40, "moyennes": ["MM50", "MM200"]}}}}},
        {"_meta": {"confidence": 5}, "score_bvc": {"facteurs": {"moyennes_mobiles": {"points": 35}}}},
        {},                                            # sans _meta : confiance 0
    ]
    out = _reserves(rows)
    assert out[0]["texte"] == "Cotation suspendue"   # avant la confiance (règle du 24/09)
    assert out[1]["texte"] == "Données insuffisantes" and out[1]["c"] == "#8892a4"   # gris
    assert out[2]["texte"] == pb and out[2]["sur"] == "le P/B"
    assert out[3]["texte"] == bpa and out[3]["sur"] == "le BPA"
    assert out[4]["texte"].startswith("MM50, MM200 incluent des cours d'avant la reprise du 16/09/2026")
    assert out[5] is None                              # rien : on n'invente pas
    assert out[6]["texte"] == "Données insuffisantes"


# ── 4. le score inchangé, aucun mot d'action ─────────────────────────────────

def test_le_score_n_a_pas_change():
    tete = DETAIL[DETAIL.index('className="score-bvc-tete"'):]
    tete = tete[:tete.index("{exactBVC(vBVC)}")]
    assert "fontSize:52" in tete and "color:couleurChiffre(r)" in tete


def test_aucun_mot_d_action():
    texte = (EN_TETE + _bloc(SRC, "const reserveEnTete=r=>")).lower()
    for mot in ("acheter", "achat", "vendre", "vente", "éviter", "surveiller", "conserver", "renforcer"):
        assert not re.search(rf"\b{mot}\b", texte), mot


def test_une_seule_reserve_principale_sur_la_fiche():
    """13/11/2026 : l'en-tête et la ligne « Réserve principale » sous le score
    suivaient deux règles et pouvaient se contredire (T2S). L'en-tête est la
    seule ; il reprend `reservePrincipale` à défaut des réserves précédentes."""
    assert "Réserve principale : <span" not in SRC
    corps = SRC[SRC.index("const reserveEnTete="):SRC.index("const EnTeteEssentiel=")]
    assert "reservePrincipale(r)" in corps
    assert "incluent des cours d'avant la reprise du" in corps


def test_a_defaut_la_reserve_principale_de_la_note():
    rows = [{"_meta": {"confidence": 4, "comptes_absents": {"dernier_depot": "2023-06-30"}}},
            {"_meta": {"confidence": 4, "stale": True, "prix_asof": "2026-09-28"}}]
    out = _reserves(rows)
    assert out[0]["texte"] == "Aucuns comptes publiés récents"
    assert out[1] is None            # le cours ancien est dit par la pastille de la date, pas répété

