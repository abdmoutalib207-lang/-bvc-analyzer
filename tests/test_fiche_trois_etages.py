"""Fiche d'un titre en trois étages, une date par chiffre (19/11/2026).

Feuille de route (docs/FEUILLE_DE_ROUTE_9_SUR_10.md), lots 1.3 et 1.5. Demande
d'Abd Moutalib : « faire le nettoyage du bruit sur l'interface, la lecture doit
être simple facile ».

Ce qui est vérifié, sur la SOURCE (terminal.src.html) :
1. les trois étages existent, une fois chacun, dans l'ordre En bref →
   Comprendre → Détail, et chaque bloc est à son étage ;
2. « En bref » porte cours, variation, Score BVC, sa tranche, sa phrase, la
   date de la semaine close, la fiabilité et trois chiffres clés — et rien de
   l'étage « Comprendre » ;
3. une date par chiffre : quatre sortes (cours, score, comptes, risque), au
   même format, lues telles que le moteur les publie ;
4. le « Détail » est replié sur téléphone, ouvert ailleurs ;
5. aucune réserve, mention ni motif d'absence n'a disparu, et les réserves
   qui portent sur tout le titre restent hors des plis ;
6. aucun mot d'action.
Contrôle négatif : ce fichier échoue sur la fiche d'avant (commit 2047d3e) —
vérifié à la livraison. Le rendu réel est contrôlé par tools/qa_navigateur.js.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def _entre(debut: str, fin: str) -> str:
    """Texte de `debut` à `fin` ; vide si l'un manque (le test échoue alors sur
    son assertion, pas à la collecte)."""
    i = SRC.find(debut)
    j = SRC.find(fin, i + len(debut)) if i >= 0 else -1
    return SRC[i:j] if j >= 0 else ""


DETAIL = _entre("const Detail=({rows,sel", "// ── WEIGHTS")
AIDES = _entre("// ── FICHE EN TROIS ÉTAGES", "const Detail=({rows,sel")


def _etage(nom: str) -> str:
    """Texte de la section `data-etage="nom"` jusqu'à sa balise fermante."""
    i = DETAIL.find(f'data-etage="{nom}"')
    j = DETAIL.find("</section>", i) if i >= 0 else -1
    return DETAIL[i:j] if j >= 0 else ""


BREF, COMPRENDRE, DETAIL_ETAGE = _etage("bref"), _etage("comprendre"), _etage("detail")


# ── 1. trois étages, dans l'ordre ───────────────────────────────────────────

def test_trois_etages_une_fois_chacun_dans_l_ordre():
    for nom in ("bref", "comprendre", "detail"):
        assert DETAIL.count(f'data-etage="{nom}"') == 1, nom
    assert (DETAIL.index('data-etage="bref"') < DETAIL.index('data-etage="comprendre"')
            < DETAIL.index('data-etage="detail"'))
    # Les intitulés se lisent à l'écran.
    for titre in ('<EtageTitre nom="En bref"', '<EtageTitre nom="Comprendre"', '<EtageTitre nom="Détail"'):
        assert DETAIL.count(titre) == 1, titre
    # Au-delà de 1200 px, le Détail (graphique) est la colonne centrale et le
    # panneau des chiffres (En bref + Comprendre) celle de droite.
    assert 'className="fiche-centre etage etage-detail"' in DETAIL
    assert ".fiche-note{grid-column:2;grid-row:1}" in SRC and ".fiche-centre{grid-column:1;grid-row:1}" in SRC


def test_chaque_bloc_est_a_son_etage():
    places = {
        "bref": ['className="fiche-cours"', 'className="fiche-identite"', "<EnTeteEssentiel ",
                 'className="score-bvc-tete"', "<DateScore ", "<Confiance r={r}", "<DetailConfiance r={r}/>",
                 "<TroisChiffres "],
        "comprendre": ["<ScoreBVC ", "echange_median_dh", ">Fondamentaux", "<SourcesRatios r={r}/>",
                       "<ResumeNote r={r}/>", "<RedFlags ", "<MesuresBancaires r={r}/>", "r.ratios_publies&&("],
        "detail": ["<StockChart r={r}/>", "<RSIGauge ", "r.niveaux", "<RisqueMesure ", "<DernierSemestre ",
                   "<EtatsFinanciers sym={sym}/>", "<ASavoir ", "r.fwd&&(", "Scénarios Prix",
                   "<SignauxTechniques r={r}/>", "<TickerNews sym={sym}/>"],
    }
    etages = {"bref": BREF, "comprendre": COMPRENDRE, "detail": DETAIL_ETAGE}
    for nom, blocs in places.items():
        for bloc in blocs:
            assert bloc in etages[nom], f"{bloc} absent de l'étage {nom}"
            for autre, texte in etages.items():
                if autre != nom:
                    assert bloc not in texte, f"{bloc} aussi dans l'étage {autre}"


