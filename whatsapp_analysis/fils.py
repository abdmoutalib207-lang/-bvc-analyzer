"""
Découpage du corpus WhatsApp en fils de discussion.

POURQUOI
────────
Le pipeline comptait les messages qui **contiennent** le code d'un titre. Mais
une conversation ne fonctionne pas comme ça : quelqu'un écrit « ADI ? », et les
quinze messages suivants parlent d'ADI sans jamais le nommer. Un lecteur humain
suit le fil ; notre compteur jetait tout ce qui ne répétait pas le code.

Mesuré sur les 919 372 messages (2020-09 → 2026-07) :

    messages exploitables      48 832  →  591 430     (×12,1)
    part du corpus utilisée       5 %  →      64 %
    taille médiane d'un fil                11 messages

    titre    mentions/jour    fil/jour
    ADI            4      →      49
    RDS            4      →      58
    titres avec ≥10 messages/jour :  0  →  15

Le dernier chiffre est celui qui compte : **aucun** titre n'avait assez de
matière pour un sentiment quotidien, **quinze** en ont. L'obstacle n'était pas
la taille du corpus, c'était la façon de le compter.

Idée d'Abd Moutalib, mesurée et confirmée le 03/09/2026.

⚠️ Le chiffrage ci-dessus vient d'un brouillon qui ne lisait QUE les lignes
horodatées. Ce module lit les messages entiers, continuations comprises —
314 346 lignes de plus, dont 19 530 messages dont le ticker n'apparaissait
qu'en deuxième ligne. Il trouve donc davantage : **35 811 fils et 608 255
messages rattachés**, contre 30 609 et 591 430 au brouillon. L'écart est du
bon côté, et il ne vient pas de TIM (3 fils).

COMMENT UN FIL SE FERME
───────────────────────
Deux signaux, et deux seulement :

1. **Quelqu'un cite un autre titre.** La conversation a changé de sujet, on
   n'attribue plus à l'ancien.
2. **Le silence.** Au-delà de `TROU_DEFAUT` minutes sans message, la
   discussion est finie ; ce qui suit est une nouvelle conversation.

⚠️ LES DEUX LIMITES, À CONNAÎTRE AVANT D'EN FAIRE UN SIGNAL PUBLIÉ
─────────────────────────────────────────────────────────────────
- **Le seuil est arbitraire.** 10 min donne ×12,1 ; 30 min donne ×15,1. Rien
  dans les données ne désigne le bon. Il doit être validé à l'œil sur des fils
  réels avant d'alimenter quoi que ce soit de publié.
- **Un fil peut dériver sans citer d'autre titre.** On parle d'ADI, puis de la
  météo, sans transition explicite. Le découpage attribuerait la météo à ADI.
  C'est la faiblesse structurelle de la méthode, et aucun réglage ne l'enlève —
  seule une relecture humaine la mesure.

C'est pourquoi `echantillonner()` existe : sortir des fils à relire est une
étape du plan, pas un ornement.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence

from whatsapp_analysis.config import BVC_TICKERS

# Format d'export WhatsApp iOS : [JJ/MM/AAAA HH:MM:SS] Auteur: texte
#
# ⚠️ WhatsApp insère des marques Unicode INVISIBLES en tête de certaines lignes
# (U+200E left-to-right mark, U+200F right-to-left, U+202A…U+202E). Ancrer le
# motif sur « ^\[ » sans les enlever fait manquer ces lignes : elles sont alors
# recollées au message précédent comme s'il s'agissait d'une continuation — et
# le NOM DE L'AUTEUR se retrouve dans le corps du message, où la
# pseudonymisation ne le cherche pas. Repéré le 03/09/2026 sur le premier
# échantillon relu : « Karim Doe Groupe Test » en clair au milieu d'un texte.
# Un corpus arabe/darija en contient beaucoup : le sens d'écriture change.
MARQUES_INVISIBLES = str.maketrans("", "", "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff")
LIGNE = re.compile(r"^\[(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.*)$")
HORODATAGE = "%d/%m/%Y %H:%M:%S"

TROU_DEFAUT = 10  # minutes de silence qui ferment un fil

# ⚠️ 81 tickers ici contre 80 dans `bvc_config.TICKERS_ALL` : l'écart est TIM,
# radié le 10/06/2024. C'est VOULU. La radiation interdit de publier une note
# sur TIM aujourd'hui ; elle n'efface pas les conversations de 2020 à 2024, qui
# restent de la matière d'apprentissage légitime. Ne pas « corriger » cet écart
# sans mesurer ce qu'on perd.
_RX_TICKERS = re.compile(
    r"\b(" + "|".join(sorted(set(BVC_TICKERS), key=len, reverse=True)) + r")\b"
)


@dataclass
class Message:
    ts: datetime
    auteur: str
    texte: str
    tickers: frozenset = field(default_factory=frozenset)


@dataclass
class Fil:
    """Une conversation continue portant sur un seul titre."""

    ticker: str
    messages: List[Message]

    @property
    def debut(self) -> datetime:
        return self.messages[0].ts

    @property
    def fin(self) -> datetime:
        return self.messages[-1].ts

    @property
    def seance(self) -> str:
        """Date de séance à laquelle rattacher le fil — celle de son OUVERTURE.

        Un fil ouvert à 23h50 et qui déborde sur le lendemain appartient à la
        séance où il a commencé : c'est l'information qui circulait ce jour-là.
        """
        return self.debut.strftime("%Y-%m-%d")

    @property
    def auteurs(self) -> set:
        return {m.auteur for m in self.messages}

    def __len__(self) -> int:
        return len(self.messages)


def lire_corpus(chemin: Path | str) -> Iterator[Message]:
    """Lit un export WhatsApp ligne à ligne, sans tout charger en mémoire.

    Les lignes de continuation d'un message multi-lignes n'ont pas
    d'horodatage : elles sont rattachées au message précédent plutôt que
    jetées, sinon la moitié d'un message long disparaît.
    """
    courant: Message | None = None
    with open(chemin, encoding="utf-8", errors="ignore") as f:
        for ligne in f:
            ligne = ligne.translate(MARQUES_INVISIBLES)
            m = LIGNE.match(ligne)
            if m:
                if courant is not None:
                    yield courant
                try:
                    ts = datetime.strptime(m.group(1), HORODATAGE)
                except ValueError:
                    courant = None
                    continue
                texte = m.group(3)
                courant = Message(
                    ts=ts,
                    auteur=m.group(2).strip(),
                    texte=texte,
                    tickers=frozenset(_RX_TICKERS.findall(texte)),
                )
            elif courant is not None:
                suite = ligne.rstrip("\n")
                courant.texte += "\n" + suite
                courant.tickers |= frozenset(_RX_TICKERS.findall(suite))
    if courant is not None:
        yield courant


def decouper_en_fils(
    messages: Iterable[Message], trou_minutes: int = TROU_DEFAUT
) -> List[Fil]:
    """Regroupe les messages en fils attribués à un titre.

    Un fil s'ouvre sur un message citant EXACTEMENT UN titre — citer deux
    titres dans la même phrase (« j'arbitre ADI contre RDS ») ne désigne pas un
    sujet unique, on ne l'utilise pas comme amorce.

    Il se poursuit tant qu'aucun autre titre n'est cité et que le silence reste
    sous `trou_minutes`. Les messages antérieurs à l'amorce ne sont pas
    rattachés : on ne sait pas de quoi ils parlaient.
    """
    msgs: Sequence[Message] = list(messages)
    trou = timedelta(minutes=trou_minutes)
    fils: List[Fil] = []

    i = 0
    while i < len(msgs):
        if len(msgs[i].tickers) != 1:
            i += 1
            continue

        cible = next(iter(msgs[i].tickers))
        bloc = [msgs[i]]
        precedent = msgs[i].ts
        j = i + 1
        while j < len(msgs):
            suivant = msgs[j]
            if suivant.ts - precedent > trou:
                break                                   # la discussion s'est arrêtée
            if suivant.tickers and cible not in suivant.tickers:
                break                                   # on parle d'autre chose
            bloc.append(suivant)
            precedent = suivant.ts
            j += 1

        fils.append(Fil(ticker=cible, messages=bloc))
        i = j if j > i else i + 1

    return fils


def echantillonner(
    fils: Sequence[Fil],
    n: int,
    plafond_auteur: float = 0.20,
    graine: int = 20260903,
) -> List[Fil]:
    """Tire `n` fils en limitant le poids de chaque auteur.

    ⚠️ Sans plafond, l'échantillon reflète cinq personnes et non le marché :
    mesuré le 03/09, les 5 auteurs les plus actifs écrivent **35,6 %** du corpus
    et les 15 premiers **50,3 %**. Un modèle entraîné là-dessus apprendrait leur
    style d'écriture.

    Le plafond porte sur l'auteur qui OUVRE le fil — c'est lui qui a introduit
    le sujet, et donc lui dont le style domine la conversation qui suit.
    """
    if n <= 0 or not fils:
        return []

    maxi = max(1, int(n * plafond_auteur))
    tirage = list(fils)
    random.Random(graine).shuffle(tirage)

    retenus: List[Fil] = []
    compte: dict = {}
    # Deux passes : on respecte le plafond, puis on complète si le plafond a
    # laissé l'échantillon incomplet — mieux vaut un échantillon plein
    # légèrement déséquilibré qu'un échantillon trop petit pour conclure.
    for strict in (True, False):
        for fil in tirage:
            if len(retenus) >= n:
                break
            if fil in retenus:
                continue
            a = fil.messages[0].auteur
            if strict and compte.get(a, 0) >= maxi:
                continue
            retenus.append(fil)
            compte[a] = compte.get(a, 0) + 1
        if len(retenus) >= n:
            break

    return retenus
