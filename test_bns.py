"""Тесты разбора данных БНС (Taldau). Сеть не требуется."""

from datetime import date

import pytest

from etl import (
    Obs,
    Series,
    SourceError,
    freshness,
    parse_bns_date,
    parse_bns_dynamics,
    validate,
)

SPEC = {"index_id": 2709379, "scale": 1e-12}


class TestParseDate:
    def test_year_code_keeps_year_only(self):
        assert parse_bns_date("122025", "A") == "2025"

    def test_quarter_code_uses_last_month_of_quarter(self):
        assert parse_bns_date("032026", "Q") == "2026-Q1"
        assert parse_bns_date("122025", "Q") == "2025-Q4"

    def test_month_code(self):
        assert parse_bns_date("072026", "M") == "2026-07"

    def test_quarter_codes_sort_chronologically(self):
        """Гейт на возрастание дат отвергнет ряд, если формат не сортируемый."""
        codes = ["032025", "062025", "092025", "122025", "032026"]
        parsed = [parse_bns_date(c, "Q") for c in codes]
        assert parsed == sorted(parsed)

    def test_broken_code_raises(self):
        with pytest.raises(SourceError):
            parse_bns_date("2025", "A")

    def test_quarter_code_not_on_quarter_boundary_raises(self):
        with pytest.raises(SourceError):
            parse_bns_date("072025", "Q")


class TestParseDynamics:
    def payload(self, **over):
        data = {
            "dateList": ["122023", "122024", "122025"],
            "valueList": ["119442289700000", "136693318300000", "159608552900000"],
        }
        data.update(over)
        return data

    def test_scale_applied_and_sorted(self):
        obs = parse_bns_dynamics(self.payload(), SPEC, "A")
        assert [o.date for o in obs] == ["2023", "2024", "2025"]
        assert obs[-1].value == pytest.approx(159.6, abs=0.1)

    def test_gaps_are_skipped_not_zeroed(self):
        """Пропуск в источнике это отсутствие данных, а не ноль."""
        obs = parse_bns_dynamics(
            self.payload(valueList=["119442289700000", "", "159608552900000"]),
            SPEC,
            "A",
        )
        assert [o.date for o in obs] == ["2023", "2025"]

    def test_empty_payload_raises(self):
        with pytest.raises(SourceError):
            parse_bns_dynamics({"dateList": [], "valueList": []}, SPEC, "A")

    def test_length_mismatch_raises(self):
        with pytest.raises(SourceError):
            parse_bns_dynamics(self.payload(valueList=["1"]), SPEC, "A")


class TestFreshness:
    def test_quarter_tolerates_publication_lag(self):
        """Квартал публикуется с лагом, свежий квартальный ряд не должен браковаться."""
        last_quarter = f"{date.today().year}-Q1"
        age, limit = freshness(last_quarter, "Q")
        assert age <= limit or date.today().month > 10

    def test_stale_quarter_is_caught(self):
        age, limit = freshness("2020-Q1", "Q")
        assert age > limit

    def test_series_with_quarterly_dates_passes_validation(self):
        series = Series(
            series_id="kz.wage.avg",
            name_ru="Среднемесячная зарплата",
            unit="тенге",
            freq="Q",
            source="Бюро национальной статистики",
            source_url="https://example.org",
            fetched_at="2026-09-03T00:00:00+00:00",
            obs=[Obs(date=f"{date.today().year}-Q1", value=461486.0)],
        )
        assert validate(series, {"min": 10000, "max": 5000000}) == []
