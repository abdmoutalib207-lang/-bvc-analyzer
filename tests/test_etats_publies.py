"""Contrat de datasets/etats_publies/<TICKER>.json — 11/11/2026.

Le fichier compact de la fiche (pipeline/etats_publies.py) :

1. est la sortie EXACTE du générateur sur les relevés commités, index compris ;
2. pèse au plus 15 Ko compressés par titre (ce que sert GitHub Pages), 80 Ko bruts ;
3. donne à chaque valeur lue un document (URL https), une page et une citation ;
4. est FIDÈLE au relevé détaillé, cellule par cellule — valeur, statut, document,
   page, citation, raison de la cellule vide — sans cellule inventée ;
5. ne calcule que des marges et des variations d'une période à la même période
   précédente, jamais sur une base nulle ou négative ;
6. ne publie rien du site tiers qui a servi de repère aux relevés ;
7. reste hors de data.json et du moteur.

Les attendus sont relus dans les RELEVÉS, pas dans le code testé.
"""
import json
import re
from pathlib import Path

import pytest

from pipeline import etats_publies as EP

RACINE = Path(__file__).resolve().parent.parent
RELEVES = RACINE / "datasets" / "etats_financiers"
PUBLIES = RACINE / "datasets" / "etats_publies"
TITRES = sorted(f.stem for f in RELEVES.glob("*.json"))
STATUT = {"publie": "p", "lu_dans_document_ulterieur_comparatif": "c",
          "calcule_depuis_composantes_publiees": "k"}
MARGES = {"marge_exploitation": ("resultat_exploitation", "chiffre_affaires"),
          "marge_nette": ("resultat_net_part_groupe", "chiffre_affaires")}


def _releve(t):
    return json.loads((RELEVES / f"{t}.json").read_text(encoding="utf-8"))


def _publie(t):
    return json.loads((PUBLIES / f"{t}.json").read_text(encoding="utf-8"))


def _cellules(pub):
    """(vue, clé de ligne, indice, période, cellule) pour toutes les cellules publiées."""
    for vue, v in pub["vues"].items():
        for cle, cs in v["cellules"].items():
            assert len(cs) == len(v["periodes"]), f"{pub['ticker']} {vue} {cle} : longueur"
            for i, c in enumerate(cs):
                yield vue, cle, i, v["periodes"][i], c


def _ligne(texte):
    return re.sub(r"\s+", " ", texte.split(" || ")[0]).strip()


# ── 1. sortie exacte du générateur, 2. poids ───────────────────────────────

def test_les_titres_des_lots_sont_la():
    assert TITRES == ["ADH", "ADI", "AKD", "ATW", "CMGP", "CMT", "CSR", "IAM", "LHM", "MNG", "MSA", "RDS", "RIS", "SMI", "SNA", "SOT", "TGCC"]


def test_fichiers_commites_sont_la_sortie_exacte_du_generateur():
    sorties = EP.generer()
    assert sorted(sorties) == sorted(f.name for f in PUBLIES.glob("*.json"))
    for nom, contenu in sorties.items():
        assert (PUBLIES / nom).read_text(encoding="utf-8") == contenu, \
            f"{nom} à régénérer : python3 pipeline/etats_publies.py"
    assert json.loads(sorties["index.json"])["titres"] == TITRES
    assert EP.main(["--verifier"]) == 0


@pytest.mark.parametrize("t", TITRES)
def test_poids_brut_et_compresse(t):
    """Le plafond porte sur ce qui transite (Pages sert le JSON en gzip) ;
    le poids brut garde une borne large."""
    contenu = (PUBLIES / f"{t}.json").read_text(encoding="utf-8")
    assert len(contenu.encode("utf-8")) <= EP.POIDS_MAX, t
    assert EP.poids_compresse(contenu) <= EP.POIDS_GZ_MAX, t


@pytest.mark.parametrize("t", TITRES)
def test_rapport_compresse_brut_plausible(t):
    """Contrôle qui ne se tait jamais (le repère SOT ci-dessous se désactive dès
    que SOT est régénéré) : le rapport compressé / brut mesuré sur les 13 titres
    va de 0,17 à 0,24 ; hors de 0,10-0,40, l'estimation ne vaut plus rien."""
    contenu = (PUBLIES / f"{t}.json").read_text(encoding="utf-8")
    r = EP.poids_compresse(contenu) / len(contenu.encode("utf-8"))
    assert 0.10 <= r <= 0.40, (t, round(r, 3))


