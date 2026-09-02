"""
Pseudonymisation des membres du groupe WhatsApp.

POURQUOI
────────
Le dépôt est PUBLIC. Deux fichiers de sortie y sont versionnés depuis le
05/06/2026 en portant les noms WhatsApp réels de 2 013 personnes, associés à
un jugement de compétence financière (taux de réussite, alpha, régularité) et
à leur influence dans le groupe. Deux entrées étaient des numéros de téléphone
en clair.

Ces personnes ont écrit dans un groupe privé. Elles n'ont pas consenti à être
notées et publiées. Le moteur, lui, n'a jamais eu besoin de leur identité : il
lui suffit de savoir que « le membre 417 » a un bon historique pour pondérer
ses messages. L'identité ne servait à rien — elle n'était que du risque.

CE QUE CE MODULE GARANTIT
─────────────────────────
1. **Stabilité.** Le même membre reçoit le même identifiant à chaque
   recalcul. Sans quoi tout l'historique et le backtest deviendraient
   incomparables d'un run à l'autre.
2. **Non-inversibilité.** L'identifiant n'encode AUCUNE information sur la
   personne — ni son ancienneté, ni son volume, ni son classement.
3. **Croissance.** Un nouveau membre reçoit un nouveau numéro sans déplacer
   ceux des autres.

⚠️ POURQUOI PAS UNE NUMÉROTATION PAR DATE D'ARRIVÉE
────────────────────────────────────────────────────
L'idée est naturelle et elle a été écartée pour trois raisons :

- **Elle ré-identifie.** Dans un groupe où les gens se connaissent, l'ancienneté
  est un signalement puissant : « M0003 » ne peut être qu'un des tout premiers
  membres, et ils sont trois. Le numéro devient un indice au lieu d'un écran.
- **Elle est reconstructible.** Quiconque possède l'historique du groupe —
  c'est-à-dire chacun de ses 2 013 membres — peut refaire l'ordre d'arrivée et
  donc la table de correspondance entière. Le pseudonyme ne protège alors plus
  personne.
- **La date d'arrivée n'est pas connue.** WhatsApp ne journalise « a rejoint »
  que pour une partie des membres ; ceux présents à la création du groupe et
  ceux ajoutés avant le début de l'export n'ont aucune date. On classerait sur
  une donnée absente pour la majorité.

L'ordre retenu est donc tiré du condensat salé : il est stable, reproductible,
et ne veut rien dire. C'est exactement ce qu'on attend d'un pseudonyme.

⚠️ LE SEL EST UN SECRET
───────────────────────
Sans sel, un condensat se casse par force brute : les noms des membres sont
devinables, il suffit de les hacher tous et de comparer. Le sel est tiré au
hasard une seule fois et conservé **hors du dépôt**, avec la table de
correspondance, dans `data/pseudonymes.json` — répertoire déjà ignoré par git.

⚠️ CE MODULE NE RÉPARE PAS LE PASSÉ. Les noms restent dans l'historique git
tant qu'il n'a pas été réécrit. Voir ERRORS.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import unicodedata
from pathlib import Path
from typing import Dict

# Hors dépôt : `data/` est ignoré par git (cf. .gitignore).
CHEMIN_TABLE = Path(__file__).resolve().parent.parent / "data" / "pseudonymes.json"

PREFIXE = "M"
# Reconnaît un identifiant déjà attribué — rend le nettoyage relançable.
DEJA_PSEUDO = re.compile(r"m\d{4,}")
LARGEUR = 4  # M0001 … M9999 ; au-delà le numéro s'allonge naturellement


def _normaliser(nom: str) -> str:
    """Ramène un nom à une forme stable.

    WhatsApp écrit le même membre de plusieurs façons selon qu'il est dans les
    contacts ou non : espaces insécables, casse variable, accents composés
    différemment. Sans normalisation, la même personne recevrait deux
    identifiants et son historique serait coupé en deux.
    """
    n = unicodedata.normalize("NFKC", str(nom or ""))
    n = n.replace(" ", " ").replace(" ", " ").replace("‎", "")
    n = re.sub(r"\s+", " ", n).strip().casefold()
    return n


class TablePseudonymes:
    """Table de correspondance nom → pseudonyme, persistée hors du dépôt."""

    def __init__(self, chemin: Path | None = None):
        self.chemin = Path(chemin) if chemin else CHEMIN_TABLE
        self._sel: str = ""
        self._table: Dict[str, str] = {}
        self._charger()

    # ── persistance ──────────────────────────────────────────────────────
    def _charger(self) -> None:
        if self.chemin.exists():
            donnees = json.loads(self.chemin.read_text(encoding="utf-8"))
            self._sel = donnees.get("sel", "")
            self._table = dict(donnees.get("table", {}))
        if not self._sel:
            # Tiré une seule fois dans la vie du projet. Le perdre revient à
            # renuméroter tout le monde et à casser la comparabilité.
            self._sel = secrets.token_hex(16)

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        charge = {
            "_avertissement": (
                "SECRET — ne jamais commiter. Contient les noms réels des "
                "membres et le sel qui rend les pseudonymes stables."
            ),
            "sel": self._sel,
            "table": self._table,
        }
        # Écriture atomique puis permissions restreintes : le fichier porte
        # l'identité de 2 000 personnes.
        tmp = self.chemin.with_suffix(".tmp")
        tmp.write_text(json.dumps(charge, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.chemin)
        try:
            os.chmod(self.chemin, 0o600)
        except OSError:
            pass  # systèmes de fichiers sans permissions POSIX

    # ── attribution ──────────────────────────────────────────────────────
    def _rang(self, cle: str) -> str:
        return hashlib.sha256((self._sel + "|" + cle).encode("utf-8")).hexdigest()

    def pseudonyme(self, nom: str) -> str:
        """Renvoie le pseudonyme stable d'un membre, en le créant au besoin."""
        cle = _normaliser(nom)
        if not cle:
            return f"{PREFIXE}0000"  # auteur absent ou message système
        if DEJA_PSEUDO.fullmatch(cle):
            # Le script de nettoyage est relançable, et il l'a été : sans cette
            # garde, un second passage prend les pseudonymes du premier pour de
            # nouveaux membres et double la table (1 994 → 3 988 le 02/09).
            # Un pseudonyme est déjà le résultat voulu : on le rend tel quel.
            return cle.upper()
        if cle not in self._table:
            self._table[cle] = f"{PREFIXE}{len(self._table) + 1:0{LARGEUR}d}"
        return self._table[cle]

    def amorcer(self, noms) -> None:
        """Attribue leurs numéros à un lot de membres d'un coup.

        L'ordre d'attribution suit le condensat salé, PAS l'ordre d'arrivée du
        lot : deux exécutions sur le même corpus donnent la même table, et
        l'ordre ne raconte rien sur les personnes. Les membres déjà connus
        gardent leur numéro — c'est ce qui rend la table stable dans le temps.
        """
        nouveaux = {_normaliser(n) for n in noms}
        nouveaux = {c for c in nouveaux
                    if c and c not in self._table and not DEJA_PSEUDO.fullmatch(c)}
        for cle in sorted(nouveaux, key=self._rang):
            self._table[cle] = f"{PREFIXE}{len(self._table) + 1:0{LARGEUR}d}"

    def __len__(self) -> int:
        return len(self._table)


def pseudonymiser_colonne(serie, table: TablePseudonymes):
    """Remplace une colonne d'auteurs par leurs pseudonymes.

    Amorce d'abord la table sur toute la colonne pour que l'attribution suive
    le condensat et non l'ordre des lignes du fichier — sinon le numéro
    trahirait le classement, qui est précisément ce qu'on publie.
    """
    table.amorcer(serie.dropna().unique())
    return serie.map(lambda n: table.pseudonyme(n))
