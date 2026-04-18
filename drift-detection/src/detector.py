"""
Statistical drift detection engine.
Implements:
  - Kolmogorov-Smirnov (KS) test  — p-value based, catches distribution shape changes
  - Population Stability Index (PSI) — binning-based, widely used in credit/ML monitoring
"""

import logging
from typing import List, Optional

import numpy as np
from scipy import stats

logger = logging.getLogger("cortex.drift-detection.engine")

# Default thresholds
KS_P_VALUE_THRESHOLD = 0.05  # p < 0.05 → drift
PSI_LOW_THRESHOLD = 0.10  # PSI < 0.10  → no significant change
PSI_MEDIUM_THRESHOLD = 0.20  # 0.10–0.20   → moderate change, monitor
PSI_HIGH_THRESHOLD = 0.20  # PSI ≥ 0.20  → significant shift, alert

N_BINS = 10
EPS = 1e-6  # avoid log(0)


def ks_test(
    reference: List[float],
    current: List[float],
    threshold: float = KS_P_VALUE_THRESHOLD,
) -> dict:
    """
    Run a two-sample Kolmogorov-Smirnov test.

    Returns:
        statistic  : KS statistic (max distance between CDFs)
        p_value    : p-value (low = drift likely)
        drift      : bool — True if p_value < threshold
    """
    if len(reference) < 10 or len(current) < 10:
        logger.warning("KS test needs at least 10 samples per distribution")
        return {
            "statistic": 0.0,
            "p_value": 1.0,
            "drift_detected": False,
            "threshold": threshold,
        }

    stat, p_value = stats.ks_2samp(reference, current)
    drift = bool(p_value < threshold)

    logger.debug(f"KS test → stat={stat:.4f} p={p_value:.4f} drift={drift}")
    return {
        "statistic": round(float(stat), 6),
        "p_value": round(float(p_value), 6),
        "drift_detected": drift,
        "threshold": threshold,
    }


def compute_psi(
    reference: List[float],
    current: List[float],
    n_bins: int = N_BINS,
    threshold: float = PSI_HIGH_THRESHOLD,
    bin_edges: Optional[List[float]] = None,
) -> dict:
    """
    Compute Population Stability Index (PSI).

    PSI = Σ (actual% - expected%) × ln(actual% / expected%)

    Returns:
        psi_score  : float
        bin_edges  : list of bin edges used (reuse for future scoring)
        drift      : bool — True if psi_score >= threshold
    """
    ref_arr = np.array(reference, dtype=float)
    cur_arr = np.array(current, dtype=float)

    if len(ref_arr) < 10 or len(cur_arr) < 10:
        return {
            "psi_score": 0.0,
            "drift_detected": False,
            "threshold": threshold,
            "bin_edges": [],
        }

    # Build bins from reference if not provided
    if bin_edges is None:
        bin_edges = list(np.percentile(ref_arr, np.linspace(0, 100, n_bins + 1)))
        bin_edges[0] -= EPS
        bin_edges[-1] += EPS

    edges = np.array(bin_edges)

    ref_counts, _ = np.histogram(ref_arr, bins=edges)
    cur_counts, _ = np.histogram(cur_arr, bins=edges)

    ref_pct = ref_counts / (ref_counts.sum() + EPS)
    cur_pct = cur_counts / (cur_counts.sum() + EPS)

    # Clip to avoid log(0)
    ref_pct = np.clip(ref_pct, EPS, None)
    cur_pct = np.clip(cur_pct, EPS, None)

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    drift = psi >= threshold

    severity = "none"
    if psi >= PSI_HIGH_THRESHOLD:
        severity = "high"
    elif psi >= PSI_LOW_THRESHOLD:
        severity = "moderate"

    logger.debug(f"PSI → score={psi:.4f} severity={severity} drift={drift}")

    return {
        "psi_score": round(psi, 6),
        "statistic": round(psi, 6),
        "drift_detected": drift,
        "threshold": threshold,
        "severity": severity,
        "bin_edges": [round(float(e), 6) for e in bin_edges],
        "ref_counts": ref_counts.tolist(),
        "cur_counts": cur_counts.tolist(),
    }


def run_full_drift_check(
    reference: List[float],
    current: List[float],
    bin_edges: Optional[List[float]] = None,
    ks_threshold: float = KS_P_VALUE_THRESHOLD,
    psi_threshold: float = PSI_HIGH_THRESHOLD,
) -> dict:
    """Run both KS and PSI, return combined result."""
    ks = ks_test(reference, current, threshold=ks_threshold)
    psi = compute_psi(reference, current, threshold=psi_threshold, bin_edges=bin_edges)

    drift_detected = ks["drift_detected"] or psi["drift_detected"]

    return {
        "ks": ks,
        "psi": psi,
        "drift_detected": drift_detected,
        "sample_size": len(current),
    }
