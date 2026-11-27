from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SYNTHESIS_PATH = ROOT / "docs" / "RESEARCH_SYNTHESIS.md"


def _synthesis() -> str:
    return SYNTHESIS_PATH.read_text(encoding="utf-8")


def test_research_synthesis_covers_five_defect_families_and_three_seeds():
    content = _synthesis().lower()
    for defect in (
        "missingness",
        "exact duplicate",
        "categorical consistency",
        "invalid numeric",
        "numerical anomalies",
    ):
        assert defect in content
    assert "1%, 5%, and 10%" in content
    assert "42, 123, and 2026" in content
    assert "45 rate/seed trials and 135 ridge fits" in content


def test_research_synthesis_preserves_rolling_origin_aggregates_and_uncertainty_label():
    content = _synthesis()
    for value in (
        "102.337591",
        "14.717943",
        "134.584052",
        "16.832018",
        "0.610930",
        "0.007623",
    ):
        assert value in content
    assert "not random-seed uncertainty" in content
    assert "not a confidence interval" in content


def test_research_synthesis_records_scope_cuts_and_generalization_limits():
    content = _synthesis().lower()
    for limitation in (
        "not estimates of real-world defect prevalence",
        "controlled scaling study",
        "hybrid versus individual",
        "python allocation proxy",
        "not be described as a production-ready platform",
    ):
        assert limitation in content