# ── 2. En bref ───────────────────────────────────────────────────────────────

def test_en_bref_cours_score_tranche_phrase_fiabilite():
    assert "{px(price)} DH" in BREF and "varSeance(r)" in BREF          # cours et variation
    assert "{exactBVC(vBVC)}" in BREF and "<PastilleBVC r={r}" in BREF  # score et tranche
    assert "descriptif, pas une prévision" in BREF                      # sa phrase
    assert "<DateScore s={r.score_bvc}/>" in BREF                        # sa semaine close
    # Le score garde sa taille et sa couleur grise à confiance ≤ 1.
    tete = BREF[BREF.index('className="score-bvc-tete"'):BREF.index("{exactBVC(vBVC)}")]
    assert "fontSize:52" in tete and "color:couleurChiffre(r)" in tete


def test_trois_chiffres_cles_au_plus_avec_leur_motif():
    corps = _entre("const TroisChiffres=", "const SourcesRatios=")
    cles = re.findall(r'\["(pe|div|cap|pb)",', corps)
    assert cles == ["pe", "div", "cap"]                     # PER, rendement, capitalisation
    # Mêmes valeurs et mêmes absences que la grille « Fondamentaux ».
    for x in ("perTxt(r.pe,bpa)", "divFiche(r.div)", 'r.cap?fmtM(r.cap):"—"', "perNS(r.pe,bpa)"):
        assert x in corps, x
    # Le motif d'un « — » ou d'un « n.s. » au toucher : l'explication des ratios.
    assert "explRatio(cle,r,price)" in corps and "aria-expanded={ex===cle}" in corps
    assert "minHeight:24" in corps
    # L'exception déclarée du PER suit le chiffre.
    assert "r.pe_exception" in corps


# ── 3. une date par chiffre ──────────────────────────────────────────────────

def test_quatre_sortes_de_dates_au_meme_format():
    m = re.search(r"const DATES_FICHE=(\{[^}]*\});", SRC)
    assert m, "DATES_FICHE introuvable"
    assert re.findall(r"(\w+):", m.group(1)) == ["cours", "score", "comptes", "risque"]
    # Un seul format, JJ/MM/AAAA, pour toutes.
    corps = _entre("const DateChiffre=", "const DateScore=")
    assert "jjmmaaaa(d)" in corps and "date inconnue" in corps
    # Chaque date est placée à côté de son chiffre.
    assert 'data-date="cours"' in _entre("const EnTeteEssentiel=", "const DetailConfiance=")
    assert 'quoi="score" d={w.fin}' in AIDES                       # score_bvc.semaine.fin
    assert "<TroisChiffres " in BREF and "<DatePER r={r}/>" in _entre("const TroisChiffres=", "const SourcesRatios=")
    assert "<DatePER r={r}/>" in COMPRENDRE
    assert '<DateChiffre quoi="risque" d={q.asof}/>' in _entre("const RisqueMesure=", "const TexteLong=")
    # Plus de date ISO brute (« 2026-09-29 ») sur la fiche : même format partout.
    assert "· {m.fond_asof} <b>" not in SRC and "relevés le {jjmmaaaa(m.fond_asof)}" in COMPRENDRE


def test_la_date_du_score_n_est_ecrite_qu_une_fois():
    corps = _entre("const ScoreBVC=", "const RisqueMesure=")
    # En tête de fiche (sansValeur), la date de la semaine est dans « En bref ».
    assert "{!sansValeur&&s.semaine&&s.semaine.fin&&" in corps
    # Le dernier échange, quand le titre n'a pas coté le dernier jour, reste dit.
    assert "dernier échange le" in _entre("const DateScore=", "const arreteComptes=")


