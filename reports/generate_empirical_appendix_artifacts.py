"""Generate standardized report figures/tables and a conservative empirical appendix draft.

This script reads existing synthetic experiment outputs under ``artifacts/`` and writes
report-ready assets under ``reports/figures`` and ``reports/tables``.
"""

from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = ROOT / "artifacts"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
TABLES_DIR = REPORTS_DIR / "tables"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _to_float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def _policy_comparison_figure(rows: list[dict[str, str]], out_path: Path) -> None:
    width, height = 920, 360
    margin = 45
    chart_h = height - 2 * margin
    groups = ["behavior_only", "behavior_plus_physio"]
    policies = ["static-help", "monotone-help", "cabdi-regime-aware"]
    colors = {
        "static-help": "#9c755f",
        "monotone-help": "#4e79a7",
        "cabdi-regime-aware": "#59a14f",
    }

    by_mode = {g: [r for r in rows if r["observation_mode"] == g] for g in groups}
    risk_values = [_to_float(r, "catastrophic_risk_proxy") for r in rows]
    vmax = max(risk_values) if risk_values else 1.0

    section_w = (width - 2 * margin) // len(groups)
    bar_w = max(20, int((section_w - 70) / len(policies)))
    bars: list[str] = []
    labels: list[str] = []

    for gi, group in enumerate(groups):
        x0 = margin + gi * section_w
        labels.append(f'<text x="{x0 + 8}" y="{height-12}" font-size="12">{group}</text>')
        row_by_policy = {r["policy"]: r for r in by_mode[group]}
        for pi, policy in enumerate(policies):
            row = row_by_policy[policy]
            val = _to_float(row, "catastrophic_risk_proxy")
            bar_h = int(chart_h * (val / max(vmax, 1e-9)))
            x = x0 + 28 + pi * (bar_w + 12)
            y = height - margin - bar_h
            bars.append(
                f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="{colors[policy]}" />'
            )
            labels.append(f'<text x="{x}" y="{height-margin+16}" font-size="11">{policy}</text>')
            labels.append(f'<text x="{x}" y="{max(18, y-4)}" font-size="11">{val:.3f}</text>')

    legend = [
        '<text x="14" y="22" font-size="14">Policy comparison: catastrophic-risk proxy (lower is better)</text>',
    ]
    out_path.write_text(
        "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
                '<rect width="100%" height="100%" fill="white"/>',
                f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#333"/>',
                f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#333"/>',
                *legend,
                *bars,
                *labels,
                "</svg>",
            ]
        ),
        encoding="utf-8",
    )


def _fd_admissibility_figure(rows: list[dict[str, str]], out_path: Path) -> None:
    width, height = 920, 340
    margin = 42
    metrics = [
        ("one_step_prediction_error", "one-step"),
        ("rollout_error", "rollout"),
        ("local_gain_proxy", "gain"),
        ("envelope_violation_rate", "envelope"),
        ("out_of_support_warning_rate", "oos"),
    ]
    cols = len(metrics)
    rows_n = len(rows)
    cell_w = (width - 2 * margin) / cols
    cell_h = (height - 2 * margin) / max(1, rows_n)

    max_by_metric = {
        m: max(_to_float(r, m) for r in rows) if rows else 1.0 for m, _ in metrics
    }

    rects: list[str] = []
    texts: list[str] = []
    for ri, row in enumerate(rows):
        y = margin + ri * cell_h
        texts.append(f'<text x="8" y="{y + 20:.1f}" font-size="12">{row["fd_model"]}</text>')
        texts.append(
            f'<text x="{width-120}" y="{y + 20:.1f}" font-size="12">admitted={row["admitted"]}</text>'
        )
        for ci, (metric, short) in enumerate(metrics):
            val = _to_float(row, metric)
            frac = val / max(max_by_metric[metric], 1e-9)
            shade = int(245 - 120 * frac)
            color = f"rgb(80,{shade},120)"
            x = margin + ci * cell_w
            rects.append(
                f'<rect x="{x+4:.1f}" y="{y+4:.1f}" width="{cell_w-8:.1f}" height="{cell_h-8:.1f}" fill="{color}" />'
            )
            texts.append(
                f'<text x="{x+8:.1f}" y="{y + cell_h/2 + 4:.1f}" font-size="11" fill="black">{short}={val:.4f}</text>'
            )

    out_path.write_text(
        "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
                '<rect width="100%" height="100%" fill="white"/>',
                '<text x="12" y="20" font-size="14">F_d admissibility diagnostics summary (synthetic)</text>',
                *rects,
                *texts,
                '</svg>',
            ]
        ),
        encoding="utf-8",
    )


