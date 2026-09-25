#!/usr/bin/env python3
"""Le briefing constate. Il n'explique pas, et il ne doit jamais s'y mettre.

⚠️ CE QUE CES TESTS DÉFENDENT
─────────────────────────────
Un briefing quotidien dérive naturellement vers le récit. « Le marché a reculé
sur fond d'incertitude politique » se lit mieux que « 42 valeurs sur 68 ont
baissé » — et c'est exactement ce qui le rend dangereux : la phrase agréable
est celle qu'aucune donnée du dépôt ne permet d'écrire.

Le lecteur peut vérifier « 42 sur 68 ». Il ne peut pas vérifier « sur fond
d'incertitude ». Et c'est sur l'invérifiable qu'il fondera sa décision.

⚠️ LE DÉFAUT QUE LA LARGEUR DE MARCHÉ CORRIGE
La variation de l'indice, seule, se trompe régulièrement de sens : le MASI est
pondéré par les capitalisations, donc trois poids lourds suffisent à le porter
pendant que la majorité des valeurs recule. Un lecteur qui n'a que « +0,4 % »
conclut alors l'inverse de ce qui s'est passé.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import briefing as bf  # noqa: E402


def _flux(masi=None, tickers=None):
    return {"masi": masi or {}, "tickers": tickers or []}


def _t(sym="ADH", asof="2026-09-24", **kw):
    d = {"symbol": sym, "name": sym, "price": 100.0, "chg": 0.0, "vol": 100,
         "_meta": {"prix_asof": asof, "vol_median20": 100, "n_candles": 400}}
    for k, v in kw.items():
        if k in ("vol_median20", "n_candles"):
            d["_meta"][k] = v
        else:
            d[k] = v
    return d


# ── ⚠️ LA RÈGLE CENTRALE : AUCUNE CAUSE ────────────────────────────────────

MOTS_DE_CAUSE = (
    " parce que", " en raison de", " à cause de", " sur fond de", " dû à",
    " s'explique par", " porté par l'", " sous l'effet de", " grâce à",
)


def test_aucun_constat_n_avance_de_cause():
    """⚠️ LE TEST QUI JUSTIFIE LE MODULE.

    Le jour où quelqu'un ajoutera « le marché recule sur fond de… », ce test
    l'arrêtera. Aucune donnée de ce dépôt n'établit une cause : nous mesurons
    des cours et des volumes.
    """
    b = bf.composer(json.loads((RACINE / "data.json").read_text(encoding="utf-8")))
    for c in b["constats"]:
        for mot in MOTS_DE_CAUSE:
            assert mot not in c.lower(), (
                f"un constat avance une cause — « {mot.strip()} » dans : {c}")


def test_le_briefing_dit_lui_meme_qu_il_n_explique_pas():
    """Une limite écrite dans la documentation n'est pas lue. Écrite dans le
    produit, elle l'est."""
    b = bf.composer(_flux())
    assert any("cause" in x.lower() for x in b["non_mesurable"]), (
        "le briefing ne prévient pas qu'il ne mesure pas de causes")


# ── ⚠️ Le désaccord entre l'indice et le marché ────────────────────────────

def test_un_indice_qui_monte_pendant_que_le_marche_baisse_est_signale():
    """⚠️ LE CAS DANGEREUX, et la raison d'être de la largeur.

    Attendu écrit à la main : 10 hausses, 50 baisses, 8 inchangés → le marché
    baisse nettement. Un indice à +0,40 % le contredit, et il faut le dire.
    """
    a = bf.accord_indice_marche(
        {"change_pct": 0.40, "hausses": 10, "baisses": 50, "inchanges": 8})
    assert a["sens_indice"] == "hausse" and a["sens_marche"] == "baisse"
    assert a["accord"] is False
    b = bf.composer(_flux({"change_pct": 0.40, "hausses": 10, "baisses": 50,
                           "inchanges": 8}))
    assert any("ne disent pas la même chose" in c for c in b["constats"])


def test_une_seance_concordante_n_est_pas_signalee_comme_un_desaccord():
    a = bf.accord_indice_marche(
        {"change_pct": -0.95, "hausses": 16, "baisses": 42, "inchanges": 10})
    assert a["accord"] is True and a["sens_marche"] == "baisse"


def test_les_inchanges_comptent_au_denominateur():
    """⚠️ Un marché où rien ne bouge n'est pas un marché haussier. Les exclure
    gonflerait le ratio des séances calmes — celles où l'on se trompe le plus.

    Attendu à la main : (10 − 8) / (10 + 8 + 82) = 2/100 = 0,02.
    """
    lg = bf.largeur({"hausses": 10, "baisses": 8, "inchanges": 82})
    assert lg["total"] == 100
    assert lg["ratio"] == 0.02