def test_poids_compresse_mesure_comme_pages():
    """Repère mesuré le 12/11/2026 : SOT, 44 944 octets bruts, servi en 9 472
    octets gzip par GitHub Pages. L'estimation doit tomber à ±10 % de ce repère."""
    contenu = (PUBLIES / "SOT.json").read_text(encoding="utf-8")
    if len(contenu.encode("utf-8")) != 44_944:
        pytest.skip("SOT.json a changé depuis la mesure du 12/11")
    assert abs(EP.poids_compresse(contenu) - 9_472) <= 950


# ── 3. toute valeur a sa source ─────────────────────────────────────────────

@pytest.mark.parametrize("t", TITRES)
def test_chaque_valeur_a_document_page_citation(t):
    pub = _publie(t)
    docs, textes = pub["documents"], pub["textes"]
    assert all(d["u"].startswith("https://") for d in docs)

    def source(c, ou):
        assert isinstance(c.get("d"), int) and 0 <= c["d"] < len(docs), f"{ou} : document"
        assert isinstance(c.get("p"), int) and c["p"] >= 1, f"{ou} : page"
        assert isinstance(c.get("c"), str) and c["c"].strip(), f"{ou} : citation"

    n = 0
    for vue, cle, i, per, c in _cellules(pub):
        ou = f"{t} {per['cle']} {cle}"
        for j in c.get("r", []) + c.get("o", []) + ([c["n"]] if "n" in c else []) + ([c["f"]] if "f" in c else []):
            assert 0 <= j < len(textes), f"{ou} : texte"
        if "v" not in c:
            assert set(c) == {"n"}, f"{ou} : cellule vide = sa raison, rien d'autre"
            continue
        n += 1
        assert isinstance(c["v"], (int, float)) and not isinstance(c["v"], bool)
        assert c["s"] in pub["statuts"], ou
        if cle in MARGES:
            assert c["s"] == "m" and set(c) == {"v", "s"}, ou
        elif c["s"] == "k":
            assert "d" not in c and c["k"], f"{ou} : calculé = composantes citées"
            for comp in c["k"]:
                source(comp, ou + " (composante)")
                assert 0 <= comp["l"] < len(textes)
        else:
            assert c["s"] in ("p", "c"), ou
            source(c, ou)
            assert c.get("u") or docs[c["d"]].get("un"), f"{ou} : unité imprimée"
    assert n > (60 if t == "SMI" else 40 if t == "CMGP" else 100), "le lot porte plus de cent valeurs par titre"   # SMI : comptes sociaux, moins de lignes ; CMGP : introduit en bourse en 2025, quatre périodes seulement


# ── 4. fidélité au relevé, cellule par cellule ──────────────────────────────

