#!/usr/bin/env python3
"""États financiers publiés : le fichier COMPACT de la fiche — 11/11/2026.

Demande d'Abd Moutalib (étape 2 de l'enrichissement de la fiche) : montrer
l'historique des états financiers d'un titre — annuel 2016-2025, semestriel
2019-2026 — chaque chiffre avec sa source.

⚠️ CE MODULE NE LIT AUCUN DOCUMENT ET N'INVENTE AUCUN CHIFFRE
──────────────────────────────────────────────────────────────
Il RANGE, pour l'écran, les relevés détaillés `datasets/etats_financiers/
<TICKER>.json` (relus sur pièce, voir leur README) dans un fichier par titre,
`datasets/etats_publies/<TICKER>.json`, plus `index.json` (la liste des titres
couverts : le terminal ne demande jamais un fichier qui n'existe pas).

Les SEULS calculs, étiquetés « calculé » :
  · marge = résultat ÷ chiffre d'affaires (ou PNB) × 100, même période ;
  · variation = période ÷ même période de l'année précédente − 1.
Jamais sur une base nulle ou négative (« n.s. »), jamais d'interpolation : une
cellule non lue reste vide, avec sa raison. La dette nette « calculée par BVC
Analyzer » n'est pas calculée ici : c'est celle du relevé, avec ses composantes
citées ; la dette nette publiée par l'émetteur est une AUTRE ligne.

⚠️ CE QUI N'EST PAS RECOPIÉ
────────────────────────────
Les relevés gardent, pour le contrôle, les valeurs d'un site tiers
(`controle_ms`) ; certaines raisons de cellule vide les citent. Rien de cela
n'est publié : les raisons sont ramenées à une liste fermée (`_RAISONS`), et
une raison inconnue ARRÊTE la génération plutôt que de passer telle quelle.
Le référentiel comptable n'est publié que s'il a été relu sur la page.

⚠️ STATIQUE, HORS data.json, HORS SCORE (R8)
─────────────────────────────────────────────
Ces fichiers ne changent que lorsqu'un relevé change : ils sont commités, lus
à la demande par la fiche, et ni `update_data.py` ni le Score BVC ne les
lisent. `python3 pipeline/etats_publies.py --verifier` échoue si un fichier
commité n'est plus la sortie exacte du générateur.

FORMAT (`etats_publies/1`) — clés courtes, tables factorisées
──────────────────────────────────────────────────────────────
  documents  [{u: URL, f?: nom du fichier quand l'URL ne le dit pas,
              un?: unité imprimée la plus fréquente du document}]
  textes     [str]                             réserves, raisons, formules,
                                               libellés de composantes
  statuts    {p|c|k|m: libellé}                p publié · c lu dans un document
             ultérieur (comparatif) · k calculé depuis composantes publiées ·
             m calculé (marge)
  lignes     [{cle, libelle, groupe, unite, graphique?, calcul?, pendant?}]
  vues       {annuel|semestriel: {periodes: [{cle, libelle, cloture}],
              cellules: {<cle de ligne>: [cellule, …]},
              couverture: {relevees, cellules, documents} — hors marges}}
  cellule    v valeur · s statut · d document (indice) · p page · c citation
             i jeton imprimé · u unité imprimée (seulement si elle diffère de
             celle du document) · rf référentiel lu sur la page
             r [indices de textes] réserves (ce qui rend la valeur incertaine)
             o [indices de textes] précisions (ce qu'est le chiffre)
             g variation en % ou "ns"
             f formule (indice de texte) · k composantes [{l (indice de
             texte), sg, v, i, d, p, c, r, o}]
             n raison de la cellule vide (indice de texte)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:          # lancé en script : bvc_config est à la racine
    sys.path.insert(0, str(RACINE))
import bvc_config as C  # noqa: E402

RELEVES = RACINE / "datasets" / "etats_financiers"
SORTIE = RACINE / "datasets" / "etats_publies"
SCHEMA = "etats_publies/1"
SCHEMA_RELEVE = "etats_financiers/1"
POIDS_MAX = 45_000            # octets par titre (40 000 au lot 1 ; relevé à 45 000 au lot 2 : ADH, 18 périodes de dette nette sur trois composantes citées)
CITATION_MAX = 200            # caractères ; au-delà, coupée et marquée « […] »

STATUTS = {
    "p": "publié — lu dans le document de la période",
    "c": "lu dans un document ultérieur (colonne comparative) — peut être une valeur retraitée",
    "k": "calculé depuis des composantes publiées, chacune citée",
    "m": "calculé — rapport entre deux chiffres relevés de la même période",
}
_STATUT_RELEVE = {"publie": "p", "lu_dans_document_ulterieur_comparatif": "c",
                  "calcule_depuis_composantes_publiees": "k"}

UNITES = {"KMAD": "milliers de DH", "MMAD": "millions de DH", "MDH": "millions de DH",
          "milliards MAD": "milliards de DH", "actions": "actions", "DH par action": "DH par action",
          "DH": "DH"}
# Facteur vers l'unité de la ligne (MDH), pour recouper la valeur et le jeton imprimé.
_VERS_MDH = {"KMAD": 1e-3, "MMAD": 1.0, "MDH": 1.0, "milliards MAD": 1e3}

G_RES, G_BIL, G_FLUX, G_ACT = "Compte de résultat", "Bilan", "Flux de trésorerie", "Par action"
# (clé, groupe, libellé, libellé banque, unité, bouton du graphique, variation ?)
LIGNES = (
    ("chiffre_affaires", G_RES, "Chiffre d'affaires", "Produit net bancaire (PNB)", "MDH", True, True),
    ("ebitda_ajuste", G_RES, "EBITDA ajusté (indicateur de gestion, non audité)", None, "MDH", False, True),
    ("ebe", G_RES, "EBE (ligne des états de synthèse)", "Résultat brut d'exploitation (RBE)", "MDH", False, True),
    ("resultat_exploitation_courant", G_RES, "Résultat d'exploitation courant", None, "MDH", False, True),
    ("resultat_exploitation", G_RES, "Résultat d'exploitation", None, "MDH", True, True),
    ("marge_exploitation", G_RES, "Marge d'exploitation", None, "%", False, False),
    ("resultat_net_ensemble", G_RES, "Résultat net de l'ensemble consolidé", None, "MDH", False, True),
    ("resultat_net_part_groupe", G_RES, "Résultat net part du groupe", None, "MDH", True, True),
    ("marge_nette", G_RES, "Marge nette part du groupe", None, "%", False, False),
    ("interets_minoritaires", G_RES, "Intérêts minoritaires", None, "MDH", False, False),
    ("capitaux_propres_part_groupe", G_BIL, "Capitaux propres part du groupe", None, "MDH", False, True),
    ("dette_nette_publiee", G_BIL, "Dette nette publiée par l'émetteur", None, "MDH", True, False),
    ("dette_nette", G_BIL, "Dette nette calculée par BVC Analyzer", None, "MDH", True, False),
    ("flux_exploitation", G_FLUX, "Flux de trésorerie d'exploitation", None, "MDH", False, False),
    ("flux_investissement", G_FLUX, "Flux de trésorerie d'investissement", None, "MDH", False, False),
    ("nombre_actions", G_ACT, "Nombre d'actions", None, "actions", False, False),
    ("dividende_par_action_propose", G_ACT, "Dividende proposé par action", None, "DH", False, True),
)
# Marges : (numérateur, dénominateur) — résultat ÷ chiffre d'affaires, rien d'autre.
MARGES = {"marge_exploitation": ("resultat_exploitation", "chiffre_affaires"),
          "marge_nette": ("resultat_net_part_groupe", "chiffre_affaires")}
# Les deux dettes nettes se lisent l'une à côté de l'autre.
PENDANTS = {"dette_nette": "dette_nette_publiee", "dette_nette_publiee": "dette_nette"}
# Boutons du graphique quand le libellé de ligne est trop long.
_BOUTON = {"dette_nette_publiee": "Dette nette (émetteur)", "dette_nette": "Dette nette (calcul BVC Analyzer)"}

# Raisons de cellule vide : liste FERMÉE. (motif du relevé → texte publié)
_SANS_OBJET = "Sans objet pour une banque : la dette nette n'y est pas définie."
_RAISONS = (
    (r"^sans objet pour une banque", _SANS_OBJET),
    (r"^non relevé dans ce lot",
     "Non relevé dans ce lot : cette ligne n'a pas encore été lue dans les documents "
     "(ce qui ne veut pas dire qu'elle n'est pas publiée)."),
    (r"non retrouvée dans les pièces téléchargées",
     "Non relevé : aucune ligne des documents téléchargés n'a pu être rattachée à cette grandeur "
     "(pièce non lue ou libellé différent)."),
    (r"^total « part du groupe » non imprimé",
     "Non relevé : le total « part du groupe » n'est pas imprimé dans le document "
     "(somme de lignes du bilan), et il n'a pas été reconstitué."),
    (r"^non publié \(constat",
     "Non relevé : donné comme non publié par un relevé tiers, non reconfirmé par nous dans le document."),
    (r"^EBE comptable",
     "Aucune ligne « EBE » lue dans les états de synthèse ; quand l'émetteur publie un indicateur "
     "de gestion, il figure à la ligne « EBITDA ajusté »."),
    (r"^EBITDA/EBE publié non lu dans ce lot",
     "Non relevé : aucun EBITDA ou EBE publié par l'émetteur n'a été lu pour cette période."),
    (r"^ligne « Dette nette » du tableau consolidé non retrouvée",
     "Non relevé : la ligne « Dette nette » du tableau consolidé n'a pas été retrouvée dans la "
     "colonne de la période."),
    # lot 2 (ADH, CSR, TGCC, MSA)
    (r"^document introuvable",
     "Non relevé : document introuvable, aucun dépôt AMMC de comptes pour cette période."),
    (r"^sans objet : semestre",
     "Sans objet : un dividende se propose au titre d'un exercice, pas d'un semestre."),
    (r"image sans texte",
     "Non relevé : le document déposé est une image sans couche texte, il n'a pas été lu."),
    (r"^tableau des flux au 30/06",
     "Non relevé : pas de tableau des flux publié à cette date (le comparatif du document suivant est celui de fin d'exercice)."),
    (r"^bilan au 30/06",
     "Non relevé : pas de bilan publié à cette date (le comparatif du document suivant est celui de fin d'exercice)."),
    # Trois motifs distincts (relecture #341) : une absence constatée ne se dit que
    # de la ligne qu'elle concerne, et « non lu » ne devient jamais « absent ».
    (r"^(EBE : aucune ligne|aucune ligne.*EBE)",
     "Aucune ligne « EBE » dans les états consolidés de l'émetteur ; quand il publie un indicateur "
     "de gestion, il figure à la ligne « EBITDA ajusté »."),
    (r"^pas de ligne « résultat d'exploitation courant »",
     "Aucune ligne « résultat d'exploitation courant » dans les comptes consolidés de l'émetteur "
     "(présentation aux normes marocaines)."),
    (r"^aucun EBITDA",
     "Non relevé : aucun EBITDA ou EBE publié par l'émetteur n'a été lu pour cette période."),
    (r"^nombre d'actions non imprimé",
     "Non relevé : le document n'imprime pas le nombre d'actions (capital seul, nominal non cité)."),
    (r"colonne du semestre à « - »",
     "Non relevé : le document du semestre laisse cette colonne vide (« - »)."),
    (r"^endettement net publié",
     "Non retenu : l'endettement net publié par l'émetteur porte sur une branche ou sur le social, "
     "sans périmètre consolidé établi."),
    (r"non lu|non relevé|non établi|non repris",
     "Non relevé : cette ligne n'a pas été lue pour cette période (ce qui ne veut pas dire "
     "qu'elle n'est pas publiée)."),
)
RAISON_ABSENTE = "Non relevé : cette grandeur n'a pas été lue pour cette période."
RAISON_TERME = "Non calculé : un des deux termes n'est pas relevé pour cette période."
RAISON_BASE = "Non calculé (n.s.) : chiffre d'affaires nul ou négatif, un pourcentage n'a pas de sens."

R_COMPARATIF = ("Pièce d'origine de la période non exploitée : valeur lue dans la colonne comparative "
                "d'un document ultérieur, donc peut-être retraitée.")
R_PRESUME = "Périmètre consolidé présumé : il n'est pas écrit en toutes lettres sur la page."
R_SOCIAL = "Comptes sociaux, et non consolidés."
R_SIGNE = ("Signe à relire : le relevé signale un nombre sans signe accolé sur la ligne "
           "(charge, ou colonne à relire).")


class ReleveInvalide(ValueError):
    """Le relevé sort du contrat connu : on s'arrête plutôt que de publier à l'aveugle."""


# ─────────────────────────── utilitaires ───────────────────────────

def _nombre(x):
    """36699.0 → 36699 (JSON plus court, même valeur)."""
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def _fr(x, d=1) -> str:
    s = f"{abs(x):,.{d}f}".replace(",", " ").replace(".", ",")
    if d and s.endswith("," + "0" * d):
        s = s[: -d - 1]
    return ("−" if x < 0 else "") + s


def marge(num, den):
    """Résultat ÷ chiffre d'affaires × 100, ou None (terme absent, base ≤ 0)."""
    if num is None or den is None or den <= 0:
        return None
    return round(num / den * 100, 1) + 0.0