def test_une_largeur_absente_rend_none_et_est_declaree():
    assert bf.largeur({"change_pct": -1.0}) is None
    b = bf.composer(_flux({"change_pct": -1.0}))
    assert any("largeur" in x for x in b["non_mesurable"])


# ── ⚠️ Les volumes : comparés à soi, jamais au marché ──────────────────────

def test_le_volume_est_compare_a_la_mediane_du_titre():
    """⚠️ Mille titres est considérable pour Zellidja et négligeable pour
    Attijariwafa. Le seul repère qui vaille est le titre lui-même."""
    v = bf.volumes_inhabituels(
        [_t("AAA", vol=1000, vol_median20=100),     # 10× → retenu
         _t("BBB", vol=1000, vol_median20=900)],    # 1,1× → ordinaire
        "2026-09-24")
    assert [x["symbol"] for x in v] == ["AAA"]
    assert v[0]["facteur"] == 10.0


def test_un_titre_sans_mediane_est_ecarte_et_non_repute_calme():
    """⚠️ « On ne sait pas » coûte moins cher que de l'affirmer."""
    assert bf.volumes_inhabituels(
        [_t("AAA", vol=99999, vol_median20=None)], "2026-09-24") == []


def test_un_titre_d_une_autre_seance_est_ecarte():
    assert bf.volumes_inhabituels(
        [_t("AAA", asof="2026-09-23", vol=1000, vol_median20=10)],
        "2026-09-24") == []


# ── ⚠️ Les extrêmes annuels ────────────────────────────────────────────────

def test_un_titre_a_serie_courte_n_est_pas_dit_au_plus_haut_annuel():
    """⚠️ Un titre introduit il y a deux mois est à son « plus haut annuel »
    PAR CONSTRUCTION. L'annoncer serait un artefact de la longueur de sa
    série, pas un fait de marché."""
    e = bf.extremes_annuels(
        [_t("NEW", price=100.0, h52w=100.0, n_candles=40)], "2026-09-24")
    assert e["plus_hauts"] == []


def test_un_titre_a_serie_longue_au_plus_haut_est_signale():
    e = bf.extremes_annuels(
        [_t("OLD", price=100.0, h52w=100.0, n_candles=400)], "2026-09-24")
    assert [x["symbol"] for x in e["plus_hauts"]] == ["OLD"]


# ── ⚠️ La concentration, en dirhams ────────────────────────────────────────

def test_la_concentration_se_mesure_en_dirhams_pas_en_titres():
    """⚠️ Dix titres de Minière Touissit valent 35 670 DH, dix d'Addoha en
    valent 370. Compter les titres désignerait les valeurs bon marché.

    Attendu à la main : un titre à 1 000 DH échangé 1 000 fois pèse 1 M DH ;
    cinq titres à 1 DH échangés 1 000 fois pèsent 1 000 DH chacun. Le premier
    doit dominer malgré un volume identique.
    """
    t = [_t("CHER", price=1000.0, vol=1000)] + \
        [_t(f"BAS{i}", price=1.0, vol=1000) for i in range(5)]
    c = bf.concentration(t, "2026-09-24")
    assert c["titres"][0]["symbol"] == "CHER"
    assert c["titres"][0]["montant_dh"] == 1_000_000


def test_la_concentration_exige_au_moins_cinq_titres_actifs():
    """Une « part des cinq premiers » sur trois titres ne veut rien dire."""
    assert bf.concentration([_t("A"), _t("B")], "2026-09-24") is None


# ── Le rendu ───────────────────────────────────────────────────────────────

def test_le_texte_porte_les_nombres_et_non_des_qualificatifs():
    """Un constat sans son nombre est une opinion."""
    txt = bf.texte(bf.composer(json.loads(
        (RACINE / "data.json").read_text(encoding="utf-8"))))
    assert any(ch.isdigit() for ch in txt)
    assert "LECTURE DE LA SÉANCE" in txt


def test_les_nombres_sont_ecrits_a_la_francaise():
    """⚠️ Le reste du bulletin écrit « -0,95 % ». Un « -0.95 % » au milieu se
    lit comme une donnée venue d'ailleurs."""
    assert bf._fr(-0.95) == "-0,95"
    assert bf._fr(1234.5, 1) == "1 234,5"


