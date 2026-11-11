#!/usr/bin/env python3
"""La fiche d'un titre : « Dernier semestre » et « À savoir » — 09/11/2026.

Demande d'Abd Moutalib du 09/11/2026 : enrichir la fiche de chaque titre, en
s'inspirant de ce qui se fait ailleurs (vue d'ensemble, dernier semestre,
points d'attention), SANS rien retirer de l'existant et SANS donnée nouvelle.

⚠️ CE MODULE NE LIT AUCUN DOCUMENT ET N'INVENTE AUCUN CHIFFRE
──────────────────────────────────────────────────────────────
Il RANGE, pour la fiche, ce qui est déjà relevé sur pièce dans le dépôt :

  · `comptes_s1` — le tableau S1 2026 contre S1 2025, recopié de
    `datasets/resultats_s1_2026.json` (et des EBITDA de
    `datasets/bilan_ebitda_s1_2026.json` quand ils existent). Les seuls calculs
    sont des rapports entre chiffres relevés : variation en %, marge en %,
    écart de marge en points. Chaque ligne porte sa source (document, URL,
    pages) TELLE QU'ELLE EST RELEVÉE ; les réserves du relevé (conclusion des
    commissaires « sous réserve », reprises d'exploitation, périmètre élargi,
    éléments exceptionnels) sont publiées, jamais filtrées. Un titre sans relevé
    dit « non relevé » et, quand le dépôt la porte, la raison.

  · `a_savoir` — la liste DATÉE des faits qui changent la lecture des chiffres,
    lus dans les REGISTRES de `bvc_config.py` (SPLITS, SUSPENSIONS,
    OFFRES_PUBLIQUES, METHODE_COMPTABLE, RUPTURES_METHODE, SANS_COMPTES,
    OPERATIONS_SUR_CAPITAL, HISTORIQUE_ACTIONS, CAUSES_RESIDU_FONDS_PROPRES,
    COTATION_AU_FIXING) et dans les champs `_meta` déjà publiés
    (`pb_actions_autodetenues`, accord ACCORD_AUTODETENUES_PB). Chaque fait
    porte sa pièce ; un registre qui n'en cite pas (SPLITS) le DIT.

⚠️ DESCRIPTIF : N'ENTRE DANS AUCUN SCORE (R8)
──────────────────────────────────────────────
`annexer_fiche` ne pose que `comptes_s1` et `a_savoir`, après la note, la
confiance, le Score BVC et le rang sectoriel ; rien en aval ne les lit.
L'invariance est prouvée par un essai à blanc jumeau (mêmes entrées, avec et
sans ce bloc) : `tests/test_fiche_comptes.py`. Tout ou rien : les deux blocs
sont calculés pour tous les titres avant d'être posés.

⚠️ AUCUN MOT D'ACTION, AUCUNE PRÉVISION (Vision produit) : des faits datés, des
chiffres publiés et leurs rapports, rien sur ce que le cours « va » faire.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import unquote

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:          # lancé en script : bvc_config est à la racine
    sys.path.insert(0, str(RACINE))
import bvc_config as C  # noqa: E402
JEU_S1 = RACINE / "datasets" / "resultats_s1_2026.json"
JEU_EBITDA = RACINE / "datasets" / "bilan_ebitda_s1_2026.json"
JEU_EXERCICE = RACINE / "datasets" / "exercice_2025_rectifie.json"

PERIODE = "S1 2026 contre S1 2025"
SOURCE_S1 = "datasets/resultats_s1_2026.json"
SOURCE_EBITDA = "datasets/bilan_ebitda_s1_2026.json"

# Champs du relevé publiés comme PRÉCISIONS, dans cet ordre, avec leur libellé.
# Les champs absents d'ici (actions, capitaux propres, exercice 2025, anciennes
# valeurs `avant_*`) ne décrivent pas la comparaison des deux semestres.
_PRECISIONS = (
    ("base", "Base retenue"),
    ("ca_libelle", "Ligne de chiffre d'affaires"),
    ("note", "Note du relevé"),
    ("perimetre_elargi", "Périmètre"),
    ("production_lue", "Lecture de la ligne de chiffre d'affaires"),
)
# Toujours des réserves, quel que soit leur texte.
_TOUJOURS_RESERVE = {"note", "perimetre_elargi", "reserve_cac", "proforma_s1_2025",
                     "retraitement_exceptionnel", "rnpg_publie_s1_2026"}
# Mots qui font d'une précision une réserve (texte du relevé, insensible à la casse).
_MOTS_RESERVE = ("⚠", "réserve", "exceptionnel", "non récurrent", "reprise", "plus-value",
                 "proforma", "pro forma", "périmètre")


# ─────────────────────────── utilitaires ───────────────────────────

def _lire(chemin: Path) -> dict:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def charger(racine: Path | None = None) -> dict:
    """Les trois jeux relevés : {"s1": …, "ebitda": …, "exercice": …}."""
    r = Path(racine) if racine else RACINE
    s1 = _lire(r / "datasets" / "resultats_s1_2026.json")
    eb = _lire(r / "datasets" / "bilan_ebitda_s1_2026.json")
    ex = _lire(r / "datasets" / "exercice_2025_rectifie.json")
    return {"s1": s1, "ebitda": eb.get("titres", eb), "exercice": ex.get("titres", {})}


def nombre_fr(x, d: int = 0) -> str:
    """« 1 418,7 » — séparateur de milliers espace, virgule décimale."""
    if x is None:
        return "—"
    s = f"{abs(x):,.{d}f}".replace(",", " ").replace(".", ",")
    return ("−" if x < 0 else "") + s


def _date_fr(iso: str | None) -> str:
    s = str(iso or "")[:10]
    p = s.split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else s


def document_de(url: str | None) -> str | None:
    """Le nom du document lu dans son URL (« ADI_S1_26.pdf »)."""
    if not url:
        return None
    return unquote(str(url).rstrip("/").rsplit("/", 1)[-1]) or None


def _variation_pct(avant, apres):
    """(variation en %, motif) — sans objet si la base est nulle ou négative."""
    if avant is None or apres is None:
        return None, "un des deux semestres n'est pas relevé"
    if avant <= 0:
        return None, "base S1 2025 nulle ou négative : un pourcentage n'a pas de sens"
    return round((apres / avant - 1) * 100, 1), None


def _marge(num, den):
    if num is None or den is None or den <= 0:
        return None
    return round(num / den * 100, 1)


def _est_reserve(champ: str, texte: str) -> bool:
    if champ in _TOUJOURS_RESERVE:
        return True
    t = (texte or "").lower()
    return any(m in t for m in _MOTS_RESERVE)


def _libelle_ca(ticker: str, ca_libelle: str | None) -> str:
    """Le libellé COURT de la première ligne, déduit de la ligne relevée."""
    t = (ca_libelle or "").lower()
    if t.startswith("produit net bancaire"):
        return "Produit net bancaire"
    if t.startswith("primes émises"):
        return "Primes émises"
    if t.startswith("produits des activités ordinaires"):
        return "Produits des activités ordinaires"
    if t.startswith("produits d'exploitation"):
        return "Produits d'exploitation"
    if t.startswith("ventes"):
        return "Ventes"
    if not t and C.famille_note(ticker) == "banque":
        return "Produit net bancaire"
    return "Chiffre d'affaires"


# ─────────────────────────── « Dernier semestre » ───────────────────────────

def _motif_non_releve(ticker: str, ecartes: dict, exercice: dict) -> tuple[str | None, str | None]:
    """(motif, source) d'un titre sans relevé S1, tels que le dépôt les porte."""
    if ticker in ecartes:
        return str(ecartes[ticker]), f"{SOURCE_S1} › _ecartes › {ticker}"
    sc = C.sans_comptes(ticker)
    if sc:
        return (f"aucun compte déposé depuis le {_date_fr(sc.get('dernier_depot'))} : {sc.get('motif')}",
                sc.get("source"))
    ex = exercice.get(ticker) or {}
    clos = str(ex.get("exercice_clos") or "")
    if clos and not clos.endswith("-12-31"):
        return (f"exercice décalé, clos le {_date_fr(clos)} : aucun semestre arrêté au 30/06/2026 "
                f"n'est relevé pour cette société",
                f"datasets/exercice_2025_rectifie.json › {ticker} › exercice_clos")
    return None, None