def variation(avant, apres):
    """Variation en %, "ns" si la base est nulle ou négative, None si un terme manque."""
    if avant is None or apres is None:
        return None
    if avant <= 0:
        return "ns"
    return round((apres / avant - 1) * 100, 1) + 0.0


# Jargon interne jamais publié : numéro de règle (R11), nom de registre ou de
# fichier de configuration, pictogramme (relecture #341).
JARGON = re.compile(r"\bR\d{1,2}\b|bvc_config|SPLITS|HISTORIQUE_ACTIONS|[\u2600-\u27BF\U0001F300-\U0001FAFF]")


def raison_publique(texte: str) -> str:
    for motif, public in _RAISONS:
        if re.search(motif, texte or ""):
            return public
    raise ReleveInvalide(f"raison de cellule vide inconnue, à ajouter à _RAISONS : {texte!r}")


def _public(texte: str, ou: str) -> str:
    """Un texte du relevé publié tel quel : jamais de renvoi au site tiers ni de nom de champ."""
    t = re.sub(r"\s+", " ", str(texte)).strip()
    if "ms-screener" in t.lower() or "`" in t or JARGON.search(t):
        raise ReleveInvalide(f"{ou} : texte non publiable tel quel ({t[:80]!r})")
    return t


def citation_courte(texte: str | None) -> str | None:
    """La ligne de la valeur elle-même. Le relevé ajoute parfois, après « || », la
    ligne qui a servi à identifier la colonne : elle reste dans le relevé détaillé."""
    if not texte:
        return None
    t = re.sub(r"\s+", " ", texte.split(" || ")[0]).strip()
    if len(t) <= CITATION_MAX:
        return t
    return t[:CITATION_MAX].rsplit(" ", 1)[0] + " […]"


