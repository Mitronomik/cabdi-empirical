"""Run minimal first validation for CABDI synthetic scaffold."""

from __future__ import annotations

import csv
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.admissibility import AdmissibilityThresholds, evaluate_admissibility
from models.fd_arx import LinearARXFd
from models.fd_narx import ConstrainedNARXFd
from models.fd_piecewise_affine import PiecewiseAffineFd
from policies.cabdi_regime_aware import make_cabdi_regime_policy
from policies.monotone_help import make_monotone_help_policy
from policies.static_help import make_static_help_policy
from sim.risk_models import aggregate_policy_metrics
from sim.tasks import run_task_family


@dataclass
class MinimalConfig:
    seed: int = 11
    episodes: int = 30
    horizon: int = 60


def _build_policies(mode: str):
    return {
        "static-help": make_static_help_policy(),
        "monotone-help": make_monotone_help_policy(),
        "cabdi-regime-aware": make_cabdi_regime_policy(use_physiology=(mode == "behavior_plus_physio")),
    }


def _fd_dataset(records):
    d, a, e = [], [], []
    for r in records:
        d.append(max(0.0, min(1.0, 0.65 * r.behavior_load_proxy + 0.35 * (1.0 - r.behavior_oversight_proxy))))
        a.append(r.help_level)
        e.append(r.task_evidence)
    return d, a, e


def _write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_simple_svg(path: Path, rows: list[dict]):
    width, height = 760, 260
    margin = 40
    bars = []
    cat_vals = [r["catastrophic_risk_proxy"] for r in rows]
    vmax = max(cat_vals) if cat_vals else 1.0
    bar_w = max(14, (width - 2 * margin) // max(1, len(rows)))
    for i, r in enumerate(rows):
        h = int((height - 2 * margin) * (r["catastrophic_risk_proxy"] / max(vmax, 1e-6)))
        x = margin + i * bar_w
        y = height - margin - h
        color = "#4e79a7" if r["observation_mode"] == "behavior_only" else "#f28e2b"
        bars.append(f'<rect x="{x}" y="{y}" width="{bar_w-2}" height="{h}" fill="{color}" />')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<rect width="100%" height="100%" fill="white"/>
<text x="20" y="20" font-size="14">Catastrophic-risk proxy (lower is better)</text>
{''.join(bars)}
</svg>'''
    path.write_text(svg, encoding="utf-8")


def _write_report(report_path: Path, metrics_rows: list[dict], fd_rows: list[dict], strongest_behavior_policy: str):
    def rows_md(rows):
        if not rows:
            return "(no rows)"
        cols = list(rows[0].keys())
        lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for r in rows:
            lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
        return "\n".join(lines)

    lines = [
        "# Minimal First Validation (Synthetic, Falsification-Oriented)",
        "",
        "This report summarizes a stylized simulation only. It does not establish real-world validity.",
        "",
        "## Supported claims",
        f"- In this stylized setup, `{strongest_behavior_policy}` was strongest in behavior-only mode by risk-first ranking.",
        "- Non-monotone routing can be evaluated directly under overload and catastrophic-weighted errors.",
        "",
        "## Unsupported claims",
        "- No real-world cognitive, physiological, or universal human-AI performance claim is supported.",
        "",
        "## Inconclusive / narrowed claims",
        "- Physiology-like auxiliary channel is only incremental and synthetic in this scaffold.",
        "- Any non-admitted F_d model is excluded from theorem-facing interpretation.",
        "",
        "## Policy metrics",
        rows_md(metrics_rows),
        "",
        "## F_d admissibility diagnostics",
        rows_md(fd_rows),
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    cfg = MinimalConfig()
    out_dir = Path("artifacts/minimal_first_validation")
    out_dir.mkdir(parents=True, exist_ok=True)

    all_records = []
    summary_rows = []

    for mode in ["behavior_only", "behavior_plus_physio"]:
        for i, (name, policy) in enumerate(_build_policies(mode).items()):
            recs = run_task_family(policy_name=name, policy_fn=policy, observation_mode=mode, seed=cfg.seed + 101 * i + (17 if mode == "behavior_plus_physio" else 0), episodes=cfg.episodes, horizon=cfg.horizon)
            all_records.extend(recs)
            metrics = aggregate_policy_metrics(recs)
            summary_rows.append({"policy": name, "observation_mode": mode, **metrics})

    behavior = [r for r in summary_rows if r["observation_mode"] == "behavior_only"]
    strongest_behavior_policy = sorted(behavior, key=lambda r: (r["catastrophic_risk_proxy"], r["commission_error_proxy"]))[0]["policy"]

    strongest_logs = [r for r in all_records if r.observation_mode == "behavior_only" and r.policy_name == strongest_behavior_policy]
    d, a, e = _fd_dataset(strongest_logs)
    split = int(0.7 * len(d))
    d_train, a_train, e_train = d[:split], a[:split], e[:split]
    d_eval, a_eval, e_eval = d[split:], a[split:], e[split:]

    fd_models = {
        "linear_arx": LinearARXFd().fit(d_train, a_train, e_train),
        "piecewise_affine": PiecewiseAffineFd().fit(d_train, a_train, e_train),
        "constrained_narx": ConstrainedNARXFd().fit(d_train, a_train, e_train),
    }

    thresholds = AdmissibilityThresholds()
    fd_rows = []
    for name, model in fd_models.items():
        fd_rows.append({"fd_model": name, **evaluate_admissibility(model, d_train, d_eval, a_eval, e_eval, thresholds)})

    _write_csv(out_dir / "policy_metrics.csv", summary_rows)
    _write_csv(out_dir / "fd_admissibility.csv", fd_rows)
    _write_csv(out_dir / "step_logs.csv", [asdict(r) for r in all_records])
    _write_simple_svg(out_dir / "catastrophic_risk_comparison.svg", summary_rows)
    _write_report(Path("reports/minimal_first_validation.md"), summary_rows, fd_rows, strongest_behavior_policy)

    admitted = [r["fd_model"] for r in fd_rows if r["admitted"]]
    print(f"Wrote artifacts to: {out_dir}")
    print(f"Strongest behavior-only baseline: {strongest_behavior_policy}")
    print(f"Admitted F_d models: {admitted}")


if __name__ == "__main__":
    main()
