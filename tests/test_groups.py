import numpy as np
import pandas as pd

from metro.features import FEATURE_COLS
from metro.groups import discover_groups, fit_rule, rule_agreement, rule_text


def _two_clusters(seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(40):
        am, pm = (0.6, 0.1) if i < 20 else (0.1, 0.6)
        rows.append({"line": "M2", "station": f"S{i:02d}",
                     "weekend_ratio": 0.5 + rng.normal(0, 0.01), "am_share": am + rng.normal(0, 0.01),
                     "midday_share": 0.2 + rng.normal(0, 0.01), "pm_share": pm + rng.normal(0, 0.01),
                     "late_share": 0.1 + rng.normal(0, 0.01), "discount_share": 0.4 + rng.normal(0, 0.01),
                     "transfer_share": 0.1 + rng.normal(0, 0.01), "months_active": 19, "eligible": True})
    return pd.DataFrame(rows).set_index(["line", "station"])


def test_discover_groups_separates_obvious_clusters():
    features = _two_clusters()
    labels = discover_groups(features, k_values=(2, 3))
    assert labels.nunique() == 2 and labels.iloc[:20].nunique() == 1 and labels.iloc[20:].nunique() == 1


def test_discover_groups_skips_ineligible_units():
    features = _two_clusters()
    features.loc[("M2", "S00"), "eligible"] = False
    labels = discover_groups(features, k_values=(2,))
    assert ("M2", "S00") not in labels.index and len(labels) == 39


def test_rule_reproduces_separable_clusters():
    features = _two_clusters()
    labels = discover_groups(features, k_values=(2, 3))
    tree = fit_rule(features, labels)
    assert rule_agreement(tree, features, labels) == 1.0
    assert "am_share" in rule_text(tree) or "pm_share" in rule_text(tree)


def test_tiny_clusters_become_outliers_and_do_not_use_up_a_group():
    features = _two_clusters()
    event = features.iloc[[0]].copy()
    event.index = pd.MultiIndex.from_tuples([("M9", "STADIUM")], names=features.index.names)
    event[["weekend_ratio", "am_share", "midday_share", "pm_share", "late_share"]] = [0.01, 0.0, 0.01, 0.03, 0.96]
    features = pd.concat([features, event])
    labels = discover_groups(features, k_values=(2, 3), min_size=5)
    assert labels[("M9", "STADIUM")] == -1
    real = labels.drop(("M9", "STADIUM"))
    assert real.nunique() == 2 and real.iloc[:20].nunique() == 1 and real.iloc[20:].nunique() == 1