def _jeton(texte: str):
    """« 1 012 305 », « 2.378,5 », « 1,179 milliard MAD » → nombre (valeur absolue), ou None."""
    s = re.sub(r"[^\d,.]", "", str(texte).replace(" ", "").replace("\xa0", ""))
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):
        s = s.replace(".", "")
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _periode(cle: str, p: dict) -> dict:
    an = cle[-4:]
    lib = an if p.get("type") == "annuel" else f"S1 {an}"
    return {"cle": cle, "libelle": lib, "cloture": p.get("cloture")}


def _splits_apres(ticker: str, cloture: str | None) -> list[dict]:
    return [s for s in C.SPLITS.get(ticker, []) if cloture and s["date"] > cloture]


# ─────────────────────────── construction ───────────────────────────

class _Tables:
    """Documents et textes factorisés : un indice par valeur distincte."""

    def __init__(self, documents: dict):
        self._docs_releve = documents
        self.documents: list[dict] = []
        self._i_doc: dict[str, int] = {}
        self.textes: list[str] = []
        self._i_txt: dict[str, int] = {}

    def doc(self, cle: str, ou: str) -> int:
        if cle not in self._i_doc:
            d = self._docs_releve.get(cle)
            if not d or not str(d.get("url", "")).startswith("https://"):
                raise ReleveInvalide(f"{ou} : document {cle!r} absent de la table ou sans URL https")
            self._i_doc[cle] = len(self.documents)
            doc = {"u": d["url"]}
            if (d.get("fichier") or cle) != unquote(d["url"].rsplit("/", 1)[-1]):
                doc["f"] = d.get("fichier") or cle        # sinon le nom se lit dans l'URL
            self.documents.append(doc)
        return self._i_doc[cle]

    def txt(self, texte: str) -> int:
        if texte not in self._i_txt:
            self._i_txt[texte] = len(self.textes)
            self.textes.append(texte)
        return self._i_txt[texte]


