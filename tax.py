"""Справочник налоговых ставок и порогов Казахстана на 2026 год.

Это не временной ряд и не результат ETL: источник здесь Налоговый кодекс, а не
машинный интерфейс. Поэтому у каждой позиции своя дата ревизии и ссылка на норму,
а не отметка о времени загрузки.

Все величины, выраженные в МРП и МЗП, считаются из базовых констант, а не вбиваются
готовыми числами: при смене МРП пересчитается весь справочник, и арифметическая
ошибка в производной величине становится невозможной.

Запуск: .venv/bin/python tax.py out/tax.json
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / "out" / "tax.json"

YEAR = 2026
# Закон РК «О республиканском бюджете на 2026-2028 годы» от 08.12.2025, статья 7.
MRP = 4325
MZP = 85000

BUDGET_LAW = "Закон РК о республиканском бюджете на 2026-2028 годы, ст. 7"
TAX_CODE = "НК РК (Закон № 214-VIII от 18.07.2025)"

# Дата, когда справочник последний раз сверялся с первоисточниками. Показывается
# на странице: справочник без даты ревизии выглядит вечно актуальным, а он не такой.
REVIEWED_AT = "2026-09-03"


def mrp(n: float) -> int:
    return round(n * MRP)


def mzp(n: float) -> int:
    return round(n * MZP)


def money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " тг"


BASE = [
    {
        "name": "МРП, месячный расчётный показатель",
        "value": money(MRP),
        "basis": BUDGET_LAW,
    },
    {
        "name": "МЗП, минимальная заработная плата",
        "value": money(MZP),
        "basis": BUDGET_LAW,
    },
    {
        "name": "Базовый вычет по ИПН, 30 МРП в месяц",
        "value": money(mrp(30)),
        "basis": TAX_CODE,
    },
    {
        "name": "Порог регистрации по НДС, 10 000 МРП в год",
        "value": money(mrp(10_000)),
        "basis": TAX_CODE,
    },
    {
        "name": "Порог ставки ИПН 15%, 8 500 МРП в год",
        "value": money(mrp(8_500)),
        "basis": TAX_CODE,
    },
]

GROUPS = [
    {
        "id": "vat",
        "title": "НДС",
        "note": "Ставка выросла с 12% до 16%, порог регистрации снижен вдвое.",
        "items": [
            {"name": "Стандартная ставка", "value": "16%", "was": "было 12%"},
            {"name": "Медицина и медизделия", "value": "5%", "was": "с 2027 года 10%"},
            {"name": "Экспорт", "value": "0%", "was": ""},
            {
                "name": "Аренда и продажа жилья",
                "value": "16%",
                "was": "до 2026 освобождение",
            },
            {
                "name": "Порог обязательной регистрации",
                "value": money(mrp(10_000)) + " в год",
                "was": "было 20 000 МРП",
            },
        ],
    },
    {
        "id": "cit",
        "title": "КПН, корпоративный подоходный налог",
        "note": "Ставка зависит от вида деятельности, а не только от размера бизнеса.",
        "items": [
            {"name": "Стандартная ставка", "value": "20%", "was": ""},
            {
                "name": "Образование и медицина",
                "value": "5%",
                "was": "с 2027 года 10%",
            },
            {"name": "Сельхозпроизводители", "value": "3%", "was": "было 10%"},
            {"name": "Сельхозкооперативы", "value": "6%", "was": ""},
            {
                "name": "Банки (кроме кредитования МСБ), казино, букмекеры",
                "value": "25%",
                "was": "",
            },
            {
                "name": "Дивиденды резидентам",
                "value": "5% до " + money(mrp(230_000)) + ", далее 15%",
                "was": "освобождение до 30 000 МРП отменено",
            },
            {
                "name": "Роялти и управленческие услуги нерезидентам",
                "value": "15%",
                "was": "",
            },
        ],
    },
    {
        "id": "pit",
        "title": "ИПН, индивидуальный подоходный налог",
        "note": "Появилась вторая ставка: доход свыше порога облагается по 15%.",
        "items": [
            {
                "name": "Зарплата и ГПХ до " + money(mrp(8_500)) + " в год",
                "value": "10%",
                "was": "",
            },
            {
                "name": "Зарплата и ГПХ свыше " + money(mrp(8_500)) + " в год",
                "value": "15%",
                "was": "новое с 2026",
            },
            {"name": "Нерезиденты у источника выплаты", "value": "20%", "was": ""},
            {
                "name": "Базовый вычет",
                "value": money(mrp(30)) + " в месяц",
                "was": "было 14 МРП",
            },
            {
                "name": "Базовый вычет по договорам ГПХ",
                "value": money(mrp(30)) + " в месяц",
                "was": "новое с 2026, по заявлению",
            },
            {
                "name": "Корректировка 90% при зарплате ниже 25 МРП",
                "value": "отменена",
                "was": "действовала до 2026",
            },
        ],
    },
    {
        "id": "social",
        "title": "Зарплатные налоги и социальные платежи",
        "note": (
            "Соцналог больше не уменьшается на социальные отчисления, "
            "а пределы ВОСМС и ООСМС различаются между собой."
        ),
        "items": [
            {
                "name": "ОПВ, пенсионные взносы работника",
                "value": "10%",
                "was": "предел базы " + money(mzp(50)),
            },
            {
                "name": "ОПВР, взносы работодателя",
                "value": "3,5%",
                "was": "было 2,5%",
            },
            {
                "name": "СО, социальные отчисления",
                "value": "5%",
                "was": "предел базы " + money(mzp(7)),
            },
            {
                "name": "ВОСМС, взносы работника на медстрахование",
                "value": "2%",
                "was": "предел базы " + money(mzp(20)),
            },
            {
                "name": "ООСМС, отчисления работодателя",
                "value": "3%",
                "was": "предел базы " + money(mzp(40)),
            },
            {
                "name": "Соцналог для юрлиц",
                "value": "6% от дохода за вычетом ОПВ и ВОСМС",
                "was": "вычет СО отменён",
            },
            {
                "name": "Соцналог для ИП на ОУР за себя",
                "value": money(mrp(2)) + " в месяц",
                "was": "фиксированный, не процент",
            },
            {
                "name": "Соцналог для ИП за каждого работника",
                "value": money(mrp(1)) + " в месяц",
                "was": "",
            },
        ],
    },
    {
        "id": "special",
        "title": "Специальные налоговые режимы",
        "note": "Режимов стало три вместо четырёх.",
        "items": [
            {
                "name": "Упрощённая декларация, ставка",
                "value": "4% от дохода",
                "was": "соцналог включён",
            },
            {
                "name": "Упрощённая декларация, предел дохода",
                "value": money(mrp(600_000)) + " в год",
                "was": "до 30 работников",
            },
            {
                "name": "Расходы у заказчика на ОУР по услугам от упрощёнки",
                "value": "не идут на вычет по КПН",
                "was": "ст. 286, новое с 2026",
            },
            {
                "name": "Самозанятые через e-Salyq",
                "value": "4% от дохода",
                "was": "ИПН 0%, остальное соцплатежи",
            },
        ],
    },
]

CALENDAR = [
    {
        "name": "КПН, годовая декларация 100.00",
        "value": "до 31 марта, уплата до 10 апреля",
    },
    {"name": "НДС, декларация 300.00", "value": "ежеквартально, уплата до 25 числа"},
    {
        "name": "Зарплатные налоги, форма 200.00",
        "value": "ежеквартально нарастающим итогом",
    },
    {"name": "Упрощённая декларация 910.00", "value": "15 февраля и 15 августа"},
    {"name": "Имущество, земля, транспорт, форма 700.00", "value": "до 25 октября"},
]

# Блокировка счетов зависит от размера долга: пороги в МРП, поэтому тоже считаются.
ENFORCEMENT = [
    {
        "name": "До 20 МРП",
        "value": "до " + money(mrp(20)),
        "effect": "только извещение",
    },
    {
        "name": "От 20 до 45 МРП",
        "value": money(mrp(20)) + " ... " + money(mrp(45)),
        "effect": "уведомление, приостановление расходных операций, инкассо",
    },
    {
        "name": "Свыше 45 МРП",
        "value": "свыше " + money(mrp(45)),
        "effect": "блокировка счёта и опись имущества",
    },
]


def validate(data: dict) -> list[str]:
    """Гейт публикации справочника. Проверяется не свежесть данных, как у рядов,
    а полнота: позиция без значения или без основания вводит читателя в заблуждение."""
    problems: list[str] = []

    for item in data["base"]:
        if not item.get("value") or not item.get("basis"):
            problems.append(
                f"базовая величина без значения или основания: {item.get('name')}"
            )

    seen: set[str] = set()
    for group in data["groups"]:
        if not group.get("items"):
            problems.append(f"группа без позиций: {group.get('title')}")
        for item in group["items"]:
            name = item.get("name", "")
            if not name or not item.get("value"):
                problems.append(
                    f"позиция без имени или значения в группе {group['title']}"
                )
            key = f"{group['id']}/{name}"
            if key in seen:
                problems.append(f"позиция повторяется: {key}")
            seen.add(key)

    # Производные величины обязаны сходиться с базой: расхождение означает, что
    # кто-то вписал число руками вместо расчёта из МРП.
    checks = {
        "порог НДС": (mrp(10_000), 43_250_000),
        "базовый вычет ИПН": (mrp(30), 129_750),
        "порог ИПН 15%": (mrp(8_500), 36_762_500),
    }
    for label, (computed, expected) in checks.items():
        if computed != expected:
            problems.append(
                f"{label}: расчёт {computed} не сходится с ожидаемым {expected}"
            )

    try:
        reviewed = date.fromisoformat(data["reviewed_at"])
    except (KeyError, ValueError):
        problems.append("нет корректной даты ревизии")
    else:
        if reviewed > date.today():
            problems.append("дата ревизии в будущем")

    return problems


def build() -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reviewed_at": REVIEWED_AT,
        "year": YEAR,
        "mrp": MRP,
        "mzp": MZP,
        "source": TAX_CODE,
        "base": BASE,
        "groups": GROUPS,
        "calendar": CALENDAR,
        "enforcement": ENFORCEMENT,
    }


def main() -> None:
    dataset = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_DATASET
    data = build()
    problems = validate(data)
    if problems:
        for problem in problems:
            print(f"  проблема: {problem}")
        raise SystemExit("справочник не прошёл проверку, публикация отменена")
    dataset.parent.mkdir(parents=True, exist_ok=True)
    dataset.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    positions = sum(len(g["items"]) for g in data["groups"])
    print(
        f"Групп: {len(data['groups'])}, позиций: {positions}, ревизия: {data['reviewed_at']}"
    )
    print(f"Записано: {dataset}")


if __name__ == "__main__":
    main()