def test_pas_de_parenthese_de_pluriel():
    """« 1 valeur(s) » signale que personne n'a relu la phrase."""
    assert bf._pluriel(1, "valeur") == "1 valeur"
    assert bf._pluriel(2, "valeur") == "2 valeurs"
    txt = bf.texte(bf.composer(json.loads(
        (RACINE / "data.json").read_text(encoding="utf-8"))))
    assert "(s)" not in txt


def test_un_flux_vide_ne_fait_pas_lever():
    """⚠️ Le briefing ne doit jamais empêcher l'envoi du bulletin."""
    b = bf.composer({})
    assert isinstance(b["constats"], list)
    assert bf.texte(b)


# ── ⚠️ Les actualités : des publications, jamais des causes ────────────────

def _art(titre="T", date="2026-09-24", material=True, tickers=("CSR",),
         importance=80, tier="S1", type_="resultats"):
    return {"title": titre, "date": date, "material": material,
            "tickers": list(tickers), "importance": importance,
            "source_tier": tier, "event_type": type_,
            "publisher": "AMMC", "url": "https://exemple.ma/a"}


def test_le_briefing_ne_definit_pas_son_propre_seuil_de_materialite():
    """⚠️ LE DÉFAUT QUE CE TEST EMPÊCHE DE REVENIR.

    Une première version portait `IMPORTANCE_MIN = 65`, fixé après mesure de
    la distribution. Vérification faite, `enrich_news.py:192` calcule déjà
    `material = score >= 65` : les deux désignaient EXACTEMENT les mêmes
    73 articles sur 300.

    C'était une seconde définition du mot « important », posée à côté de celle
    du collecteur. Deux définitions qui concordent aujourd'hui divergeront le
    jour où l'une bougera, et personne ne saura laquelle fait foi.

    Lu par l'AST : le fichier CITE le seuil dans ses commentaires pour
    expliquer pourquoi il a disparu.
    """
    import ast
    arbre = ast.parse((RACINE / "pipeline" / "briefing.py").read_text(encoding="utf-8"))
    noms = {t.id for n in ast.walk(arbre) if isinstance(n, ast.Assign)
            for t in n.targets if isinstance(t, ast.Name)}
    assert "IMPORTANCE_MIN" not in noms, (
        "le briefing redéfinit un seuil d'importance — c'est le travail du "
        "collecteur, et deux définitions finiront par diverger")


def test_la_selection_suit_le_drapeau_du_collecteur():
    a = bf.actualites([_art("retenu", material=True),
                       _art("écarté", material=False)], "2026-09-24")
    assert [x["titre"] for x in a["titres"]] == ["retenu"]


def test_la_fenetre_couvre_le_week_end():
    """⚠️ Le lundi matin, le briefing doit reprendre ce qui a été publié
    samedi et dimanche. Une fenêtre d'un jour les perdrait chaque semaine."""
    a = bf.actualites([_art("vendredi", date="2026-09-22"),
                       _art("samedi", date="2026-09-23"),
                       _art("lundi", date="2026-09-24"),
                       _art("trop vieux", date="2026-09-21")], "2026-09-24")
    assert {x["titre"] for x in a["titres"]} == {"vendredi", "samedi", "lundi"}


def test_un_article_posterieur_a_la_seance_est_ecarte():
    """⚠️ Le briefing porte la séance CLOSE. Y verser une publication du
    lendemain donnerait au lecteur une information que le marché n'avait pas
    quand il a coté."""
    a = bf.actualites([_art("demain", date="2026-09-25")], "2026-09-24")
    assert a["titres"] == []


def test_la_source_officielle_se_distingue_de_la_presse():
    """⚠️ Un communiqué déposé au régulateur et un article de presse
    n'engagent pas la même chose."""
    a = bf.actualites([_art("officiel", tier="S1"),
                       _art("presse", tier="S2")], "2026-09-24")
    par = {x["titre"]: x["officielle"] for x in a["titres"]}
    assert par == {"officiel": True, "presse": False}


def test_le_texte_integral_n_est_jamais_repris():
    """⚠️ `rights` vaut « unknown » sur les 300 articles collectés. Tant que
    les conditions de reprise ne sont pas établies, citer le titre et renvoyer
    à la source est la seule forme sûre — et la plus utile."""
    a = bf.actualites([dict(_art(), summary="A" * 500,
                            content="texte intégral de l'article")],
                      "2026-09-24")
    x = a["titres"][0]
    assert "summary" not in x and "content" not in x
    assert set(x) == {"titre", "source", "url", "date", "importance",
                      "tickers", "type", "officielle"}