def comptes_s1(ticker: str, releve: dict | None, *, ecartes: dict | None = None,
               ebitda: dict | None = None, exercice: dict | None = None,
               fin_periode: str = "2026-06-30") -> dict:
    """Le bloc « Dernier semestre » d'un titre.

    `releve` est l'entrée de `resultats_s1_2026.json › titres › ticker` (ou None),
    `ebitda` celle de `bilan_ebitda_s1_2026.json` (ou None). Aucun chiffre n'est
    produit qui ne soit un rapport entre chiffres relevés."""
    if not releve:
        motif, src = _motif_non_releve(ticker, ecartes or {}, exercice or {})
        return {"etat": "non_releve", "periode": PERIODE, "fin_periode": fin_periode,
                "motif": motif, "motif_source": src, "lignes": [], "reserves": [],
                "precisions": [], "sources": []}

    url = releve.get("url")
    src_principale = {"document": document_de(url), "url": url, "pages": releve.get("pages"),
                      "releve": f"{SOURCE_S1} › titres › {ticker}"}
    sources = [src_principale]
    lignes = []

    ca25, ca26 = releve.get("ca_s1_2025"), releve.get("ca_s1_2026")
    lib_ca = _libelle_ca(ticker, releve.get("ca_libelle"))
    if ca25 is not None or ca26 is not None:
        v, m = _variation_pct(ca25, ca26)
        lignes.append({"cle": "ca", "libelle": lib_ca, "unite": "MDH", "s1_2025": ca25, "s1_2026": ca26,
                       "variation_pct": v, "variation_motif": m, "source": 0})

    eb = ebitda or {}
    e25 = (eb.get("ebitda_s1_2025") or {}).get("valeur")
    e26 = (eb.get("ebitda_s1_2026") or {}).get("valeur")
    if e25 is not None or e26 is not None:
        sources.append({"document": document_de(eb.get("source")), "url": eb.get("source"),
                        "pages": "p." + ", p.".join(sorted({str((eb.get(k) or {}).get("page"))
                                                            for k in ("ebitda_s1_2026", "ebitda_s1_2025")
                                                            if (eb.get(k) or {}).get("page") is not None})),
                        "releve": f"{SOURCE_EBITDA} › titres › {ticker}",
                        "formule": (eb.get("ebitda_s1_2026") or {}).get("formule")})
        v, m = _variation_pct(e25, e26)
        lib = ("EBITDA publié" if eb.get("base_ebitda") == "publié"
               else "EBITDA (résultat opérationnel + dotations)")
        lignes.append({"cle": "ebitda", "libelle": lib, "unite": "MDH", "s1_2025": e25, "s1_2026": e26,
                       "variation_pct": v, "variation_motif": m, "source": len(sources) - 1})

    r25, r26 = releve.get("rnpg_s1_2025"), releve.get("rnpg_s1_2026")
    base = (releve.get("base") or "").lower()
    lib_rn = ("Résultat net (social)" if "social" in base.split("—")[0].split("(")[0]
              else "Résultat net part du groupe")
    v, m = _variation_pct(r25, r26)
    lignes.append({"cle": "rnpg", "libelle": lib_rn, "unite": "MDH", "s1_2025": r25, "s1_2026": r26,
                   "variation_pct": v, "variation_motif": m, "source": 0})

    # Marges : rapports entre chiffres relevés, en %, et leur écart en points.
    def _ligne_marge(cle, libelle, numerateur, n25, n26, src):
        m25, m26 = _marge(n25, ca25), _marge(n26, ca26)
        if m25 is None and m26 is None:
            return None
        pts = round(m26 - m25, 1) if (m25 is not None and m26 is not None) else None
        return {"cle": cle, "libelle": libelle, "unite": "%", "s1_2025": m25, "s1_2026": m26,
                "variation_pts": pts,
                "calcul": f"{numerateur} ÷ {lib_ca.lower()} × 100, semestre par semestre",
                "source": src}

    if e25 is not None or e26 is not None:
        lm = _ligne_marge("marge_ebitda", f"Marge d'EBITDA (EBITDA / {lib_ca.lower()})", "EBITDA",
                          e25, e26, len(sources) - 1)
        if lm:
            lignes.append(lm)
    num_rn = "RNPG" if lib_rn.endswith("groupe") else "résultat net"
    lm = _ligne_marge("marge_nette", f"Marge nette ({num_rn} / {lib_ca.lower()})", num_rn, r25, r26, 0)
    if lm:
        lignes.append(lm)

    # Précisions et réserves, recopiées du relevé.
    reserves, precisions = [], []
    for champ, libelle in _PRECISIONS:
        t = releve.get(champ)
        if not t:
            continue
        item = {"champ": champ, "libelle": libelle, "texte": str(t)}
        (reserves if _est_reserve(champ, str(t)) else precisions).append(item)
    if releve.get("reserve_cac"):
        reserves.insert(0, {"champ": "reserve_cac", "libelle": "Réserve des commissaires aux comptes",
                            "texte": str(releve["reserve_cac"]), "source": releve.get("source_reserve_cac")})
    pf = releve.get("proforma_s1_2025")
    if isinstance(pf, dict):
        reserves.append({"champ": "proforma_s1_2025", "libelle": "S1 2025 à périmètre comparable (pro forma)",
                         "texte": pf.get("citation") or "", "source": pf.get("source"), "page": pf.get("page"),
                         "valeurs": {k: pf.get(k) for k in ("ca", "rnpg", "unite")}})
    rx = releve.get("retraitement_exceptionnel")
    if isinstance(rx, dict):
        reserves.append({"champ": "retraitement_exceptionnel",
                         "libelle": "Résultat ajusté publié par la société",
                         "texte": rx.get("citation") or "", "source": rx.get("source"), "page": rx.get("page"),
                         "valeurs": {"s1_2026": rx.get("rnpg_ajuste_s1_2026"),
                                     "s1_2025": rx.get("rnpg_ajuste_s1_2025"), "unite": rx.get("unite")}})
    if releve.get("rnpg_publie_s1_2026") is not None:
        reserves.append({"champ": "rnpg_publie_s1_2026",
                         "libelle": "Résultat net publié, avant retrait des éléments exceptionnels",
                         "texte": (f"S1 2026 : {nombre_fr(releve['rnpg_publie_s1_2026'], 1)} MDH"
                                   + (f" ; S1 2025 : {nombre_fr(releve['rnpg_publie_s1_2025'], 1)} MDH"
                                      if releve.get("rnpg_publie_s1_2025") is not None else "")
                                   + " — le tableau retient la base décrite ci-dessus")})
    # Une citation de page qui porte elle-même un avertissement : réserve aussi.
    pages = str(releve.get("pages") or "")
    if "⚠" in pages:
        reserves.append({"champ": "pages", "libelle": "Avertissement porté par le relevé",
                         "texte": pages[pages.index("⚠"):]})

    return {"etat": "releve", "periode": PERIODE, "fin_periode": fin_periode, "unite": "MDH",
            "lignes": lignes, "sources": sources, "reserves": reserves, "precisions": precisions,
            "motif": None, "motif_source": None}