def _source(c: dict, t: _Tables, ou: str) -> dict:
    """document, page, citation, jeton imprimé — exigés pour toute valeur lue."""
    if not c.get("document") or not c.get("page") or not c.get("citation"):
        raise ReleveInvalide(f"{ou} : valeur sans document, page ou citation")
    out = {"d": t.doc(c["document"], ou), "p": c["page"], "c": citation_courte(c["citation"])}
    if c.get("valeur_source") is not None:
        out["i"] = re.sub(r"\s+", " ", str(c["valeur_source"])).strip()
    return out


def _reserves(cle: str, c: dict, t: _Tables, ticker: str, cloture: str | None, ou: str) -> dict:
    """{"r": réserves, "o": précisions} — indices de textes ; clés absentes si vides.

    Réserve = ce qui rend la valeur incertaine (lue dans un comparatif, périmètre
    présumé, signe ou unité à relire, arrondi, division du nominal). Précision =
    ce qui dit ce qu'est le chiffre (nature de l'indicateur, convention de signe,
    façon dont la colonne a été identifiée)."""
    r: list[str] = []
    o: list[str] = []
    # Une valeur lue dans un comparatif le dit toujours : par la note du relevé
    # quand elle en parle, sinon par la réserve générique.
    n = _public(c["note"], ou) if c.get("note") else ""
    dit_comparatif = "comparati" in n.lower()
    if c.get("statut") == "lu_dans_document_ulterieur_comparatif" and not dit_comparatif:
        r.append(R_COMPARATIF)
    if n:
        (r if dit_comparatif else o).append(n[0].upper() + n[1:] + ("" if n.endswith(".") else "."))
    if c.get("nature"):
        n = _public(c["nature"], ou)
        o.append("Nature : " + n + ".")
    if c.get("reserve"):
        r.append(_public(c["reserve"], ou).rstrip(".") + ".")
    if c.get("perimetre") == "consolide_presume":
        r.append(R_PRESUME)
    elif c.get("perimetre") == "social":
        r.append(R_SOCIAL)
    if c.get("signe_a_verifier"):
        r.append(R_SIGNE)
    if c.get("unite_note"):
        r.append("Unité à relire (réserve du relevé) : " + _public(c["unite_note"], ou) + ".")
    if c.get("convention_signe"):
        o.append("Convention de signe : " + _public(c["convention_signe"], ou) + ".")
    # La valeur du relevé doit se lire sur la ligne citée, à l'unité près.
    f = _VERS_MDH.get(c.get("unite_source"))
    j = _jeton(c["valeur_source"]) if c.get("valeur_source") is not None else None
    if f and j is not None and c.get("valeur_mdh") is not None:
        lu, v = j * f, abs(c["valeur_mdh"])
        if abs(lu - v) > max(1e-6, 5e-7 * v):
            r.append(f"Arrondi à relire : la ligne citée imprime {_fr(lu, 3)} MDH, "
                     f"le relevé retient {_fr(v, 3)}.")
    # R11 : un nombre d'actions ou un montant par action d'avant une division du
    # nominal ne se rapporte pas à un cours postérieur sans ajustement.
    if cle in ("nombre_actions", "dividende_par_action_propose"):
        for s in _splits_apres(ticker, cloture):
            d = s["date"].split("-")
            r.append(f"Avant la division du nominal du {d[2]}/{d[1]}/{d[0]} (1 action → {s['ratio']}, "
                     "registre des opérations sur titres) : à ajuster avant tout rapprochement avec un cours postérieur.")
    return {k: [t.txt(x) for x in xs] for k, xs in (("r", r), ("o", o)) if xs}


