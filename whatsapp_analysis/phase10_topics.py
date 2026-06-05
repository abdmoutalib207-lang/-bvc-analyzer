"""
Phase 10 — Topic Modeling & Détection de Signaux Faibles
LDA sur le corpus de messages WhatsApp (FR/AR/Darija/Arabizi)
"""
from __future__ import annotations

import logging
import re
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# STOPWORDS MULTILINGUES (FR + AR + Darija)
# ─────────────────────────────────────────────────────────────

STOPWORDS_FR = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "en", "à", "au", "aux",
    "il", "elle", "ils", "elles", "je", "tu", "nous", "vous", "on", "que", "qui",
    "ce", "cette", "ces", "dans", "sur", "par", "pour", "avec", "sans", "mais",
    "ou", "donc", "car", "si", "ne", "pas", "plus", "bien", "très", "aussi",
    "même", "tout", "toujours", "jamais", "encore", "déjà", "ici", "là", "oui",
    "non", "suis", "est", "sont", "être", "avoir", "fait", "faire", "dit", "dire",
    "voir", "pouvoir", "vouloir", "aller", "venir", "prendre", "savoir", "croire",
    "mon", "ton", "son", "notre", "votre", "leur", "ma", "ta", "sa", "mes", "tes",
    "ses", "nos", "vos", "leurs", "qu", "c", "j", "l", "d", "m", "n", "s", "y",
    "nan", "null", "none", "media", "omitted", "deleted", "message", "https", "http",
    "www", "com", "re", "wa", "wa3", "hh", "hhh", "haha", "lol", "ok", "okay",
}

STOPWORDS_AR = {
    "في", "من", "إلى", "على", "عن", "مع", "هذا", "هذه", "ذلك", "التي", "الذي",
    "كان", "كانت", "لا", "ما", "هو", "هي", "هم", "أن", "وأن", "وهو", "وهي",
    "قد", "كل", "أو", "لم", "لن", "ولا", "ولم", "وقد", "كما", "حتى", "إذا",
    "وإذا", "ثم", "بعد", "قبل", "أكثر", "أقل", "يمكن", "يجب",
}

STOPWORDS_DARIJA = {
    "rah", "wah", "ewa", "ewa3", "hada", "hadi", "hadak", "hadchi", "daba", "dyal",
    "bzzaf", "shwya", "3la", "men", "fih", "fiha", "lih", "liha", "3ndi", "3ndek",
    "3ndu", "3ndhom", "khas", "ghir", "ama", "walakin", "bsah", "machi", "bghit",
    "bgha", "kayn", "kayna", "mkayn", "walo", "bla", "b7al", "kima", "3tini",
    "safi", "yallah", "zid", "aji", "sir", "khod", "hna", "lah", "allah",
    "inshallah", "hamdullah", "bismillah", "mashallah", "subhanallah",
}

STOPWORDS_ARABIZI = {
    "wah", "la", "ewa", "daba", "bzzaf", "shwya", "3la", "men", "walakin",
    "machi", "kayn", "safi", "yallah", "zid", "aji", "sir", "inshallah",
    "hamdullah", "mashallah", "hhh", "hhhh", "khok", "khti",
}

STOPWORDS_FINANCE_GENERIC = {
    "marché", "bourse", "action", "titre", "valeur", "cours", "prix", "bvc",
    "casablanca", "maroc", "moroccan", "marocain", "stock", "trading", "trader",
    "invest", "investir", "investissement",
}

ALL_STOPWORDS = (
    STOPWORDS_FR | STOPWORDS_AR | STOPWORDS_DARIJA |
    STOPWORDS_ARABIZI | STOPWORDS_FINANCE_GENERIC
)

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

N_TOPICS = 20
TOP_WORDS_PER_TOPIC = 15
MIN_DF = 5           # min fréquence de document pour un terme
MAX_DF = 0.85        # max fréquence relative
MIN_MESSAGE_LEN = 10  # chars minimum pour inclure dans le corpus
MAX_FEATURES = 8000  # max vocabulary size