@pytest.mark.parametrize("t", TITRES)
def test_fidelite_au_releve_cellule_par_cellule(t):
    rel, pub = _releve(t), _publie(t)
    textes, docs = pub["textes"], pub["documents"]
    lignes = {l["cle"] for l in pub["lignes"]}
    assert [l["cle"] for l in pub["lignes"]] == list(pub["vues"]["annuel"]["cellules"]) \
        == list(pub["vues"]["semestriel"]["cellules"])
    vus = set()
    for vue, v in pub["vues"].items():
        typ = "annuel" if vue == "annuel" else "semestriel"
        attendues = sorted((k for k, p in rel["periodes"].items() if p["type"] == typ),
                           key=lambda k: rel["periodes"][k]["cloture"])
        assert [p["cle"] for p in v["periodes"]] == attendues, f"{t} {vue} : périodes"
        for p in v["periodes"]:
            assert p["cloture"] == rel["periodes"][p["cle"]]["cloture"]
    for vue, cle, i, per, c in _cellules(pub):
        if cle in MARGES:
            continue
        ou = f"{t} {per['cle']} {cle}"
        d = rel["periodes"][per["cle"]]["donnees"].get(cle)
        vus.add((per["cle"], cle))
        if d is None or d.get("valeur_mdh") is None:
            assert "v" not in c, f"{ou} : valeur publiée absente du relevé"
            raison = textes[c["n"]]
            assert "ms-screener" not in raison and not re.search(r"\d{3}", raison), ou
            if d is not None:
                assert raison == EP.raison_publique(d["raison_null"]), ou
            continue
        assert c["v"] == d["valeur_mdh"], f"{ou} : valeur"
        assert c["s"] == STATUT[d["statut"]], f"{ou} : statut"
        if d.get("composantes"):
            assert len(c["k"]) == len(d["composantes"]), ou
            for comp, (k, dv) in zip(c["k"], d["composantes"].items()):
                assert docs[comp["d"]]["u"] == rel["documents"][dv["document"]]["url"], f"{ou}/{k}"
                assert comp["p"] == dv["page"] and _ligne(dv["citation"]).startswith(comp["c"].removesuffix(" […]")), f"{ou}/{k}"
                if "v" in comp:
                    assert comp["v"] == dv["valeur_mdh"], f"{ou}/{k}"
            if all("sg" in comp for comp in c["k"]):          # somme signée = valeur du relevé
                somme = sum((1 if comp["sg"] == "+" else -1) * comp["v"] for comp in c["k"])
                assert abs(somme - c["v"]) < 0.01, f"{ou} : la somme des composantes ne redonne pas la valeur"
        else:
            assert docs[c["d"]]["u"] == rel["documents"][d["document"]]["url"], f"{ou} : document"
            assert c["p"] == d["page"], f"{ou} : page"
            assert _ligne(d["citation"]).startswith(c["c"].removesuffix(" […]")), f"{ou} : citation"
            assert c["i"] == re.sub(r"\s+", " ", d["valeur_source"]).strip(), f"{ou} : jeton imprimé"
            assert (c.get("u") or docs[c["d"]]["un"]) == d["unite_source"], f"{ou} : unité"
            if "rf" in c:                                      # référentiel : seulement s'il est relu
                assert c["rf"] == d["referentiel"] and not d.get("referentiel_source"), ou
        if d["statut"] == "lu_dans_document_ulterieur_comparatif":
            assert any("comparati" in textes[j].lower() for j in c.get("r", [])), \
                f"{ou} : valeur d'un comparatif sans réserve qui le dise"
    # Rien d'oublié : toute cellule du relevé est publiée, sauf une ligne « sans objet » partout.
    for k, p in rel["periodes"].items():
        for cle, d in p["donnees"].items():
            if (k, cle) in vus:
                continue
            assert cle not in lignes and d.get("valeur_mdh") is None \
                and d["raison_null"].startswith("sans objet"), f"{t} {k} {cle} : cellule du relevé non publiée"


# ── 5. les seuls calculs : marges et variations, jamais sur base ≤ 0 ────────

@pytest.mark.parametrize("t", TITRES)
def test_variations_et_marges_recalculees(t):
    pub = _publie(t)
    n_var = n_ns = 0
    for vue, v in pub["vues"].items():
        annee = {int(p["cle"][-4:]): i for i, p in enumerate(v["periodes"])}
        for cle, cs in v["cellules"].items():
            for an, i in annee.items():
                c = cs[i]
                avant = cs[annee[an - 1]].get("v") if an - 1 in annee else None
                if "g" not in c:
                    continue
                assert cle not in MARGES and "v" in c and avant is not None, \
                    f"{t} {vue} {cle} {an} : variation sans ses deux termes"
                if c["g"] == "ns":
                    n_ns += 1
                    assert avant <= 0, f"{t} {cle} {an} : « ns » sur une base positive"
                else:
                    n_var += 1
                    assert avant > 0, f"{t} {cle} {an} : variation sur base nulle ou négative"
                    assert c["g"] == round((c["v"] / avant - 1) * 100, 1), f"{t} {cle} {an}"
        for cle, (num, den) in MARGES.items():
            for a, b, m in zip(v["cellules"][num], v["cellules"][den], v["cellules"][cle]):
                if "v" in m:
                    assert b["v"] > 0 and m["v"] == round(a["v"] / b["v"] * 100, 1)
                else:
                    assert "v" not in a or "v" not in b or b["v"] <= 0
    assert n_var > (10 if t == "CMGP" else 20 if t in ("AKD", "RDS") else 50)       # AKD : quatre exercices et quatre semestres seulement (introduit fin 2022) ; RDS : exercices 2019-2025, semestres 2022-2026 seulement, tableau des flux absent
    if t in ("ADI", "MNG"):                      # pertes relues dans les relevés : des « ns » existent
        assert n_ns >= 1