def test_un_article_materiel_sans_ticker_n_est_pas_jete():
    """⚠️ Vide au 25/09 — les 73 articles matériels portent tous un ticker.
    Mais jeter en silence celui qu'on n'attendait pas serait perdre
    précisément celui qui compte."""
    a = bf.actualites([_art("orphelin", tickers=())], "2026-09-24")
    assert [x["titre"] for x in a["autres"]] == ["orphelin"]


def test_les_actualites_absentes_n_empechent_pas_le_briefing():
    """⚠️ Un briefing sans actualités reste utile. L'inverse n'est pas vrai."""
    assert bf.charger_articles("/inexistant/news.json") == []
    b = bf.composer(_flux({"change_pct": -1.0, "hausses": 1, "baisses": 5,
                           "inchanges": 0}))
    assert b["constats"]


# ── Le fichier que le terminal lit ─────────────────────────────────────────

def test_le_briefing_s_ecrit_dans_un_fichier(tmp_path):
    """⚠️ Le terminal est un site STATIQUE : il ne collecte rien. Le bouton
    lit un fichier déjà publié — c'est la même limite qui a rendu les proxys
    CORS inutilisables le 25/08/2026."""
    chemin = tmp_path / "briefing.json"
    bf.ecrire({"seance": "2026-09-24", "constats": ["un constat"]}, chemin)
    assert json.loads(chemin.read_text(encoding="utf-8"))["seance"] == "2026-09-24"


def test_le_moteur_ecrit_le_briefing():
    """Un briefing qu'aucun run ne produit laisse le bouton vide à jamais."""
    import ast
    arbre = ast.parse((RACINE / "update_data.py").read_text(encoding="utf-8"))
    assert any(isinstance(n, ast.ImportFrom)
               and (n.module or "").endswith("briefing")
               for n in ast.walk(arbre)), \
        "le moteur ne génère pas briefing.json"


def test_le_terminal_lit_le_briefing_et_dit_quand_il_manque():
    """⚠️ Un panneau vide se lit « rien à signaler », ce qui est faux. Le
    terminal doit DIRE que le briefing manque."""
    ecran = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "briefing.json" in ecran, "le terminal ne lit pas le briefing"
    assert '{id:"briefing"' in ecran, "l'onglet BRIEFING n'existe pas"
    i = ecran.find('etat==="absent"')
    assert i > 0 and "n'a pas été publié" in ecran[i:i + 400], (
        "l'absence de briefing s'afficherait comme un panneau vide")


# ── Le branchement dans le bulletin ────────────────────────────────────────

def test_le_bulletin_porte_la_lecture_dans_SES_DEUX_rendus():
    """⚠️ Un briefing présent dans le texte et absent du HTML donnerait deux
    bulletins différents au même lecteur selon son logiciel de courrier."""
    sys.path.insert(0, str(RACINE / "pipeline"))
    import bulletin_mail as bm
    d, t = bm.charger()
    a = bm.analyser(d, t)
    assert "LECTURE DE LA SÉANCE" in bm.texte(a)
    assert "Lecture de la séance" in bm.html(a)


def test_la_largeur_est_la_meme_dans_les_deux_rendus():
    """⚠️ L'en-tête comptait les hausses sur NOTRE univers (80 titres) et la
    lecture sur celui de l'opérateur (68 valeurs traitées) : « 14 hausses »
    quatre lignes au-dessus de « 16 valeurs en hausse », dans le même
    courriel. Une seule fonction sert désormais les deux rendus."""
    sys.path.insert(0, str(RACINE / "pipeline"))
    import bulletin_mail as bm
    d, t = bm.charger()
    a = bm.analyser(d, t)
    ligne = bm.largeur_ligne(a)
    assert ligne in bm.texte(a) and ligne in bm.html(a)
    m = a["masi"]
    if m.get("hausses") is not None:
        assert str(m["hausses"]) in ligne, (
            "l'en-tête ne reprend pas la largeur de l'opérateur")


def test_la_largeur_retombe_sur_notre_decompte_et_le_dit():
    """Quand l'indice ne livre pas sa largeur, on publie la nôtre — en disant
    que c'est la nôtre. Un décompte anonyme serait pris pour celui de la
    Bourse."""
    sys.path.insert(0, str(RACINE / "pipeline"))
    import bulletin_mail as bm
    a = {"masi": {}, "hausses": [1, 2], "baisses": [1], "cotes": 5}
    ligne = bm.largeur_ligne(a)
    assert "2 hausses" in ligne and "nos 5 titres" in ligne