def _node(script: str):
    node = shutil.which("node")
    if not node:                                    # pragma: no cover
        pytest.skip("node absent de cette machine")
    r = subprocess.run([node, "-"], input=script, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_date_d_arrete_lue_jamais_deduite():
    fn = SRC[SRC.index("const arreteComptes="):SRC.index("const DatePER=")]
    out = _node(fn + "console.log(JSON.stringify([%s].map(arreteComptes)));" % ",".join([
        '{pe_base:"12 mois au 2026-06-30"}', '{pe_base:"exercice 2025"}', "{pe_base:null}", "{}"]))
    assert out[0] == {"d": "2026-06-30"}
    assert out[1] == {"texte": "exercice 2025"}    # pas de « 31/12 » inventé
    assert out[2] is None and out[3] is None


# ── 4. Détail replié sur téléphone, ouvert ailleurs ─────────────────────────

def test_detail_replie_sur_telephone_ouvert_sur_ordinateur():
    pli = _entre("const Pli=", "const EtageTitre=")
    assert "const [ouvert,setOuvert]=useState(false)" in pli       # replié par défaut
    assert "if(!tel)return <>{children}</>;" in pli                # ouvert hors téléphone
    assert "{ouvert&&" in pli                                      # monté à la première ouverture
    assert "minHeight:44" in pli                                   # cible tactile
    assert 'const REQ_TELEPHONE="(max-width:767px)";' in SRC       # même seuil que la grille
    assert "@media(max-width:767px){.detail-grid{grid-template-columns:minmax(0,1fr)!important" in SRC
    # Les blocs lourds du Détail sont dans un pli ; le graphique reste visible.
    for bloc in ("<RisqueMesure ", "<DernierSemestre ", "<EtatsFinanciers ", "<ASavoir ", "<TickerNews "):
        i = DETAIL_ETAGE.index(bloc)
        assert DETAIL_ETAGE.rfind("<Pli ", 0, i) > DETAIL_ETAGE.rfind("</Pli>", 0, i), bloc
    i = DETAIL_ETAGE.index("<StockChart r={r}/>")
    assert DETAIL_ETAGE.rfind("<Pli ", 0, i) == -1


def test_un_pli_replie_dit_ce_qu_il_cache():
    # Réserves du dernier semestre : comptées dans le titre du pli.
    assert "réserve" in _entre("const resumeSemestre=", "const Detail=")
    assert 'resume={resumeSemestre(r.comptes_s1)}' in DETAIL_ETAGE
    # Le prévisionnel garde « non vérifié » dans son titre replié.
    i = DETAIL_ETAGE.index('<Pli titre="Prévisionnel IDBourse DATA+"')
    assert "non vérifié" in DETAIL_ETAGE[i:DETAIL_ETAGE.index(">", DETAIL_ETAGE.index("resume=", i) + 60)]


# ── 5. rien d'honnête n'a disparu ────────────────────────────────────────────

def test_aucune_reserve_ni_motif_ne_disparait():
    for texte in ("descriptif, pas une prévision", "Aucune valeur approchée n'est affichée à la place",
                  "Données insuffisantes", "suspendu depuis le", "REPRISE", "confiance plafonnée",
                  "Aucun compte récent", "Changement de méthode comptable", "Comptes plus récents publiés",
                  "Réserve des commissaires aux comptes", "non vérifié", "Pivots non publiés",
                  "Aucun scénario de prix n'est publié", "formule {s.version}", "date inconnue"):
        assert texte in DETAIL + AIDES + SRC[SRC.index("const ScoreBVC="):SRC.index("const RisqueMesure=")], texte
    # Les réserves qui portent sur tout le titre restent HORS des plis.
    for texte in ("Aucun compte récent", "Changement de méthode comptable", "Comptes plus récents publiés",
                  "Réserve des commissaires aux comptes", "confiance plafonnée", "<ResumeNote r={r}/>"):
        assert texte in COMPRENDRE, texte
    # Une seule réserve principale, en tête ; l'offre publique avant tout.
    assert DETAIL.index("<BandeauOffre ") < DETAIL.index('data-etage="bref"')


def test_la_liquidite_n_est_plus_ecrite_deux_fois():
    corps = _entre("const ResumeNote=", "/* ── EN-TÊTE DE FICHE")
    assert "echange_median_dh" not in corps and "r.alertes" in corps
    assert COMPRENDRE.count("echange_median_dh") == 1


# ── 6. aucun mot d'action ────────────────────────────────────────────────────

def test_aucun_mot_d_action():
    # 19/11/2026 : « pression achat / pression vente » sous l'OBV devient
    # « cumul positif / négatif » — le signe du chiffre, pas une lecture.
    texte = (AIDES + DETAIL).lower()
    for mot in ("acheter", "achat", "vendre", "vente", "éviter", "surveiller", "conserver", "renforcer",
                "potentiel", "objectif de cours", "recommand"):
        assert not re.search(rf"\b{mot}", texte), mot