def _catastrophic_risk_region_figure(rows: list[dict[str, str]], out_path: Path) -> None:
    width, height, m = 820, 320, 44
    xs = [_to_float(r, "overload_curvature") for r in rows]
    ys = [_to_float(r, "delta_catastrophic_risk") for r in rows]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    classes = {
        "supports_cabdi_non_monotone": "#2ca02c",
        "matches_monotone": "#4e79a7",
        "monotone_stronger": "#d62728",
        "inconclusive": "#f28e2b",
    }

    def sx(x: float) -> float:
        return m + (x - x_min) / max(1e-9, x_max - x_min) * (width - 2 * m)

    def sy(y: float) -> float:
        return height - m - (y - y_min) / max(1e-9, y_max - y_min) * (height - 2 * m)

    circles: list[str] = []
    for r in rows:
        circles.append(
            f'<circle cx="{sx(_to_float(r, "overload_curvature")):.1f}" cy="{sy(_to_float(r, "delta_catastrophic_risk")):.1f}" r="5" fill="{classes[r["region_class"]]}" />'
        )

    out_path.write_text(
        "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
                '<rect width="100%" height="100%" fill="white"/>',
                '<text x="10" y="18" font-size="13">Existing catastrophic-risk comparison: delta risk (monotone - CABDI)</text>',
                f'<line x1="{m}" y1="{height-m}" x2="{width-m}" y2="{height-m}" stroke="#333"/>',
                f'<line x1="{m}" y1="{m}" x2="{m}" y2="{height-m}" stroke="#333"/>',
                *circles,
                '</svg>',
            ]
        ),
        encoding="utf-8",
    )