# ─────────────────────────────────────────────────────────────
# PREPROCESSING
# ─────────────────────────────────────────────────────────────

def preprocess_message(text: str) -> str:
    """
    Nettoie et normalise un message pour le topic modeling.
    - Supprime URLs, emojis, médias omis
    - Normalise les chiffres arabizi
    - Uniformise les espaces
    """
    if not isinstance(text, str) or len(text) < MIN_MESSAGE_LEN:
        return ""

    # Supprime médias et messages système
    if any(tok in text.lower() for tok in [
        "media omitted", "message deleted", "image omitted",
        "audio omitted", "video omitted", "sticker omitted",
        "<media omitted>",
    ]):
        return ""

    # Supprime URLs
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)

    # Supprime emojis (unicode ranges)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    text = emoji_pattern.sub(" ", text)

    # Normalise les chiffres arabizi (3->ع, 7->ح, etc.) — conserve la forme texte
    arabizi_norm = {
        "3": "3", "7": "7", "9": "9", "2": "2",
    }

    # Supprime ponctuation excessive
    text = re.sub(r"[^\w\s؀-ۿ]", " ", text)

    # Supprime rires répétitifs
    text = re.sub(r"\b(h{2,}|ha{2,}|hh+)\b", "rire", text, flags=re.IGNORECASE)

    # Normalise les espaces multiples
    text = re.sub(r"\s+", " ", text).strip()

    return text.lower()


def build_corpus(
    df: pd.DataFrame,
    language_filter: Optional[List[str]] = None,
) -> Tuple[List[str], pd.Index]:
    """
    Construit le corpus de documents depuis le DataFrame.
    Retourne: (corpus, index_valide)
    """
    if df.empty or "message_text" not in df.columns:
        return [], pd.Index([])

    work = df.copy()
    if language_filter and "language" in work.columns:
        work = work[work["language"].isin(language_filter)]

    texts = []
    valid_idx = []

    for idx, row in work.iterrows():
        processed = preprocess_message(str(row.get("message_text", "")))
        if len(processed) >= MIN_MESSAGE_LEN:
            texts.append(processed)
            valid_idx.append(idx)

    logger.info(f"Corpus: {len(texts)} messages valides sur {len(df)} total")
    return texts, pd.Index(valid_idx)


def build_stop_words_list() -> List[str]:
    """Retourne la liste complète des stopwords."""
    return sorted(ALL_STOPWORDS)


# ─────────────────────────────────────────────────────────────
# LDA
# ─────────────────────────────────────────────────────────────

def train_lda_model(
    corpus: List[str],
    n_topics: int = N_TOPICS,
    max_features: int = MAX_FEATURES,
    min_df: int = MIN_DF,
    max_df: float = MAX_DF,
) -> Tuple[LatentDirichletAllocation, TfidfVectorizer, Any]:
    """
    Entraîne le modèle LDA sur le corpus.
    Retourne: (lda_model, vectorizer, doc_topic_matrix)
    """
    stopwords = build_stop_words_list()

    vectorizer = TfidfVectorizer(
        max_features=max_features,
        min_df=min_df,
        max_df=max_df,
        stop_words=stopwords,
        ngram_range=(1, 2),
        sublinear_tf=True,
        token_pattern=r"(?u)\b[a-zA-Z؀-ۿ][a-zA-Z؀-ۿ0-9_-]{1,30}\b",
    )

    # Utilise CountVectorizer pour LDA (LDA attend des counts, pas TF-IDF)
    count_vec = CountVectorizer(
        max_features=max_features,
        min_df=min_df,
        max_df=max_df,
        stop_words=stopwords,
        ngram_range=(1, 2),
        token_pattern=r"(?u)\b[a-zA-Z؀-ۿ][a-zA-Z؀-ۿ0-9_-]{1,30}\b",
    )

    try:
        doc_term_matrix = count_vec.fit_transform(corpus)
        logger.info(f"Vocabulaire: {len(count_vec.vocabulary_)} termes | "
                    f"Matrice: {doc_term_matrix.shape}")
    except Exception as e:
        logger.error(f"Erreur vectorisation: {e}")
        return None, None, None

    lda = LatentDirichletAllocation(
        n_components=n_topics,
        max_iter=30,
        learning_method="online",
        learning_offset=50.0,
        random_state=42,
        n_jobs=-1,
        doc_topic_prior=0.1,
        topic_word_prior=0.01,
    )

    try:
        doc_topic_matrix = lda.fit_transform(doc_term_matrix)
        perplexity = lda.perplexity(doc_term_matrix)
        logger.info(f"LDA entraîné. Perplexité: {perplexity:.2f}")
    except Exception as e:
        logger.error(f"Erreur LDA: {e}")
        return None, count_vec, None

    # Vectorise aussi avec TF-IDF pour analyses ultérieures
    try:
        vectorizer.fit(corpus)
    except Exception:
        pass

    return lda, count_vec, doc_topic_matrix


