"""Small robustness sweep for CABDI non-monotone routing claim (synthetic only)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import sys
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from policies.cabdi_regime_aware import make_cabdi_regime_policy
from policies.monotone_help import make_monotone_help_policy
from sim.risk_models import aggregate_policy_metrics
from sim.tasks import TaskFamilyScenario, run_task_family


@dataclass(frozen=True)
class RegionSetting:
    setting_id: str
    overload_curvature: float
    catastrophic_risk_weight: float
    verification_saturation: float
    observation_noise: float
    regime_threshold_name: str
    regime_thresholds: tuple[float, float]


def _small_settings() -> list[RegionSetting]:
    thresholds = {
        "early_overload": (0.35, 0.66),
        "default": (0.40, 0.72),
        "late_overload": (0.45, 0.78),
    }
    settings: list[RegionSetting] = []
    idx = 0
    for curvature in (0.9, 1.3):
        for risk_weight in (0.8, 1.2):
            for sat in (0.8, 1.2):
                for noise in (0.8, 1.2):
                    regime_name = "default" if idx % 2 == 0 else "early_overload"
                    if idx % 5 == 0:
                        regime_name = "late_overload"
                    idx += 1
                    settings.append(
                        RegionSetting(
                            setting_id=f"scan_{idx:02d}",
                            overload_curvature=curvature,
                            catastrophic_risk_weight=risk_weight,
                            verification_saturation=sat,
                            observation_noise=noise,
                            regime_threshold_name=regime_name,
                            regime_thresholds=thresholds[regime_name],
                        )
                    )
    return settings


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _classify(mean_delta: float, std_delta: float, n: int, margin: float = 0.03) -> str:
    if n < 2:
        return "inconclusive"
    ci95 = 1.96 * (std_delta / (n ** 0.5))
    if abs(mean_delta) <= margin:
        return "matches_monotone"
    if (mean_delta - ci95) > 0:
        return "supports_cabdi_non_monotone"
    if (mean_delta + ci95) < 0:
        return "monotone_stronger"
    return "inconclusive"


def _write_scatter_svg(path: Path, rows: list[dict]) -> None:
    width, height, m = 760, 300, 35
    classes = {
        "supports_cabdi_non_monotone": "#2ca02c",
        "matches_monotone": "#4e79a7",
        "monotone_stronger": "#d62728",
        "inconclusive": "#f28e2b",
    }
    xs = [r["overload_curvature"] for r in rows]
    ys = [r["delta_catastrophic_risk"] for r in rows]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    def sx(x: float) -> float:
        return m + (x - x_min) / max(1e-9, x_max - x_min) * (width - 2 * m)

    def sy(y: float) -> float:
        return height - m - (y - y_min) / max(1e-9, y_max - y_min) * (height - 2 * m)

    circles = []
    for r in rows:
        circles.append(
            f'<circle cx="{sx(r["overload_curvature"]):.1f}" cy="{sy(r["delta_catastrophic_risk"]):.1f}" r="5" fill="{classes[r["region_class"]]}" />'
        )

    path.write_text(
        "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
                '<rect width="100%" height="100%" fill="white"/>',
                f'<text x="10" y="18" font-size="13">Delta catastrophic risk (monotone - CABDI) by overload curvature</text>',
                f'<line x1="{m}" y1="{height-m}" x2="{width-m}" y2="{height-m}" stroke="#333"/>',
                f'<line x1="{m}" y1="{m}" x2="{m}" y2="{height-m}" stroke="#333"/>',
                *circles,
                '</svg>',
            ]
        ),
        encoding="utf-8",
    )


def _write_class_counts_svg(path: Path, rows: list[dict]) -> None:
    width, height, m = 760, 280, 40
    order = ["supports_cabdi_non_monotone", "matches_monotone", "monotone_stronger", "inconclusive"]
    counts = {k: sum(1 for r in rows if r["region_class"] == k) for k in order}
    colors = ["#2ca02c", "#4e79a7", "#d62728", "#f28e2b"]
    max_count = max(counts.values()) if counts else 1
    bar_w = (width - 2 * m) // len(order)
    bars = []
    for i, key in enumerate(order):
        h = int((height - 2 * m) * (counts[key] / max_count)) if max_count else 0
        x = m + i * bar_w
        y = height - m - h
        bars.append(f'<rect x="{x}" y="{y}" width="{bar_w-12}" height="{h}" fill="{colors[i]}"/>')
        bars.append(f'<text x="{x}" y="{height-16}" font-size="11">{key}</text>')
        bars.append(f'<text x="{x}" y="{max(14, y-4)}" font-size="11">{counts[key]}</text>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<rect width="100%" height="100%" fill="white"/>
<text x="10" y="18" font-size="13">Region count by synthetic outcome class</text>
{''.join(bars)}
</svg>'''
    path.write_text(svg, encoding="utf-8")


def _report(path: Path, rows: list[dict]) -> None:
    classes = {
        "supports_cabdi_non_monotone": [r for r in rows if r["region_class"] == "supports_cabdi_non_monotone"],
        "monotone_stronger": [r for r in rows if r["region_class"] == "monotone_stronger"],
        "matches_monotone": [r for r in rows if r["region_class"] == "matches_monotone"],
        "inconclusive": [r for r in rows if r["region_class"] == "inconclusive"],
    }

    def top(rows_subset: list[dict], n: int = 3) -> str:
        if not rows_subset:
            return "- none"
        ordered = sorted(rows_subset, key=lambda r: r["delta_catastrophic_risk"], reverse=True)
        return "\n".join(
            f"- {r['setting_id']}: delta_risk={r['delta_catastrophic_risk']:.4f}, thresholds={r['regime_threshold_name']}, noise={r['observation_noise']}, sat={r['verification_saturation']}"
            for r in ordered[:n]
        )

    lines = [
        "# Non-Monotone CABDI Region Scan (Synthetic Only)",
        "",
        "This scan is a small synthetic robustness map. It is not real-world validation.",
        "",
        "## Setup",
        "- Compared `cabdi-regime-aware` vs `monotone-help` under matched compute budgets (compute_units=1.0 each step).",
        "- Swept overload curvature, catastrophic-risk weight, verification saturation, observation noise, and CABDI regime thresholds.",
        "- Used deterministic seeds per setting and policy.",
        "",
        "## Regions supporting CABDI-style non-monotone advantage",
        top(classes["supports_cabdi_non_monotone"]),
        "",
        "## Regions where monotone-help is stronger",
        top(classes["monotone_stronger"]),
        "",
        "## Regions where outcomes match or are inconclusive",
        f"- matches_monotone: {len(classes['matches_monotone'])} settings",
        f"- inconclusive: {len(classes['inconclusive'])} settings",
        "",
        "## Interpretation discipline",
        "- These findings only narrow/support/falsify the non-monotone routing claim within stylized simulation.",
        "- No real-world human, cognition, or physiology claim is made.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    out_dir = Path("artifacts/non_monotone_region_scan")
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = [41, 43, 47]
    episodes = 18
    horizon = 55
    rows: list[dict] = []

    for setting in _small_settings():
        scenario = TaskFamilyScenario(
            overload_curvature=setting.overload_curvature,
            catastrophic_risk_weight_scale=setting.catastrophic_risk_weight,
            verification_saturation=setting.verification_saturation,
            observation_noise=setting.observation_noise,
        )
        delta_risks = []
        delta_accuracy = []
        mono_compute = 0.0
        cabdi_compute = 0.0
        for seed in seeds:
            mono = run_task_family(
                policy_name="monotone-help",
                policy_fn=make_monotone_help_policy(),
                observation_mode="behavior_only",
                seed=seed,
                episodes=episodes,
                horizon=horizon,
                scenario=scenario,
            )
            cabdi = run_task_family(
                policy_name="cabdi-regime-aware",
                policy_fn=make_cabdi_regime_policy(thresholds=setting.regime_thresholds),
                observation_mode="behavior_only",
                seed=seed,
                episodes=episodes,
                horizon=horizon,
                scenario=scenario,
            )
            mono_metrics = aggregate_policy_metrics(mono)
            cabdi_metrics = aggregate_policy_metrics(cabdi)
            delta_risks.append(mono_metrics["catastrophic_risk_proxy"] - cabdi_metrics["catastrophic_risk_proxy"])
            delta_accuracy.append(cabdi_metrics["accuracy"] - mono_metrics["accuracy"])
            mono_compute += mono_metrics["compute_usage"]
            cabdi_compute += cabdi_metrics["compute_usage"]

        mean_delta_risk = mean(delta_risks)
        std_delta_risk = stdev(delta_risks) if len(delta_risks) > 1 else 0.0
        region_class = _classify(mean_delta_risk, std_delta_risk, len(delta_risks))

        rows.append(
            {
                "setting_id": setting.setting_id,
                "overload_curvature": setting.overload_curvature,
                "catastrophic_risk_weight": setting.catastrophic_risk_weight,
                "verification_saturation": setting.verification_saturation,
                "observation_noise": setting.observation_noise,
                "regime_threshold_name": setting.regime_threshold_name,
                "regime_low_threshold": setting.regime_thresholds[0],
                "regime_overload_threshold": setting.regime_thresholds[1],
                "delta_catastrophic_risk": round(mean_delta_risk, 6),
                "delta_catastrophic_risk_std": round(std_delta_risk, 6),
                "delta_accuracy": round(mean(delta_accuracy), 6),
                "matched_compute_budget": abs(mono_compute - cabdi_compute) < 1e-9,
                "region_class": region_class,
            }
        )

    _write_csv(out_dir / "region_scan_summary.csv", rows)
    _write_scatter_svg(out_dir / "delta_risk_scatter.svg", rows)
    _write_class_counts_svg(out_dir / "region_class_counts.svg", rows)
    _report(Path("reports/non_monotone_region_scan.md"), rows)

    print(f"Wrote region scan artifacts to: {out_dir}")
    print(f"Settings scanned: {len(rows)}")


if __name__ == "__main__":
    main()