def _markdown_table(rows: list[dict], cols: list[str]) -> str:
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def _build_appendix(
    policy_rows: list[dict[str, str]],
    fd_rows: list[dict[str, str]],
    region_rows: list[dict[str, str]],
) -> str:
    behavior_rows = [r for r in policy_rows if r["observation_mode"] == "behavior_only"]
    risk_sorted = sorted(behavior_rows, key=lambda r: float(r["catastrophic_risk_proxy"]))
    best_behavior = risk_sorted[0]["policy"] if risk_sorted else "n/a"

    supported = [
        {
            "claim": "Behavior-first policy comparison is executable and reproducible in this synthetic setup",
            "status": "supported",
            "evidence": "policy_metrics_summary.csv",
            "notes": f"All three baselines ran in behavior-only mode; best risk-first ranking was {best_behavior}.",
        },
        {
            "claim": "Admitted F_d model family can be operationalized with diagnostics",
            "status": "supported",
            "evidence": "fd_admissibility_summary.csv",
            "notes": "ARX, piecewise-affine, and constrained NARX each produced admissibility diagnostics.",
        },
    ]

    unsupported = [
        {
            "claim": "CABDI non-monotone policy is globally stronger across scanned synthetic regions",
            "status": "unsupported",
            "evidence": "catastrophic_risk_region_comparison.svg + catastrophic_risk_region_scan_summary.csv",
            "notes": "Current region scan rows are classified as monotone_stronger.",
        },
    ]

    inconclusive = [
        {
            "claim": "Optional physiology-like input provides reliable incremental value over strongest behavior-only baseline",
            "status": "inconclusive",
            "evidence": "policy_metrics_summary.csv",
            "notes": "Incremental effects exist in this run but are narrow and synthetic-only; no theorem-facing physiology claim.",
        },
    ]

    all_claim_rows = supported + unsupported + inconclusive

    lines = [
        "# Empirical Appendix Draft (Synthetic, Conservative)",
        "",
        "This appendix summarizes synthetic experiment outputs only. It does not establish real-world validation.",
        "",
        "## Setup",
        "- Inputs inspected: minimal first validation artifacts, non-monotone region scan artifacts, and current report markdown files.",
        "- Seeded synthetic runs are treated as falsification scaffolds, not field evidence.",
        "- Output standardization target: `reports/figures/` and `reports/tables/`.",
        "",
        "## Baselines",
        "- static-help",
        "- monotone-help",
        "- cabdi-regime-aware non-monotone routing",
        "- observation modes: behavior-only and behavior+optional physiology-like auxiliary channel",
        "",
        "## F_d model family",
        "- Linear ARX surrogate",
        "- Piecewise-affine surrogate",
        "- Constrained nonlinear NARX surrogate",
        "- Each candidate is assessed using one-step error, rollout error, local gain proxy, envelope violations, and out-of-support warning rate.",
        "",
        "## Diagnostics",
        "- Policy-level: accuracy, catastrophic-risk proxy, commission-error proxy, recovery lag, compute usage.",
        "- F_d admissibility diagnostics are summarized in table + figure assets.",
        "- Region scan includes delta catastrophic-risk (monotone - CABDI) and class labels.",
        "",
        "## Main findings (strictly synthetic)",
        f"- Behavior-only risk-first ranking in current outputs: `{best_behavior}` is best in this run.",
        "- F_d diagnostics are available for all three required surrogate classes.",
        "- Existing non-monotone region scan currently does not show regions classified as supporting CABDI non-monotone advantage.",
        "",
        "## Limits of synthetic evidence",
        "- No claim about real-world cognition, physiology, or universal human-AI superiority is supported here.",
        "- Synthetic improvements are not translated into deployment claims.",
        "- Results should be interpreted as support/falsification/narrowing only within stylized simulation.",
        "",
        "## Supported / unsupported / inconclusive claims",
        _markdown_table(all_claim_rows, ["claim", "status", "evidence", "notes"]),
    ]

    return "\n".join(lines) + "\n"


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    policy_rows = _read_csv(ARTIFACTS_DIR / "minimal_first_validation" / "policy_metrics.csv")
    fd_rows = _read_csv(ARTIFACTS_DIR / "minimal_first_validation" / "fd_admissibility.csv")
    region_rows = _read_csv(ARTIFACTS_DIR / "non_monotone_region_scan" / "region_scan_summary.csv")

    policy_table_rows = [
        {
            "policy": r["policy"],
            "observation_mode": r["observation_mode"],
            "accuracy": f"{float(r['accuracy']):.4f}",
            "catastrophic_risk_proxy": f"{float(r['catastrophic_risk_proxy']):.4f}",
            "commission_error_proxy": f"{float(r['commission_error_proxy']):.4f}",
            "recovery_lag": f"{float(r['recovery_lag']):.4f}",
            "compute_usage": f"{float(r['compute_usage']):.1f}",
        }
        for r in policy_rows
    ]
    _write_csv(
        TABLES_DIR / "policy_metrics_summary.csv",
        policy_table_rows,
        [
            "policy",
            "observation_mode",
            "accuracy",
            "catastrophic_risk_proxy",
            "commission_error_proxy",
            "recovery_lag",
            "compute_usage",
        ],
    )

    fd_table_rows = [
        {
            "fd_model": r["fd_model"],
            "one_step_prediction_error": f"{float(r['one_step_prediction_error']):.6f}",
            "rollout_error": f"{float(r['rollout_error']):.6f}",
            "local_gain_proxy": f"{float(r['local_gain_proxy']):.6f}",
            "envelope_violation_rate": f"{float(r['envelope_violation_rate']):.6f}",
            "out_of_support_warning_rate": f"{float(r['out_of_support_warning_rate']):.6f}",
            "admitted": r["admitted"],
        }
        for r in fd_rows
    ]
    _write_csv(
        TABLES_DIR / "fd_admissibility_summary.csv",
        fd_table_rows,
        [
            "fd_model",
            "one_step_prediction_error",
            "rollout_error",
            "local_gain_proxy",
            "envelope_violation_rate",
            "out_of_support_warning_rate",
            "admitted",
        ],
    )

    class_counts: dict[str, int] = {}
    for row in region_rows:
        class_counts[row["region_class"]] = class_counts.get(row["region_class"], 0) + 1
    region_table_rows = [
        {
            "region_class": k,
            "count": v,
            "mean_delta_catastrophic_risk": f"{mean([float(r['delta_catastrophic_risk']) for r in region_rows if r['region_class'] == k]):.6f}",
        }
        for k, v in sorted(class_counts.items())
    ]
    _write_csv(
        TABLES_DIR / "catastrophic_risk_region_scan_summary.csv",
        region_table_rows,
        ["region_class", "count", "mean_delta_catastrophic_risk"],
    )

    _policy_comparison_figure(policy_rows, FIGURES_DIR / "policy_comparison.svg")
    _fd_admissibility_figure(fd_rows, FIGURES_DIR / "fd_admissibility_summary.svg")
    _catastrophic_risk_region_figure(region_rows, FIGURES_DIR / "catastrophic_risk_region_comparison.svg")

    appendix = _build_appendix(policy_rows, fd_rows, region_rows)
    (REPORTS_DIR / "empirical_appendix_draft.md").write_text(appendix, encoding="utf-8")

    print(f"Wrote figures to: {FIGURES_DIR}")
    print(f"Wrote tables to: {TABLES_DIR}")
    print("Wrote appendix draft: reports/empirical_appendix_draft.md")


if __name__ == "__main__":
    main()