def _formule(c: dict) -> tuple[str, dict[str, str]]:
    """(formule lisible, signe par composante) — à partir de la formule du relevé."""
    brute = str(c.get("formule") or "")
    tete = brute.split("—")[0]
    termes = re.findall(r"([+-])\s*(\w+)", tete)
    comps = c.get("composantes") or {}
    incl = c.get("composantes_incluses") or {}
    if termes and all(k in comps for _, k in termes) and re.fullmatch(r"(\s*[+-]\s*\w+)+\s*", tete):
        signes = {k: ("+" if s == "+" else "−") for s, k in termes}
        txt = " ".join(f"{signes[k]} {incl.get(k, k.replace('_', ' '))}" for _, k in termes).lstrip("+ ")
        excl = c.get("composantes_exclues") or []
        if excl:
            txt += ". Non inclus : " + ", ".join(excl)
        txt += (". Calcul propre à BVC Analyzer, à ne pas confondre avec la dette nette "
                "publiée par l'émetteur.")
        return txt, signes
    return brute, {}


def _cellule(cle: str, c: dict | None, t: _Tables, ticker: str, cloture: str | None, ou: str,
             unite_ligne: str) -> dict:
    if c is None:
        return {"n": t.txt(RAISON_ABSENTE)}
    v = c.get("valeur_mdh")
    if v is None:
        return {"n": t.txt(raison_publique(c.get("raison_null")))}
    if c.get("statut") not in _STATUT_RELEVE:
        raise ReleveInvalide(f"{ou} : statut inconnu {c.get('statut')!r}")
    out: dict = {"v": _nombre(v), "s": _STATUT_RELEVE[c["statut"]]}
    if c.get("composantes"):
        if out["s"] != "k":
            raise ReleveInvalide(f"{ou} : composantes sans statut « calculé »")
        formule, signes = _formule(c)
        out["f"] = t.txt(_public(formule, ou))
        incl = c.get("composantes_incluses") or {}
        out["k"] = []
        for k, cv in c["composantes"].items():
            if cv.get("valeur_mdh") is None:
                raise ReleveInvalide(f"{ou}/{k} : composante sans valeur")
            comp = {"l": t.txt(incl.get(k, k.replace("_", " ")))}
            if k in signes:
                comp["sg"] = signes[k]
            if unite_ligne == "MDH":
                comp["v"] = _nombre(cv["valeur_mdh"])
            comp.update(_source(cv, t, f"{ou}/{k}"))
            comp.update(_reserves(k, cv, t, ticker, cloture, f"{ou}/{k}"))
            out["k"].append(comp)
    else:
        out.update(_source(c, t, ou))
        if c.get("unite_source"):
            if c["unite_source"] not in UNITES:
                raise ReleveInvalide(f"{ou} : unité imprimée inconnue {c['unite_source']!r}")
            out["u"] = c["unite_source"]
        if c.get("referentiel") and not c.get("referentiel_source"):
            out["rf"] = c["referentiel"]
    out.update(_reserves(cle, c, t, ticker, cloture, ou))
    return out