def get_topic_top_words(
    lda: LatentDirichletAllocation,
    vectorizer: Any,
    n_words: int = TOP_WORDS_PER_TOPIC,
) -> Dict[int, List[str]]:
    """Extrait les N mots les plus importants par topic."""
    feature_names = vectorizer.get_feature_names_out()
    topics: Dict[int, List[str]] = {}

    for topic_idx, topic_vec in enumerate(lda.components_):
        top_indices = topic_vec.argsort()[:-n_words - 1:-1]
        topics[topic_idx] = [str(feature_names[i]) for i in top_indices]

    return topics


def auto_label_topic(
    top_words: List[str],
    ticker_words: Optional[List[str]] = None,
) -> str:
    """
    Génère un label automatique pour un topic basé sur ses mots dominants.
    """
    if not top_words:
        return "Topic Inconnu"

    # Mots-clés thématiques
    theme_keywords = {
        "Analyses Techniques": {"rsi", "macd", "support", "resistance", "cassure",
                                  "oblique", "canal", "bollinger", "stochastique",
                                  "signal", "tendance", "breakout", "retracement"},
        "Résultats Financiers": {"résultat", "bénéfice", "chiffre", "affaire",
                                   "profit", "perte", "dividende", "rapport",
                                   "financier", "annuel", "semestriel", "trimestrel"},
        "Macro & Économie": {"économie", "inflation", "taux", "bank_al_maghrib",
                               "politique", "fiscal", "croissance", "pib", "importation",
                               "exportation", "dirham", "devise", "réserve"},
        "Rumeurs & Insider": {"rumeur", "entendu", "source", "insider", "confidentiel",
                                "exclusif", "off", "record", "info", "tuyau"},
        "Panique & Crash": {"crash", "panique", "danger", "chute", "effondrement",
                              "baisse", "sell", "sortir", "alerte", "urgence"},
        "Euphorie & FOMO": {"incroyable", "historique", "record", "jackpot",
                              "tout", "monte", "fomo", "train", "rater", "manquer"},
        "IPO & Nouvelles": {"introduction", "ipo", "émission", "nouveau", "coté",
                              "officiel", "annonce", "presse", "déclaration"},
        "Smart Money": {"smart", "money", "institutionnel", "fonds", "gestionnaire",
                          "conviction", "accumuler", "position", "forte"},
        "Secteur Bancaire": {"banque", "crédit", "prêt", "taux", "dépôt", "liquide",
                               "provisions", "npls", "npl", "bancaire"},
        "Immobilier": {"immobilier", "logement", "projet", "promoteur", "résidence",
                        "terrain", "construction", "livraison"},
        "Energie & Mines": {"énergie", "mine", "phosphate", "électricité", "solaire",
                              "renouvelable", "barrage", "cobalt", "zinc"},
        "Télécoms": {"télécom", "mobile", "internet", "fibre", "4g", "5g",
                      "abonnés", "réseau", "opérateur"},
        "Agro-Alimentaire": {"alimentaire", "agriculture", "sucre", "huile", "céréales",
                               "eau", "minérale", "lait", "volaille"},
        "Pharma & Santé": {"pharmacie", "médicament", "santé", "clinique",
                            "laboratoire", "vaccin", "générique"},
    }

    word_set = set(w.lower() for w in top_words)

    # Vérifie les tickers mentionnés
    if ticker_words:
        ticker_in_topic = [t for t in ticker_words if any(
            t.lower() in w.lower() for w in top_words
        )]
        if ticker_in_topic:
            return f"Valeur: {', '.join(ticker_in_topic[:2])}"

    # Trouve le thème avec le plus de correspondances
    best_theme = None
    best_score = 0
    for theme, keywords in theme_keywords.items():
        score = len(word_set & keywords)
        if score > best_score:
            best_score = score
            best_theme = theme

    if best_theme and best_score >= 2:
        return best_theme

    # Fallback: utilise les 3 premiers mots
    return f"{top_words[0]}/{top_words[1]}/{top_words[2]}"