# ─────────────────────────── « À savoir » ───────────────────────────

def _fait(date, nature, titre, texte, source=None, url=None, pages=None, piece=None, sha256=None,
          registre=None) -> dict:
    return {"date": date, "nature": nature, "titre": titre, "texte": texte, "source": source,
            "url": url, "pages": pages, "piece": piece, "sha256": sha256, "registre": registre}


def _cle_tri(f: dict) -> str:
    d = str(f.get("date") or "")
    if len(d) == 4:
        d += "-12-31"
    elif len(d) == 7:
        d += "-31"
    return d or "0000"


def a_savoir(ticker: str, meta: dict | None = None, jour: str | None = None) -> list:
    """Les faits datés qui changent la lecture des chiffres de ce titre, les plus
    récents d'abord. Liste vide si aucun registre ne porte rien sur lui."""
    meta = meta or {}
    faits = []

    for s in C.SPLITS.get(ticker, []):
        faits.append(_fait(
            s["date"], "split", f"Division du titre : 1 action devient {s['ratio']}",
            f"Nombre d'actions multiplié par {s['ratio']} ; les cours antérieurs au {_date_fr(s['date'])} "
            f"sont divisés par {s['ratio']} dans l'historique, la capitalisation n'en change pas.",
            source="registre SPLITS (bvc_config.py) — pièce non citée dans l'entrée du registre",
            registre="SPLITS"))

    for p in C.SUSPENSIONS.get(ticker, []):
        faits.append(_fait(
            p["depuis"], "suspension", "Cotation suspendue", p.get("motif") or "",
            source=p.get("source"), url=p.get("url"), piece=p.get("piece"), sha256=p.get("piece_sha256"),
            pages=sorted({c["page"] for c in p.get("citations", [])}) or None, registre="SUSPENSIONS"))
        if p.get("reprise"):
            txt = "Reprise de la cotation."
            if p.get("reference_impliquee") is not None:
                d = p.get("dernier_cours_cote") or {}
                txt = (f"Reprise sur une référence remise à neuf de {nombre_fr(p['reference_impliquee'], 2)} DH"
                       + (f" ({p['reference_source']})" if p.get("reference_source") else "")
                       + (f", contre un dernier cours coté de {nombre_fr(d.get('valeur'), 2)} DH le "
                          f"{_date_fr(d.get('date'))}" if d.get("valeur") is not None else "")
                       + ". Ce n'est pas une division du titre : le nombre d'actions est inchangé et "
                         "l'historique n'est pas ajusté (R11).")
            elif p.get("dernier_cours_cote"):
                d = p["dernier_cours_cote"]
                txt = (f"Sans nouvelle référence de cours : la variation du jour se calcule sur "
                       f"la dernière clôture cotée ({nombre_fr(d.get('valeur'), 2)} DH le {_date_fr(d.get('date'))}).")
            faits.append(_fait(
                p["reprise"], "reprise", "Reprise de la cotation", txt,
                source=p.get("reprise_source"), url=p.get("reprise_url") or p.get("reference_piece"),
                piece=p.get("reprise_piece") or p.get("reference_piece"),
                sha256=p.get("reprise_piece_sha256") or p.get("reference_piece_sha256"),
                pages=sorted({c["page"] for c in p.get("reprise_citations", [])}) or None,
                registre="SUSPENSIONS"))

    o = meta.get("offre_publique") if "offre_publique" in meta else C.offre_publique(ticker, jour)
    if o:
        faits.append(_fait(
            o["ouverture"], "offre_publique", o["nature"],
            f"Prix de l'offre {nombre_fr(o['prix'], 2)} DH ; {nombre_fr(o['titres_vises'])} titres visés "
            f"({nombre_fr(o['part_capital_pct'], 2)} % du capital) ; période du {_date_fr(o['ouverture'])} au "
            f"{_date_fr(o['cloture'])} ; résultats le {_date_fr(o['resultats'])}, règlement-livraison le "
            f"{_date_fr(o['reglement_livraison'])}. Initiateurs : {o['initiateurs']}. Visa AMMC {o['visa']} ; "
            f"avis de la Bourse {o['avis_bourse']}.",
            source=f"note d'information visée {o['visa']}", url=o.get("source"), pages=o.get("pages"),
            registre="OFFRES_PUBLIQUES"))

    rm = meta.get("rupture_methode") if "rupture_methode" in meta else C.rupture_methode(ticker)
    for r in rm or []:
        faits.append(_fait(
            r["date_effet"], "rupture_methode", "Changement de méthode comptable",
            f"{r['nature']}. Application : {r['application']}. Non comparable : {r['non_comparable']}.",
            source=document_de(r.get("source")), url=r.get("source"), pages=r.get("pages"),
            registre="RUPTURES_METHODE"))

    mc = C.methode_comptable(ticker)
    if mc:
        ev = {"juste_valeur": "à la juste valeur", "cout": "au coût historique"}.get(
            mc.get("immeubles_placement"), "selon une méthode non établie sur pièce")
        src = mc.get("source") or {}
        faits.append(_fait(
            str(mc["exercice"]), "methode_comptable", "Référentiel comptable",
            f"Comptes {mc['exercice']} établis selon : {mc['referentiel']} ; immeubles de placement évalués {ev}.",
            source=src.get("fichier"), url=src.get("url"), sha256=src.get("sha256"),
            pages=sorted({c["page"] for c in src.get("citations", [])}) or None, registre="METHODE_COMPTABLE"))

    sc = C.sans_comptes(ticker)
    if sc:
        faits.append(_fait(
            sc["dernier_depot"], "sans_comptes", "Aucun compte déposé depuis cette date",
            (f"{sc['statut_juridique']} — " if sc.get("statut_juridique") else "") + sc["motif"],
            source=sc.get("source"), registre="SANS_COMPTES"))

    oc = C.OPERATIONS_SUR_CAPITAL.get(ticker)
    if oc:
        apport = (f" Apport en fonds propres : {nombre_fr(oc['apport_frais_mmad'], 1)} MDH."
                  if oc.get("apport_frais_mmad") is not None else "")
        faits.append(_fait(
            oc.get("date") or str(oc["exercice"]), "operation_capital",
            f"Opération sur le capital (exercice {oc['exercice']})",
            f"{oc['nature'][:1].upper()}{oc['nature'][1:]}.{apport} Les fonds propres de l'exercice ne se "
            f"comparent pas tels quels à ceux de l'exercice précédent.",
            source=oc.get("source"), registre="OPERATIONS_SUR_CAPITAL"))

    ha = C.HISTORIQUE_ACTIONS.get(ticker) or {}
    for mv in ha.get("mouvements", []):
        if mv.get("nature") == "numeraire":
            titre = "Augmentation de capital en numéraire"
            txt = (f"Nombre d'actions {nombre_fr(mv['avant'])} → {nombre_fr(mv['apres'])}. Les montants par "
                   f"action d'avant et d'après cette date ne portent pas sur le même nombre d'actions.")
        else:
            titre = "Division du nominal"
            txt = f"Ratio {mv.get('ratio')} : les montants par action d'avant cette date sont rétro-ajustés."
        faits.append(_fait(mv["date"], "nombre_actions", titre, txt, source=mv.get("source"),
                           registre="HISTORIQUE_ACTIONS"))
    if ha.get("denominateur_ambigu") and ha.get("reserve"):
        faits.append(_fait(None, "nombre_actions", "Nombre d'actions du BPA non tranché",
                           ha["reserve"], source="registre HISTORIQUE_ACTIONS (bvc_config.py)",
                           registre="HISTORIQUE_ACTIONS"))

    cr = C.CAUSES_RESIDU_FONDS_PROPRES.get(ticker)
    if cr:
        faits.append(_fait(
            str(cr["exercice"]), "fonds_propres", f"Fonds propres {cr['exercice']} : mouvement hors résultat",
            f"{cr['libelle'][:1].upper()}{cr['libelle'][1:]} : {nombre_fr(cr['montant_mmad'], 1)} MDH (part du "
            f"groupe). Les fonds propres ont varié pour une autre raison que le résultat et le dividende.",
            source=cr.get("source"), pages=[cr["page"]] if cr.get("page") else None,
            registre="CAUSES_RESIDU_FONDS_PROPRES"))

    pa = meta.get("pb_actions_autodetenues")
    if pa:
        faits.append(_fait(
            pa.get("au"), "actions_autodetenues", "Actions autodétenues retirées du P/B",
            f"{nombre_fr(pa.get('nombre'))} actions ({pa.get('nature')}) sont déduites du nombre d'actions "
            f"pour le P/B ; la capitalisation et le BPA ne sont pas touchés"
            + (f" ({pa['accord']})" if pa.get("accord") else "") + ".",
            source=pa.get("source"), pages=[pa["page"]] if pa.get("page") else None,
            registre="ACCORD_AUTODETENUES_PB"))

    fx = C.COTATION_AU_FIXING
    if ticker in fx.get("tickers", []):
        faits.append(_fait(
            fx["seance"], "fixing", "Cotation au fixing",
            f"Un seul prix par séance, au fixing de 14h30 : ouverture, plus haut, plus bas et clôture se "
            f"confondent. Constaté à la séance du {_date_fr(fx['seance'])} ; la Bourse reclasse les titres "
            f"selon leur liquidité, le mode peut avoir changé depuis.",
            source=fx.get("source"), registre="COTATION_AU_FIXING"))

    return sorted(faits, key=_cle_tri, reverse=True)