def construire(releve: dict) -> dict | None:
    """Le fichier compact d'un titre, ou None si le relevé ne porte aucune valeur."""
    if releve.get("schema") != SCHEMA_RELEVE:
        raise ReleveInvalide(f"schéma de relevé inattendu : {releve.get('schema')!r}")
    if releve.get("unite") != "MDH":
        raise ReleveInvalide(f"unité de relevé inattendue : {releve.get('unite')!r}")
    ticker = releve["ticker"]
    banque = releve.get("archetype") == "bank"
    t = _Tables(releve.get("documents") or {})
    connues = {l[0] for l in LIGNES}
    vues, presentes = {}, set()
    for k, p in releve["periodes"].items():
        if p.get("type") not in ("annuel", "semestriel"):
            raise ReleveInvalide(f"{ticker} {k} : type de période inconnu {p.get('type')!r}")
        inconnues = set(p["donnees"]) - connues
        if inconnues:
            raise ReleveInvalide(f"{ticker} {k} : grandeur(s) inconnue(s) {sorted(inconnues)}, "
                                 "à déclarer dans LIGNES")
        presentes |= set(p["donnees"])
    for nom, typ in (("annuel", "annuel"), ("semestriel", "semestriel")):
        pers = sorted(((k, p) for k, p in releve["periodes"].items() if p.get("type") == typ),
                      key=lambda kp: kp[1].get("cloture") or kp[0])
        cellules = {}
        for cle, _g, _lib, _libb, unite, _gr, _var in LIGNES:
            if cle in MARGES or cle not in presentes:
                continue
            cellules[cle] = [_cellule(cle, p["donnees"].get(cle), t, ticker, p.get("cloture"),
                                      f"{ticker} {k} {cle}", unite) for k, p in pers]
        vues[nom] = {"periodes": [_periode(k, p) for k, p in pers], "cellules": cellules}

    # Lignes sans objet partout (dette nette d'une banque) : retirées.
    i_so = t._i_txt.get(_SANS_OBJET)
    for cle in list(vues["annuel"]["cellules"]):
        if all(c.get("n") == i_so and i_so is not None
               for v in vues.values() for c in v["cellules"][cle]):
            for v in vues.values():
                del v["cellules"][cle]

    # Calculs : marges, puis variations d'une période à la même période précédente.
    varier = {l[0] for l in LIGNES if l[6]}
    for v in vues.values():
        cel = v["cellules"]
        for cle, (num, den) in MARGES.items():
            if num not in cel or den not in cel:
                continue
            ligne = []
            for a, b in zip(cel[num], cel[den]):
                m = marge(a.get("v"), b.get("v"))
                if m is not None:
                    ligne.append({"v": _nombre(m), "s": "m"})
                else:
                    ligne.append({"n": t.txt(RAISON_TERME if a.get("v") is None or b.get("v") is None
                                             else RAISON_BASE)})
            cel[cle] = ligne
        annee = {int(p["cle"][-4:]): i for i, p in enumerate(v["periodes"])}
        for cle in varier & set(cel):
            for an, i in annee.items():
                if an - 1 in annee:
                    g = variation(cel[cle][annee[an - 1]].get("v"), cel[cle][i].get("v"))
                    if g is not None:
                        cel[cle][i]["g"] = _nombre(g)
        v["cellules"] = {l[0]: cel[l[0]] for l in LIGNES if l[0] in cel}      # ordre d'affichage
        vals = [c for cle, cs in cel.items() if cle not in MARGES for c in cs]
        docs = {s["d"] for c in vals for s in [c, *c.get("k", [])] if "d" in s}
        v["couverture"] = {"relevees": sum("v" in c for c in vals), "cellules": len(vals),
                           "documents": len(docs)}

    if not any(v["couverture"]["relevees"] for v in vues.values()):
        return None
    lignes = []
    for cle, groupe, lib, lib_banque, unite, graphique, _var in LIGNES:
        if cle not in vues["annuel"]["cellules"]:
            continue
        libelle = lib_banque if (banque and lib_banque) else lib
        l = {"cle": cle, "libelle": libelle, "groupe": groupe, "unite": unite}
        if graphique:
            l["graphique"] = _BOUTON.get(cle, libelle)
        if cle in MARGES:
            l["calcul"] = {"num": MARGES[cle][0], "den": MARGES[cle][1]}
        if PENDANTS.get(cle) in vues["annuel"]["cellules"]:
            l["pendant"] = PENDANTS[cle]
        lignes.append(l)
    lues = [c for v in vues.values() for cs in v["cellules"].values() for c in cs if "u" in c]
    unites = sorted({c["u"] for c in lues})
    # L'unité imprimée la plus fréquente d'un document se dit une fois, sur le document.
    for i, doc in enumerate(t.documents):
        us = [c["u"] for c in lues if c["d"] == i]
        if us:
            doc["un"] = max(sorted(set(us)), key=us.count)
    for c in lues:
        if c["u"] == t.documents[c["d"]].get("un"):
            del c["u"]
    statuts = sorted({c["s"] for v in vues.values() for cs in v["cellules"].values() for c in cs if "s" in c})
    return {
        "schema": SCHEMA, "ticker": ticker, "nom": releve.get("nom"),
        "archetype": releve.get("archetype"), "unite": "MDH",
        "perimetre": releve.get("perimetre_principal"),
        "releve": f"datasets/etats_financiers/{ticker}.json",
        "statuts": {s: STATUTS[s] for s in statuts},
        "unites": {u: UNITES[u] for u in unites},
        "documents": t.documents, "textes": t.textes, "lignes": lignes, "vues": vues,
    }