# ─────────────────────────────────────────────────────────────
# ÉVOLUTION TEMPORELLE DES TOPICS
# ─────────────────────────────────────────────────────────────

def compute_topic_evolution(
    df: pd.DataFrame,
    valid_idx: pd.Index,
    doc_topic_matrix: np.ndarray,
    freq: str = "ME",  # mensuel
) -> pd.DataFrame:
    """
    Calcule l'évolution mensuelle de la distribution des topics.
    Retourne: DataFrame(date, topic_0, topic_1, ..., topic_N)
    """
    if df.empty or doc_topic_matrix is None:
        return pd.DataFrame()

    valid_df = df.loc[valid_idx].copy()
    valid_df["date"] = pd.to_datetime(valid_df["timestamp"]).dt.to_period(freq)

    n_docs, n_topics = doc_topic_matrix.shape
    topic_cols = [f"topic_{i}" for i in range(n_topics)]

    topic_df = pd.DataFrame(doc_topic_matrix, index=valid_idx, columns=topic_cols)
    topic_df["period"] = valid_df["date"].values

    evolution = (
        topic_df.groupby("period")[topic_cols].mean().reset_index()
    )
    evolution["period"] = evolution["period"].astype(str)
    return evolution


def identify_bull_bear_precursors(
    topic_evolution: pd.DataFrame,
    price_panel: Optional[pd.DataFrame] = None,
    threshold_pct: float = 5.0,
    min_rise_days: int = 20,
) -> Dict[str, List[int]]:
    """
    Identifie les topics qui précèdent les hausses/baisses importantes.
    Retourne: {'bull_precursors': [...], 'bear_precursors': [...]}
    """
    if topic_evolution.empty:
        return {"bull_precursors": [], "bear_precursors": []}

    topic_cols = [c for c in topic_evolution.columns if c.startswith("topic_")]

    if price_panel is not None and not price_panel.empty:
        # Calcule le rendement mensuel du marché
        monthly_ret = price_panel.pct_change(min_rise_days).mean(axis=1)
        monthly_ret.index = pd.to_datetime(monthly_ret.index)
        monthly_ret_monthly = monthly_ret.resample("ME").mean()

        bull_months = monthly_ret_monthly[monthly_ret_monthly > threshold_pct / 100].index
        bear_months = monthly_ret_monthly[monthly_ret_monthly < -threshold_pct / 100].index
    else:
        # Utilise la distribution des topics elle-même pour trouver des régimes
        if topic_evolution.empty:
            return {"bull_precursors": [], "bear_precursors": []}
        dominant_topic = topic_evolution[topic_cols].idxmax(axis=1)
        # Assigne bull/bear arbitrairement basé sur le topic dominant
        bull_periods = topic_evolution.index[:len(topic_evolution)//3]
        bear_periods = topic_evolution.index[2*len(topic_evolution)//3:]

        if len(topic_cols) == 0:
            return {"bull_precursors": [], "bear_precursors": []}

        # Topics avec score élevé pendant les périodes bull
        bull_scores = topic_evolution.iloc[list(bull_periods)][topic_cols].mean()
        bear_scores = topic_evolution.iloc[list(bear_periods)][topic_cols].mean()

        bull_top = bull_scores.nlargest(3).index.tolist()
        bear_top = bear_scores.nlargest(3).index.tolist()

        return {
            "bull_precursors": [int(c.split("_")[1]) for c in bull_top],
            "bear_precursors": [int(c.split("_")[1]) for c in bear_top],
        }

    # Calcule le score moyen par topic pendant les mois précédant les hausses/baisses
    bull_precursors = []
    bear_precursors = []

    for topic_col in topic_cols:
        topic_num = int(topic_col.split("_")[1])
        topic_evolution_copy = topic_evolution.copy()
        topic_evolution_copy["period_dt"] = pd.to_datetime(
            topic_evolution_copy["period"] + "-01", errors="coerce"
        )
        topic_evolution_copy = topic_evolution_copy.set_index("period_dt")[topic_col]

        # Score moyen 1 mois avant les hausses
        if len(bull_months) > 0:
            bull_prior = bull_months - pd.DateOffset(months=1)
            bull_topic_scores = topic_evolution_copy.reindex(bull_prior, method="nearest").mean()
            baseline = topic_evolution_copy.mean()
            if bull_topic_scores > baseline * 1.3:
                bull_precursors.append(topic_num)

        # Score moyen 1 mois avant les baisses
        if len(bear_months) > 0:
            bear_prior = bear_months - pd.DateOffset(months=1)
            bear_topic_scores = topic_evolution_copy.reindex(bear_prior, method="nearest").mean()
            if bear_topic_scores > baseline * 1.3:
                bear_precursors.append(topic_num)

    return {"bull_precursors": bull_precursors, "bear_precursors": bear_precursors}


def detect_trending_topics(
    topic_evolution: pd.DataFrame,
    recent_days: int = 30,
) -> Dict[str, Any]:
    """
    Détecte les topics en tendance haussière récente vs baseline historique.
    """
    if topic_evolution.empty:
        return {"trending": [], "disappeared": [], "stable": []}

    topic_cols = [c for c in topic_evolution.columns if c.startswith("topic_")]
    n = len(topic_evolution)

    if n < 3:
        return {"trending": [], "disappeared": [], "stable": []}

    # Approximation: dernière période = récent, reste = historique
    recent_n = max(1, n // 6)  # ~dernier 1/6 des périodes
    recent = topic_evolution.iloc[-recent_n:][topic_cols].mean()
    historical = topic_evolution.iloc[:-recent_n][topic_cols].mean()

    # Évite division par zéro
    historical_safe = historical.clip(lower=1e-8)
    ratio = recent / historical_safe

    trending = ratio[ratio > 1.5].index.tolist()
    disappeared = ratio[ratio < 0.5].index.tolist()
    stable = [c for c in topic_cols if c not in trending and c not in disappeared]

    return {
        "trending": [int(c.split("_")[1]) for c in trending],
        "disappeared": [int(c.split("_")[1]) for c in disappeared],
        "stable": [int(c.split("_")[1]) for c in stable],
        "trend_ratios": ratio.to_dict(),
    }


def detect_weak_signals(
    topic_evolution: pd.DataFrame,
    growth_threshold: float = 2.0,
    volume_threshold: float = 0.03,
) -> List[Dict[str, Any]]:
    """
    Détecte les signaux faibles: topics à faible volume mais à croissance rapide.
    """
    if topic_evolution.empty:
        return []

    topic_cols = [c for c in topic_evolution.columns if c.startswith("topic_")]
    weak_signals = []

    for col in topic_cols:
        topic_num = int(col.split("_")[1])
        series = topic_evolution[col].values

        if len(series) < 3:
            continue

        # Volume moyen faible
        avg_volume = float(np.mean(series))
        recent_volume = float(np.mean(series[-2:])) if len(series) >= 2 else avg_volume

        if avg_volume < volume_threshold:
            # Croissance rapide (dernière période vs moyenne)
            if avg_volume > 1e-8 and recent_volume / avg_volume > growth_threshold:
                weak_signals.append({
                    "topic": topic_num,
                    "avg_volume": avg_volume,
                    "recent_volume": recent_volume,
                    "growth_rate": recent_volume / max(avg_volume, 1e-8),
                    "signal_type": "weak_signal_fast_growing",
                })

    weak_signals.sort(key=lambda x: x["growth_rate"], reverse=True)
    return weak_signals


# ─────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────

def run_phase10(
    df: pd.DataFrame,
    stock_scores: Optional[pd.DataFrame] = None,
    phase8_results: Optional[Dict[str, Any]] = None,
    n_topics: int = N_TOPICS,
) -> Dict[str, Any]:
    """
    Exécute la Phase 10: Topic Modeling.

    Returns dict with keys:
        topic_model, vectorizer, doc_topic_matrix,
        topic_top_words, topic_labels, topic_evolution,
        bull_precursors, bear_precursors, trending_topics,
        disappeared_topics, weak_signals
    """
    logger.info("=== Phase 10: Topic Modeling ===")

    # Corpus
    logger.info("Construction du corpus...")
    corpus, valid_idx = build_corpus(df)

    if len(corpus) < 50:
        logger.error(f"Corpus trop petit: {len(corpus)} messages")
        return {"error": "Corpus insuffisant pour le topic modeling"}

    logger.info(f"  {len(corpus)} messages dans le corpus")

    # LDA
    logger.info(f"Entraînement LDA ({n_topics} topics)...")
    lda, vectorizer, doc_topic_matrix = train_lda_model(corpus, n_topics=n_topics)

    if lda is None:
        logger.error("Échec de l'entraînement LDA")
        return {"error": "Échec LDA"}

    # Top words par topic
    logger.info("Extraction des mots clés par topic...")
    topic_top_words = get_topic_top_words(lda, vectorizer)

    # Labels automatiques
    from whatsapp_analysis.config import BVC_TICKERS
    ticker_list = list(BVC_TICKERS.keys())

    topic_labels: Dict[int, str] = {}
    for topic_num, words in topic_top_words.items():
        topic_labels[topic_num] = auto_label_topic(words, ticker_list)

    logger.info("Topics identifiés:")
    for i, (num, label) in enumerate(topic_labels.items()):
        words_preview = ", ".join(topic_top_words[num][:5])
        logger.info(f"  Topic {num}: {label} [{words_preview}...]")

    # Évolution temporelle
    logger.info("Calcul de l'évolution temporelle des topics...")
    topic_evolution = compute_topic_evolution(df, valid_idx, doc_topic_matrix)
    logger.info(f"  {len(topic_evolution)} périodes dans l'évolution")

    # Price panel pour analyse précurseurs
    price_panel = None
    if phase8_results is not None:
        price_panel = phase8_results.get("price_panel")

    # Précurseurs bull/bear
    logger.info("Identification des précurseurs bull/bear...")
    precursors = identify_bull_bear_precursors(topic_evolution, price_panel)

    # Topics en tendance
    logger.info("Détection des topics en tendance...")
    trending = detect_trending_topics(topic_evolution)

    # Signaux faibles
    logger.info("Détection des signaux faibles...")
    weak_signals = detect_weak_signals(topic_evolution)
    logger.info(f"  {len(weak_signals)} signaux faibles détectés")

    # Statistiques finales
    if doc_topic_matrix is not None:
        dominant_topics = np.argmax(doc_topic_matrix, axis=1)
        topic_distribution = Counter(dominant_topics)
        top_5_topics = topic_distribution.most_common(5)
    else:
        topic_distribution = Counter()
        top_5_topics = []

    summary = {
        "n_topics": n_topics,
        "corpus_size": len(corpus),
        "n_periods": len(topic_evolution),
        "bull_precursor_topics": precursors.get("bull_precursors", []),
        "bear_precursor_topics": precursors.get("bear_precursors", []),
        "trending_topics": trending.get("trending", []),
        "disappeared_topics": trending.get("disappeared", []),
        "n_weak_signals": len(weak_signals),
        "top_5_dominant_topics": [
            {"topic": int(t), "label": topic_labels.get(t, f"Topic {t}"), "count": int(c)}
            for t, c in top_5_topics
        ],
    }

    logger.info(f"Phase 10 terminée. {n_topics} topics, "
                f"{len(precursors.get('bull_precursors', []))} précurseurs haussiers")

    return {
        "topic_model": lda,
        "vectorizer": vectorizer,
        "doc_topic_matrix": doc_topic_matrix,
        "topic_top_words": topic_top_words,
        "topic_labels": topic_labels,
        "topic_evolution": topic_evolution,
        "bull_precursors": precursors.get("bull_precursors", []),
        "bear_precursors": precursors.get("bear_precursors", []),
        "trending_topics": trending,
        "weak_signals": weak_signals,
        "topic_distribution": topic_distribution,
        "corpus": corpus,
        "valid_idx": valid_idx,
        "summary": summary,
    }


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    print("Test Phase 10: données synthétiques...")

    rng = np.random.RandomState(42)
    dates = pd.date_range("2021-01-01", "2024-12-31", freq="h")[:5000]

    sample_messages = [
        "IAM excellent résultat annuel dividende haussier fort achat",
        "ATW analyse technique support résistance cassure bullish",
        "crash panique vendez tout danger alerte rouge sortir",
        "rumeur source exclusive info confidentielle tuyau",
        "rsi macd bollinger signal technique tendance support",
        "résultat bénéfice dividende rapport financier annuel",
        "banque crédit dépôt taux liquidité provisions bancaire",
        "immobilier logement projet promoteur résidence terrain",
        "économie inflation banque centrale politique monétaire taux",
        "achat fort conviction maximale buy excellente opportunité",
        "BCP renforcement recommandé potentiel hausse attendue",
        "MNG managem mine phosphate métal cours international",
        "Sothema pharmacie médicament santé clinique résultat",
        "FOMO tout le monde achète train part dernier wagon",
        "incroyable historique record marché monte tout exceptionnel",
    ]

    test_df = pd.DataFrame({
        "timestamp": dates,
        "author": [f"user_{i % 50}" for i in range(5000)],
        "message_text": [rng.choice(sample_messages) for _ in range(5000)],
        "language": rng.choice(["fr", "darija", "arabizi"], 5000),
    })

    results = run_phase10(test_df, n_topics=10)

    if "error" not in results:
        print("\n=== Résultats Phase 10 ===")
        print(f"Nombre de topics: {results['summary']['n_topics']}")
        print(f"Taille corpus: {results['summary']['corpus_size']}")
        print(f"Précurseurs haussiers: {results['bull_precursors']}")
        print(f"Précurseurs baissiers: {results['bear_precursors']}")
        print(f"Topics en tendance: {results['trending_topics'].get('trending', [])}")
        print(f"Signaux faibles: {results['summary']['n_weak_signals']}")
        print("\nTop 5 topics dominants:")
        for t in results["summary"]["top_5_dominant_topics"]:
            print(f"  Topic {t['topic']}: {t['label']} ({t['count']} messages)")
        print("\nLabels des topics:")
        for num, label in list(results["topic_labels"].items())[:5]:
            words = results["topic_top_words"][num][:5]
            print(f"  Topic {num}: {label} -> {words}")
    else:
        print(f"Erreur: {results['error']}")
