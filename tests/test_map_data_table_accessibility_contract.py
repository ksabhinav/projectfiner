from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "src/components/map/MapDataTable.svelte"
PAGE = ROOT / "src/pages/index.astro"


def test_map_exposes_a_searchable_semantic_data_table():
    component = COMPONENT.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")

    assert "<MapDataTable client:load />" in page
    assert 'role="dialog"' in component
    assert 'aria-modal="true"' in component
    assert '<table>' in component
    assert '<caption>' in component
    assert 'scope="col"' in component
    assert 'scope="row"' in component
    assert 'aria-live="polite"' in component
    assert 'Filter by district or state' in component


def test_map_table_uses_the_same_rows_as_the_visual_map_and_includes_missingness():
    component = COMPONENT.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")

    assert "onFiner('legendUpdate', sync)" in component
    assert "status: status" in page
    assert "value: hasValue ? data.value : ''" in page
    assert "exportRows.push({" in page
    assert "No data" in component


def test_map_table_restores_focus_and_can_open_a_district():
    component = COMPONENT.read_text(encoding="utf-8")

    assert "trigger?.focus()" in component
    assert "event.key === 'Escape'" in component
    assert "event.key !== 'Tab'" in component
    assert "finer:focusDistrict" in component