def test_marge_et_variation_refusent_les_bases_nulles_ou_negatives():
    assert EP.variation(100, 110) == 10.0 and EP.variation(100, -50) == -150.0
    assert EP.variation(0, 10) == "ns" and EP.variation(-5, 10) == "ns"
    assert EP.variation(None, 10) is None and EP.variation(10, None) is None
    assert EP.marge(10, 200) == 5.0 and EP.marge(-10, 200) == -5.0
    assert EP.marge(10, 0) is None and EP.marge(10, -3) is None and EP.marge(None, 5) is None


def test_aucune_interpolation_un_trou_reste_un_trou():
    """Relevé synthétique : 2016 et 2018 lus, 2017 non lu. Rien n'est comblé, et
    2018 n'a pas de variation (la période précédente manque)."""
    def cel(v):
        return {"valeur_mdh": v, "unite_source": "MMAD", "valeur_source": str(v), "document": "d.pdf",
                "page": 2, "citation": f"Chiffre d'affaires {v}", "perimetre": "consolide", "statut": "publie"}
    vide = {"valeur_mdh": None, "raison_null": "non relevé dans ce lot (absent de ms-screener, pas de lecture indépendante)"}
    rel = {"schema": "etats_financiers/1", "ticker": "ZZZ", "nom": "Essai", "unite": "MDH",
           "archetype": "standard_nonfin", "perimetre_principal": "consolide",
           "documents": {"d.pdf": {"fichier": "d.pdf", "url": "https://exemple.invalid/d.pdf"}},
           "periodes": {f"FY{a}": {"type": "annuel", "cloture": f"{a}-12-31",
                                   "donnees": {"chiffre_affaires": c}}
                        for a, c in ((2016, cel(100)), (2017, vide), (2018, cel(120)))}}
    pub = EP.construire(rel)
    ca = pub["vues"]["annuel"]["cellules"]["chiffre_affaires"]
    assert [c.get("v") for c in ca] == [100, None, 120]
    assert "g" not in ca[2] and "ms-screener" not in EP.serialiser(pub)
    # Un relevé qui sort du contrat arrête la génération.
    rel["periodes"]["FY2017"]["donnees"]["chiffre_affaires"] = {"valeur_mdh": None, "raison_null": "raison jamais vue"}
    with pytest.raises(EP.ReleveInvalide):
        EP.construire(rel)
    rel["periodes"]["FY2017"]["donnees"] = {"grandeur_nouvelle": vide}
    with pytest.raises(EP.ReleveInvalide):
        EP.construire(rel)


# ── 6. rien du site tiers, libellés imposés ─────────────────────────────────

@pytest.mark.parametrize("t", TITRES)
def test_rien_du_site_tiers_ni_mot_d_action(t):
    brut = (PUBLIES / f"{t}.json").read_text(encoding="utf-8")
    for interdit in ("ms-screener", "ms_valeur", "controle_ms", "`", "ACHETER", "VENDRE", "ÉVITER",
                     "objectif de cours", "prévision"):
        assert interdit not in brut, f"{t} : « {interdit} » publié"
    # Une valeur du site tiers non retrouvée sur pièce (cellule vide du relevé) ne
    # passe ni par la cellule — voir la fidélité — ni par le texte de sa raison.
    rel, pub = _releve(t), _publie(t)
    raisons = {pub["textes"][c["n"]] for *_, c in _cellules(pub) if "n" in c}
    assert raisons and not any(re.search(r"\d", r) for r in raisons), f"{t} : un nombre dans une raison"
    cites = [d["raison_null"] for p in rel["periodes"].values() for d in p["donnees"].values()
             if d.get("valeur_mdh") is None and re.search(r"ms-screener \(\d", d.get("raison_null", ""))]
    if t in ("ADI", "ATW", "IAM", "LHM", "MNG"):   # lot 1 : relevés partis d'une valeur tierce
        assert cites, f"{t} : le relevé ne cite plus de valeur tierce — contrôle à revoir"
    else:                                          # lot 2 et suivants : lecture directe
        assert not cites, f"{t} : un relevé lu directement cite une valeur tierce"


