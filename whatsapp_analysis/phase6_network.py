"""
Phase 6 — Social Network Analysis
Build directed interaction graph, compute centrality metrics,
detect communities, identify opinion leaders, and track
signal propagation from Smart Money members.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False
    print("WARNING: networkx not installed. Network analysis disabled.")

try:
    from community import best_partition as louvain_partition
    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False

from whatsapp_analysis.config import DEFAULT_CONFIG, Config

# ─────────────────────────────────────────────
# INTERACTION DETECTION
# ─────────────────────────────────────────────

AT_MENTION_RE = re.compile(r'@([\w\.\-]+)', re.IGNORECASE)
SI_MENTION_RE = re.compile(
    r'\b(?:si|ssi|khoya|khouya|3ammi|monsieur|mr|mme)\s+([\w\.\-]+)',
    re.IGNORECASE,
)
QUOTE_RE = re.compile(r'>', re.MULTILINE)  # WhatsApp quote indicator


def _normalize_name(name: str) -> str:
    """Normalize author name for fuzzy matching."""
    return re.sub(r'[^a-z0-9]', '', name.lower().replace('~', '').strip())


def _build_name_index(authors: List[str]) -> Dict[str, str]:
    """Build {normalized_name: canonical_name} index."""
    return {_normalize_name(a): a for a in authors}


def _fuzzy_match_author(
    mention: str,
    name_index: Dict[str, str],
    min_overlap: int = 4,
) -> Optional[str]:
    """
    Try to match a mention string to a known author.
    Returns canonical author name if found.
    """
    mention_norm = _normalize_name(mention)
    if not mention_norm:
        return None

    # Exact match first
    if mention_norm in name_index:
        return name_index[mention_norm]

    # Substring match (mention is substring of author or vice versa)
    for norm, canonical in name_index.items():
        if len(mention_norm) >= min_overlap:
            if mention_norm in norm or norm in mention_norm:
                return canonical

    return None


def _extract_interactions(
    row: pd.Series,
    name_index: Dict[str, str],
    prev_messages: List[dict],
    window_size: int = 20,
) -> List[Tuple[str, str, str]]:
    """
    Extract directed interactions (source → target) from a message row.
    Returns list of (from_author, to_author, interaction_type).
    Interaction types: 'mention', 'reply', 'quote'
    """
    interactions = []
    source = row['author']
    text = str(row.get('message_text', ''))

    # 1. @mentions
    for mention in AT_MENTION_RE.findall(text):
        target = _fuzzy_match_author(mention, name_index)
        if target and target != source:
            interactions.append((source, target, 'mention'))

    # 2. "si Name" / "khoya Name" style
    for mention in SI_MENTION_RE.findall(text):
        target = _fuzzy_match_author(mention, name_index)
        if target and target != source:
            interactions.append((source, target, 'reply'))

    # 3. Temporal proximity reply detection:
    # If a message follows another author's message within short time
    # and contains a reply pattern
    msg_ts = row.get('timestamp')
    if msg_ts and prev_messages:
        for prev in reversed(prev_messages[-window_size:]):
            prev_author = prev.get('author', '')
            if prev_author == source:
                continue
            prev_ts = prev.get('timestamp')
            if prev_ts is None:
                continue
            # Within 3 minutes = likely reply
            try:
                diff_seconds = (pd.Timestamp(msg_ts) - pd.Timestamp(prev_ts)).total_seconds()
            except Exception:
                continue
            if 0 < diff_seconds < 180:
                # Check if text references the previous author or contains quote marker
                prev_norm = _normalize_name(prev_author)
                if (
                    prev_norm in _normalize_name(text) or
                    QUOTE_RE.search(text) or
                    len(interactions) == 0  # no other interaction found yet
                ):
                    interactions.append((source, prev_author, 'temporal_reply'))
                    break  # Only attribute to most recent

    return list(set(interactions))  # deduplicate


# ─────────────────────────────────────────────
# GRAPH CONSTRUCTION
# ─────────────────────────────────────────────

def build_interaction_graph(
    df: pd.DataFrame,
    cfg: Config = DEFAULT_CONFIG,
) -> Tuple['nx.DiGraph', pd.DataFrame]:
    """
    Build a directed NetworkX graph from message interactions.

    Nodes: authors
    Edges: directed interactions (source → target) with:
      - weight: number of interactions
      - types: set of interaction types

    Returns
    -------
    G : nx.DiGraph
    edge_df : DataFrame of all raw interactions
    """
    if not HAS_NX:
        raise RuntimeError("networkx required for network analysis.")

    authors = df['author'].unique().tolist()
    name_index = _build_name_index(authors)

    G = nx.DiGraph()
    G.add_nodes_from(authors)

    # Add node attributes
    author_msg_counts = df['author'].value_counts().to_dict()
    for author in authors:
        G.nodes[author]['message_count'] = author_msg_counts.get(author, 0)

    print(f"Building interaction graph for {len(authors)} authors...")

    # Accumulate edge weights
    edge_weights: Dict[Tuple[str, str], int] = defaultdict(int)
    edge_types: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    interaction_records = []

    prev_messages: List[dict] = []
    total = len(df)
    batch_report = max(1, total // 10)

    text_df = df[df['message_type'] == 'text'].copy()
    text_df = text_df.sort_values('timestamp')

    for i, (_, row) in enumerate(text_df.iterrows()):
        if i % batch_report == 0:
            print(f"  Processing interactions: {i:,}/{total:,}")

        interactions = _extract_interactions(row, name_index, prev_messages)

        for (src, tgt, itype) in interactions:
            if src not in G.nodes:
                G.add_node(src)
            if tgt not in G.nodes:
                G.add_node(tgt)
            key = (src, tgt)
            edge_weights[key] += 1
            edge_types[key].add(itype)
            interaction_records.append({
                'from_author': src,
                'to_author': tgt,
                'interaction_type': itype,
                'timestamp': row.get('timestamp'),
                'message_id': row.get('message_id'),
            })

        prev_messages.append({
            'author': row['author'],
            'timestamp': row.get('timestamp'),
        })
        if len(prev_messages) > 50:
            prev_messages.pop(0)

    # Add edges with weights
    min_interactions = cfg.network_min_interactions
    for (src, tgt), weight in edge_weights.items():
        if weight >= min_interactions:
            G.add_edge(
                src, tgt,
                weight=weight,
                types=list(edge_types[(src, tgt)]),
            )

    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")
    edge_df = pd.DataFrame(interaction_records) if interaction_records else pd.DataFrame()
    return G, edge_df


# ─────────────────────────────────────────────
# CENTRALITY METRICS
# ─────────────────────────────────────────────

def compute_node_metrics(G: 'nx.DiGraph') -> pd.DataFrame:
    """
    Compute all centrality metrics for each node.

    Returns DataFrame with columns:
    author, degree_in, degree_out, degree_total,
    betweenness, closeness, eigenvector, pagerank,
    clustering, in_degree_centrality, out_degree_centrality
    """
    if not HAS_NX:
        return pd.DataFrame()

    if G.number_of_nodes() == 0:
        return pd.DataFrame()

    print("Computing centrality metrics...")
    G_undirected = G.to_undirected()

    # Degree
    in_deg = dict(G.in_degree())
    out_deg = dict(G.out_degree())

    # Degree centrality
    in_deg_cent = nx.in_degree_centrality(G)
    out_deg_cent = nx.out_degree_centrality(G)

    # Betweenness (use undirected for speed on large graphs)
    try:
        if G.number_of_nodes() > 1000:
            # Approximate with sampling
            betweenness = nx.betweenness_centrality(G, normalized=True, k=min(500, G.number_of_nodes()))
        else:
            betweenness = nx.betweenness_centrality(G, normalized=True)
    except Exception:
        betweenness = {n: 0.0 for n in G.nodes()}

    # Closeness
    try:
        closeness = nx.closeness_centrality(G)
    except Exception:
        closeness = {n: 0.0 for n in G.nodes()}

    # Eigenvector centrality
    try:
        eigenvector = nx.eigenvector_centrality(G, max_iter=500, tol=1e-6)
    except (nx.PowerIterationFailedConvergence, Exception):
        try:
            eigenvector = nx.eigenvector_centrality_numpy(G)
        except Exception:
            eigenvector = {n: 0.0 for n in G.nodes()}

    # PageRank
    try:
        pagerank = nx.pagerank(G, alpha=0.85, max_iter=200)
    except Exception:
        pagerank = {n: 1.0/max(G.number_of_nodes(), 1) for n in G.nodes()}

    # Clustering (undirected)
    try:
        clustering = nx.clustering(G_undirected)
    except Exception:
        clustering = {n: 0.0 for n in G.nodes()}

    # Assemble
    records = []
    for node in G.nodes():
        records.append({
            'author': node,
            'degree_in': in_deg.get(node, 0),
            'degree_out': out_deg.get(node, 0),
            'degree_total': in_deg.get(node, 0) + out_deg.get(node, 0),
            'in_degree_centrality': round(in_deg_cent.get(node, 0), 5),
            'out_degree_centrality': round(out_deg_cent.get(node, 0), 5),
            'betweenness': round(betweenness.get(node, 0), 5),
            'closeness': round(closeness.get(node, 0), 5),
            'eigenvector': round(eigenvector.get(node, 0), 5),
            'pagerank': round(pagerank.get(node, 0), 6),
            'clustering': round(clustering.get(node, 0), 4),
            'message_count': G.nodes[node].get('message_count', 0),
        })

    metrics_df = pd.DataFrame(records).sort_values('pagerank', ascending=False)
    metrics_df['pagerank_rank'] = range(1, len(metrics_df) + 1)
    metrics_df['betweenness_rank'] = metrics_df['betweenness'].rank(ascending=False).astype(int)
    metrics_df['eigenvector_rank'] = metrics_df['eigenvector'].rank(ascending=False).astype(int)

    # Classify roles
    def _classify_role(row) -> str:
        pr = row['pagerank_rank']
        bt = row['betweenness_rank']
        ev = row['eigenvector_rank']
        n = len(metrics_df)

        top10pct = int(n * 0.10)
        if pr <= top10pct:
            return 'opinion_leader'
        elif bt <= top10pct:
            return 'information_relay'
        elif ev <= top10pct and row['degree_total'] < metrics_df['degree_total'].median():
            return 'hidden_influencer'
        elif row['degree_in'] > row['degree_out'] * 2:
            return 'absorber'
        elif row['degree_out'] > row['degree_in'] * 2:
            return 'broadcaster'
        else:
            return 'regular'

    metrics_df['network_role'] = metrics_df.apply(_classify_role, axis=1)
    return metrics_df.reset_index(drop=True)


# ─────────────────────────────────────────────
# COMMUNITY DETECTION
# ─────────────────────────────────────────────

def detect_communities(G: 'nx.DiGraph') -> Dict[str, int]:
    """
    Detect communities using Louvain (if available) or greedy modularity.
    Returns {author: community_id}.
    """
    if not HAS_NX:
        return {}

    G_undirected = G.to_undirected()
    if G_undirected.number_of_nodes() == 0:
        return {}

    # Remove isolated nodes for community detection
    G_connected = G_undirected.copy()
    isolates = list(nx.isolates(G_connected))
    G_connected.remove_nodes_from(isolates)

    if G_connected.number_of_nodes() == 0:
        return {n: 0 for n in G.nodes()}

    communities: Dict[str, int] = {n: -1 for n in G.nodes()}

    if HAS_LOUVAIN:
        try:
            partition = louvain_partition(G_connected)
            communities.update(partition)
            print(f"Louvain communities: {max(partition.values())+1 if partition else 0}")
        except Exception as e:
            print(f"Louvain failed: {e}, falling back to greedy modularity.")
            HAS_LOUVAIN_LOCAL = False
    else:
        HAS_LOUVAIN_LOCAL = False

    if not HAS_LOUVAIN or communities.get(list(G_connected.nodes())[0] if G_connected.nodes() else 'x', -1) == -1:
        try:
            comp_gen = nx.community.greedy_modularity_communities(G_connected)
            for i, comp in enumerate(comp_gen):
                for node in comp:
                    communities[node] = i
            print(f"Greedy modularity communities: {i+1}")
        except Exception as e:
            print(f"Community detection failed: {e}. Assigning all to community 0.")
            communities = {n: 0 for n in G.nodes()}

    # Assign isolated nodes to their own community
    max_comm = max(communities.values()) if communities else -1
    for node in isolates:
        max_comm += 1
        communities[node] = max_comm

    return communities


# ─────────────────────────────────────────────
# SIGNAL PROPAGATION
# ─────────────────────────────────────────────

def analyze_signal_propagation(
    df: pd.DataFrame,
    smart_money_list: List[str],
    signal_cols: Optional[List[str]] = None,
    horizons_hours: List[int] = [24, 48, 72],
) -> pd.DataFrame:
    """
    After a Smart Money member posts a buy/sell signal, track how many
    other members repeat the same signal (for same ticker) within horizons.

    Returns DataFrame with propagation events.
    """
    if signal_cols is None:
        signal_cols = ['signal_ACHAT_FORT', 'signal_ACHETER', 'signal_VENTE']

    available_sigs = [c for c in signal_cols if c in df.columns]
    if not available_sigs:
        print("No signal columns found for propagation analysis.")
        return pd.DataFrame()

    if not smart_money_list:
        return pd.DataFrame()

    df_text = df[df['message_type'] == 'text'].copy()
    df_text['timestamp'] = pd.to_datetime(df_text['timestamp'])

    # Identify Smart Money signal events
    sm_mask = df_text['author'].isin(smart_money_list)
    sm_df = df_text[sm_mask].copy()

    has_signal = sm_df[available_sigs].any(axis=1)
    sm_signals = sm_df[has_signal].copy()

    if sm_signals.empty:
        return pd.DataFrame()

    results = []
    for _, sm_row in sm_signals.iterrows():
        sm_ts = sm_row['timestamp']
        sm_tickers = sm_row.get('nlp_tickers', []) or sm_row.get('tickers', [])
        if not isinstance(sm_tickers, list):
            sm_tickers = []

        # Determine which signal
        active_sigs = [c.replace('signal_', '') for c in available_sigs if sm_row.get(c, False)]
        if not active_sigs:
            continue
        primary_sig = active_sigs[0]

        for horizon_h in horizons_hours:
            horizon_end = sm_ts + pd.Timedelta(hours=horizon_h)

            # Find non-SM messages in window with same signal
            window = df_text[
                (df_text['timestamp'] > sm_ts) &
                (df_text['timestamp'] <= horizon_end) &
                (~df_text['author'].isin(smart_money_list))
            ]

            # Filter for same signal
            sig_col = f'signal_{primary_sig}'
            if sig_col in window.columns:
                same_sig = window[window[sig_col] == True]
            else:
                continue

            # Filter for same ticker if available
            if sm_tickers:
                def has_ticker_overlap(row_tickers):
                    if not isinstance(row_tickers, list):
                        return False
                    return bool(set(row_tickers) & set(sm_tickers))

                ticker_col = 'nlp_tickers' if 'nlp_tickers' in same_sig.columns else 'tickers'
                if ticker_col in same_sig.columns:
                    same_sig_ticker = same_sig[same_sig[ticker_col].apply(has_ticker_overlap)]
                else:
                    same_sig_ticker = same_sig
            else:
                same_sig_ticker = same_sig

            same_sig_ticker = same_sig_ticker.reset_index(drop=True) if not same_sig_ticker.empty else same_sig_ticker
            propagators = same_sig_ticker['author'].nunique() if 'author' in same_sig_ticker.columns else 0
            results.append({
                'sm_author': sm_row['author'],
                'sm_timestamp': sm_ts,
                'signal': primary_sig,
                'tickers': str(sm_tickers),
                'horizon_hours': horizon_h,
                'n_propagators': propagators,
                'n_messages': len(same_sig_ticker),
                'propagator_authors': list(same_sig_ticker['author'].unique())[:10] if 'author' in same_sig_ticker.columns else [],
            })

    return pd.DataFrame(results)


# ─────────────────────────────────────────────
# FULL NETWORK PIPELINE
# ─────────────────────────────────────────────

def run_network_analysis(
    df: pd.DataFrame,
    smart_money_list: Optional[List[str]] = None,
    cfg: Config = DEFAULT_CONFIG,
) -> Tuple['nx.DiGraph', pd.DataFrame, Dict[str, int], pd.DataFrame]:
    """
    Full network analysis pipeline.

    Returns
    -------
    G : nx.DiGraph
    node_metrics : pd.DataFrame
    communities : Dict {author: community_id}
    propagation_df : pd.DataFrame
    """
    if not HAS_NX:
        raise RuntimeError("networkx is required. Install with: pip install networkx")

    print("Building interaction graph...")
    G, edge_df = build_interaction_graph(df, cfg)

    print("Computing node metrics...")
    node_metrics = compute_node_metrics(G)

    # Add community
    print("Detecting communities...")
    communities = detect_communities(G)
    if node_metrics is not None and not node_metrics.empty:
        node_metrics['community'] = node_metrics['author'].map(communities).fillna(-1).astype(int)

    # Add Smart Money flag
    if smart_money_list and node_metrics is not None and not node_metrics.empty:
        node_metrics['is_smart_money'] = node_metrics['author'].isin(smart_money_list)

    # Signal propagation
    propagation_df = pd.DataFrame()
    if smart_money_list:
        print("Analyzing signal propagation...")
        propagation_df = analyze_signal_propagation(df, smart_money_list)
        if not propagation_df.empty:
            print(f"  Found {len(propagation_df)} propagation events.")

    return G, node_metrics, communities, propagation_df


# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────

def summarize_network(
    G: 'nx.DiGraph',
    node_metrics: pd.DataFrame,
    communities: Dict[str, int],
) -> None:
    print(f"\n{'='*60}")
    print("NETWORK ANALYSIS SUMMARY")
    print(f"{'='*60}")
    if not HAS_NX:
        print("NetworkX not available.")
        return

    print(f"Nodes: {G.number_of_nodes():,}")
    print(f"Edges: {G.number_of_edges():,}")
    try:
        print(f"Density: {nx.density(G):.4f}")
        print(f"Is weakly connected: {nx.is_weakly_connected(G) if G.number_of_nodes() > 0 else 'N/A'}")
    except Exception:
        pass

    n_communities = len(set(communities.values()))
    print(f"Communities: {n_communities}")

    if node_metrics is not None and not node_metrics.empty:
        print(f"\nTop Opinion Leaders (PageRank):")
        top = node_metrics.head(5)
        for _, row in top.iterrows():
            print(f"  {str(row['author'])[:40]:<40} PR={row['pagerank']:.4f} Role={row['network_role']}")

        role_counts = node_metrics['network_role'].value_counts()
        print(f"\nRole distribution:")
        for role, cnt in role_counts.items():
            print(f"  {role:<25}: {cnt}")
    print(f"{'='*60}\n")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import time
    import json
    from pathlib import Path

    OUT_DIR = Path("/home/user/-bvc-analyzer/whatsapp_analysis/output")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    for fname in ["phase3_messages.parquet", "phase2_messages.parquet", "phase1_messages.parquet"]:
        p = OUT_DIR / fname
        if p.exists():
            print(f"Loading {fname}...")
            df = pd.read_parquet(p)
            break
    else:
        raise FileNotFoundError("No phase parquet found.")

    # Load smart money list if available
    sm_path = OUT_DIR / "phase5_smart_money_list.json"
    smart_money_list = []
    if sm_path.exists():
        with open(sm_path) as f:
            smart_money_list = json.load(f)
        print(f"Loaded {len(smart_money_list)} smart money members.")

    print(f"Loaded {len(df):,} messages.")
    t0 = time.time()

    G, node_metrics, communities, propagation_df = run_network_analysis(
        df, smart_money_list=smart_money_list
    )

    print(f"\nNetwork analysis complete in {time.time()-t0:.1f}s")
    summarize_network(G, node_metrics, communities)

    # Save
    if node_metrics is not None and not node_metrics.empty:
        node_metrics.to_parquet(OUT_DIR / "phase6_node_metrics.parquet", index=False)
        node_metrics.to_csv(OUT_DIR / "phase6_node_metrics.csv", index=False)
        print(f"Saved node_metrics")

    if not propagation_df.empty:
        propagation_df.to_csv(OUT_DIR / "phase6_propagation.csv", index=False)
        print(f"Saved {len(propagation_df)} propagation events")

    # Save communities
    with open(OUT_DIR / "phase6_communities.json", 'w', encoding='utf-8') as f:
        json.dump(communities, f, ensure_ascii=False)
    print(f"Saved communities ({len(set(communities.values()))} clusters)")

    # Save graph
    try:
        nx.write_gexf(G, str(OUT_DIR / "phase6_graph.gexf"))
        print(f"Saved graph as GEXF (importable in Gephi)")
    except Exception as e:
        print(f"Could not save GEXF: {e}")