# ─────────────────────────── annexion ───────────────────────────

def annexer_fiche(tickers: list, racine: Path | None = None, jour: str | None = None) -> dict:
    """Pose `comptes_s1` et `a_savoir` sur chaque titre — et RIEN d'autre.

    Tout ou rien : les blocs sont calculés pour tous les titres, puis posés.
    Une exception remonte à l'appelant, qui la journalise sans emporter la
    publication (update_data.run)."""
    jeux = charger(racine)
    s1 = jeux["s1"]
    titres_s1 = s1.get("titres", {})
    calcul = {}
    for x in tickers:
        sym = x["symbol"]
        calcul[sym] = {
            "comptes_s1": comptes_s1(sym, titres_s1.get(sym), ecartes=s1.get("_ecartes", {}),
                                     ebitda=jeux["ebitda"].get(sym), exercice=jeux["exercice"],
                                     fin_periode=s1.get("fin_periode", "2026-06-30")),
            "a_savoir": a_savoir(sym, x.get("_meta") or {}, jour),
        }
    for x in tickers:
        x["comptes_s1"] = calcul[x["symbol"]]["comptes_s1"]
        x["a_savoir"] = calcul[x["symbol"]]["a_savoir"]
    return calcul


def resume(calcul: dict) -> dict:
    """Comptes pour le journal du run."""
    return {"titres": len(calcul),
            "dernier_semestre": sum(1 for v in calcul.values() if v["comptes_s1"]["etat"] == "releve"),
            "a_savoir_non_vide": sum(1 for v in calcul.values() if v["a_savoir"])}


if __name__ == "__main__":                                   # pragma: no cover
    data = _lire(RACINE / "data.json")
    c = annexer_fiche(data["tickers"])
    print(resume(c))
    for t in sys.argv[1:]:
        print(json.dumps(c.get(t), ensure_ascii=False, indent=1))
