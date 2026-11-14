"""Station groups: k-means to discover them, a shallow tree to turn them into a readable rule."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

from metro.features import FEATURE_COLS


OUTLIER = -1


def _fit(Z, k, seed, min_size):
    """K-means; members of clusters smaller than min_size are set aside and the rest refitted."""
    keep = np.ones(len(Z), dtype=bool)
    for _ in range(5):
        labels = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(Z[keep])
        sizes = np.bincount(labels, minlength=k)
        tiny = sizes[labels] < min_size
        if not tiny.any():
            break
        keep[np.flatnonzero(keep)[tiny]] = False
    out = np.full(len(Z), OUTLIER)
    out[keep] = labels
    return out, silhouette_score(Z[keep], labels)


def discover_groups(features: pd.DataFrame, k_values=(4, 5, 6), seed: int = 0, min_size: int = 5) -> pd.Series:
    """Cluster id per eligible unit; k is the one with the best silhouette score.

    A unit that would form a cluster of fewer than min_size units (e.g. an event-only
    stadium station) gets OUTLIER (-1) instead of using up a group. Ids are renumbered
    by cluster size (0 = largest) so they are stable to read.
    """
    X = features.loc[features["eligible"], FEATURE_COLS]
    Z = StandardScaler().fit_transform(X)
    best = None
    for k in k_values:
        labels, score = _fit(Z, k, seed, min_size)
        if best is None or score > best[0]:
            best = (score, labels)
    raw = pd.Series(best[1], index=X.index)
    counts = raw[raw != OUTLIER].value_counts()
    order = {old: new for new, old in enumerate(counts.index)}
    order[OUTLIER] = OUTLIER
    return raw.map(order).rename("cluster")


def fit_rule(features: pd.DataFrame, labels: pd.Series, max_depth: int = 3) -> DecisionTreeClassifier:
    """Shallow tree on unstandardized features, so thresholds read as plain shares and ratios."""
    tree = DecisionTreeClassifier(max_depth=max_depth, random_state=0)
    return tree.fit(features.loc[labels.index, FEATURE_COLS], labels)


def rule_text(tree: DecisionTreeClassifier) -> str:
    return export_text(tree, feature_names=FEATURE_COLS, decimals=2)


def rule_agreement(tree: DecisionTreeClassifier, features: pd.DataFrame, labels: pd.Series) -> float:
    """Share of units where the rule gives the same group as k-means."""
    pred = tree.predict(features.loc[labels.index, FEATURE_COLS])
    return float((pred == labels.to_numpy()).mean())