def serialiser(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def generer(releves: Path | None = None) -> dict[str, str]:
    """{nom de fichier: contenu} pour tous les relevés, index compris."""
    src = Path(releves) if releves else RELEVES
    sorties, titres = {}, []
    for f in sorted(src.glob("*.json")):
        compact = construire(json.loads(f.read_text(encoding="utf-8")))
        if compact is None:
            continue
        sorties[f"{compact['ticker']}.json"] = serialiser(compact)
        titres.append(compact["ticker"])
    sorties["index.json"] = serialiser({
        "schema": "etats_publies_index/1",
        "_lecture": "Titres dont l'historique des états financiers est publié "
                    "(datasets/etats_publies/<TICKER>.json), produit par pipeline/etats_publies.py.",
        "titres": titres})
    return sorties


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verifier", action="store_true",
                    help="n'écrit rien ; échoue si un fichier commité diffère de la sortie du générateur")
    a = ap.parse_args(argv)
    sorties = generer()
    ecarts = []
    if a.verifier:
        for nom, contenu in sorties.items():
            f = SORTIE / nom
            if not f.exists() or f.read_text(encoding="utf-8") != contenu:
                ecarts.append(nom)
        ecarts += [f.name for f in SORTIE.glob("*.json") if f.name not in sorties]
    else:
        SORTIE.mkdir(parents=True, exist_ok=True)
        for nom, contenu in sorties.items():
            (SORTIE / nom).write_text(contenu, encoding="utf-8")
        # Un fichier dont le relevé a disparu n'est pas supprimé ici (on archive,
        # on ne supprime pas) : il est signalé, et l'index ne le cite plus.
        ecarts += [f.name for f in SORTIE.glob("*.json") if f.name not in sorties]
    for nom, contenu in sorted(sorties.items()):
        o = len(contenu.encode("utf-8"))
        print(f"  {nom:<12} {o:>6} octets" + ("  ⚠ au-dessus de l'objectif" if o > POIDS_MAX else ""))
    if ecarts:
        print(("À RÉGÉNÉRER (python3 pipeline/etats_publies.py) : " if a.verifier
               else "SANS RELEVÉ, à archiver à la main : ") + ", ".join(sorted(ecarts)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