def test_libelles_ebitda_dette_nette_et_banque():
    for t in TITRES:
        lib = {l["cle"]: l["libelle"] for l in _publie(t)["lignes"]}
        if "ebitda_ajuste" in lib:
            assert lib["ebitda_ajuste"] == "EBITDA ajusté (indicateur de gestion, non audité)"
        if "dette_nette" in lib:
            assert lib["dette_nette"] == "Dette nette calculée par BVC Analyzer"
        if "dette_nette_publiee" in lib:
            assert lib["dette_nette_publiee"] == "Dette nette publiée par l'émetteur"
    atw = {l["cle"]: l for l in _publie("ATW")["lignes"]}
    assert atw["chiffre_affaires"]["libelle"] == "Produit net bancaire (PNB)"
    assert atw["ebe"]["libelle"] == "Résultat brut d'exploitation (RBE)"
    assert "dette_nette" not in atw and "dette_nette_publiee" not in atw and "ebitda_ajuste" not in atw
    assert [l["graphique"] for l in atw.values() if "graphique" in l] == \
        ["Produit net bancaire (PNB)", "Résultat d'exploitation", "Résultat net part du groupe"]
    iam = {l["cle"]: l for l in _publie("IAM")["lignes"]}
    assert iam["dette_nette"]["pendant"] == "dette_nette_publiee" and iam["dette_nette_publiee"]["pendant"] == "dette_nette"


def test_r11_nombre_d_actions_d_avant_une_division_porte_sa_reserve():
    """Managem : division du nominal le 27/07/2026 (registre SPLITS). Tout nombre
    d'actions d'une clôture antérieure le dit ; Maroc Telecom n'a rien à dire."""
    mng = _publie("MNG")
    cs = [c for c in mng["vues"]["annuel"]["cellules"]["nombre_actions"] if "v" in c]
    assert len(cs) >= 8
    for c in cs:
        assert any("27/07/2026" in mng["textes"][j] and "division du nominal" in mng["textes"][j] for j in c.get("r", []))
    iam = _publie("IAM")
    assert not any("division du nominal" in x for x in iam["textes"])


# ── 7. hors data.json, hors moteur ──────────────────────────────────────────

def test_hors_data_json_et_hors_moteur():
    assert "etats_publies" not in (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert "etats_publies" not in (RACINE / "pipeline" / "score_bvc.py").read_text(encoding="utf-8")
    data = (RACINE / "data.json").read_text(encoding="utf-8")
    assert "etats_publies" not in data and '"vues"' not in data


# ── relecture #341 : raisons exactes, aucun jargon interne publié ───────────

@pytest.mark.parametrize("t", TITRES)
def test_aucun_jargon_interne_publie(t):
    pub = _publie(t)
    for x in pub["textes"]:
        assert not EP.JARGON.search(x), f"{t} : jargon interne publié : {x[:90]!r}"


def test_une_absence_ne_se_dit_que_de_sa_ligne_et_non_lu_ne_devient_pas_absent():
    ebe_abs = EP.raison_publique("EBE : aucune ligne « EBE » aux états consolidés")
    rec_abs = EP.raison_publique("pas de ligne « résultat d'exploitation courant » aux comptes consolidés")
    for t in TITRES:
        rel = json.loads((RELEVES / f"{t}.json").read_text(encoding="utf-8"))
        for p in rel["periodes"].values():
            for cle, d in p["donnees"].items():
                if d.get("valeur_mdh") is not None or not d.get("raison_null"):
                    continue
                pub = EP.raison_publique(d["raison_null"])
                if pub == ebe_abs:
                    assert cle == "ebe", (t, cle, d["raison_null"][:60])
                if pub == rec_abs:
                    assert cle == "resultat_exploitation_courant", (t, cle)
                if re.search(r"non lu|non relevé|non exploré", d["raison_null"]):
                    assert not pub.startswith("Aucune"), (t, cle, d["raison_null"][:60])


def test_temoin_jargon_refuse():
    for x in ("⚠️ attention", "voir R11", "registre SPLITS", "bvc_config"):
        with pytest.raises(EP.ReleveInvalide):
            EP._public(x, "témoin")

