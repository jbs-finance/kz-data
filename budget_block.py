"""Блок «Поступления в бюджет» для страницы /radar/tax/.

Три части: карточки итога, помесячный график с переключением по регионам и разрез
по видам налогов. Переключение сделано на радиокнопках и CSS: страница отдаётся с
запретом скриптов (CSP script-src 'none'), и ослаблять его ради интерактива нельзя.

Данные приходят из budget.py: помесячная динамика по регионам за последний
опубликованный год и разрез по кодам бюджетной классификации нарастающим итогом.
"""

from __future__ import annotations

import html

from build_pulse import fmt_num

MONTH_SHORT = [
    "янв",
    "фев",
    "мар",
    "апр",
    "май",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
]
MONTH_CASE = [
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
]

CHART_W = 720
CHART_H = 250
PAD_L = 46
PAD_R = 8
PAD_T = 14
PAD_B = 26

BUDGET_STYLE = """
.bud-cards { display: grid; gap: 0.75rem; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  margin-block: 1rem; }
.bud-cards .card { gap: 0.15rem; }
.bud-cards .num { font-size: 1.375rem; }

.drill { background: var(--card); border: 1px solid var(--muted); border-radius: var(--radius);
  overflow: hidden; margin-block: 1rem; }
.drill-radio { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.drill-tabs { display: flex; gap: 0.35rem; overflow-x: auto; padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--muted); scrollbar-width: thin; }
.drill-tabs label { flex: 0 0 auto; font-size: 0.8125rem; line-height: 1; padding: 0.45rem 0.7rem;
  border: 1px solid var(--muted); border-radius: 999px; cursor: pointer; white-space: nowrap;
  color: var(--muted-fg); background: var(--bg); transition: background 0.18s ease, color 0.18s ease,
  border-color 0.18s ease; }
.drill-tabs label:hover { border-color: var(--accent); color: var(--fg); }
.drill-stage { padding: 0.9rem 1rem 1.1rem; }
.series { display: none; }
.series-head { display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; align-items: baseline;
  justify-content: space-between; margin-bottom: 0.6rem; }
.series-name { font-weight: 600; }
.series-sub { color: var(--muted-fg); font-size: 0.8125rem; }
.series-stats { display: flex; flex-wrap: wrap; gap: 0.15rem 1.1rem; margin: 0; }
.series-stats div { display: flex; gap: 0.35rem; align-items: baseline; }
.series-stats dt { color: var(--muted-fg); font-size: 0.75rem; margin: 0; }
.series-stats dd { margin: 0; font-size: 0.875rem; font-weight: 600;
  font-family: "JetBrains Mono", ui-monospace, monospace; }
.series-stats dd.up { color: #2F7A4F; }
.series-stats dd.down { color: var(--accent); }
/* На узком экране график не сжимается до нечитаемых подписей, а прокручивается:
   двенадцать месяцев на 375 пикселях иначе превращаются в кашу. */
.chart-scroll { overflow-x: auto; margin-inline: -0.25rem; padding-inline: 0.25rem; }
.chart { width: 100%; min-width: 480px; height: auto; display: block; overflow: visible; }
.chart .grid { stroke: var(--muted); stroke-width: 1; }
.chart .axis { fill: var(--muted-fg); font-size: 11px;
  font-family: "JetBrains Mono", ui-monospace, monospace; }
.chart .bar-now { fill: var(--accent); }
.chart .bar-prev { fill: var(--muted); }
.chart .bar-now, .chart .bar-prev { transform-box: fill-box; transform-origin: bottom; }
.series-legend { display: flex; gap: 1rem; margin: 0.5rem 0 0; font-size: 0.75rem;
  color: var(--muted-fg); }
.series-legend span { display: inline-flex; align-items: center; gap: 0.35rem; }
.series-legend i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.series-legend .k-now { background: var(--accent); }
.series-legend .k-prev { background: var(--muted); }

.split { display: grid; gap: 0.55rem; margin-block: 1rem; }
.split-row { display: grid; grid-template-columns: minmax(120px, 15rem) 1fr auto; gap: 0.75rem;
  align-items: center; font-size: 0.875rem; }
.split-name { color: var(--fg); }
.split-track { background: var(--muted); border-radius: 999px; height: 0.6rem; overflow: hidden; }
.split-fill { display: block; height: 100%; background: var(--accent); border-radius: 999px;
  transform-origin: left; animation: split-grow 0.6s cubic-bezier(0.2, 0.7, 0.3, 1) both; }
.split-val { font-family: "JetBrains Mono", ui-monospace, monospace; white-space: nowrap;
  font-size: 0.8125rem; text-align: right; min-width: 8.5rem; }
.split-val b { font-weight: 600; }
.split-val span { display: inline-block; min-width: 3.2rem; color: var(--muted-fg); }

@keyframes split-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes bar-rise { from { transform: scaleY(0); } to { transform: scaleY(1); } }
@keyframes series-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

/* На широком экране все регионы видны сразу, на узком остаётся полоса прокрутки:
   перенос двадцати двух кнопок в столбик съел бы весь экран. */
@media (min-width: 48rem) {
  .drill-tabs { flex-wrap: wrap; overflow-x: visible; }
}

@media (max-width: 34rem) {
  .split-row { grid-template-columns: 1fr auto; }
  .split-track { grid-column: 1 / -1; }
}

@media (prefers-reduced-motion: reduce) {
  .split-fill, .chart .bar-now, .chart .bar-prev, .series { animation: none !important; }
}
"""


def drill_rules(count: int) -> str:
    """Правила показа выбранной серии и подсветки её вкладки.

    Пишутся отдельно от основного CSS, потому что зависят от числа регионов."""
    rules = []
    for i in range(count):
        rules.append(
            f"#rg{i}:checked ~ .drill-stage .s{i} {{ display: block; "
            f"animation: series-in 0.25s ease both; }}"
        )
        rules.append(
            f'#rg{i}:checked ~ .drill-tabs label[for="rg{i}"] '
            f"{{ background: var(--accent); border-color: var(--accent); color: #fff; }}"
        )
        rules.append(
            f'#rg{i}:focus-visible ~ .drill-tabs label[for="rg{i}"] '
            f"{{ outline: 2px solid var(--fg); outline-offset: 2px; }}"
        )
    return "\n" + "\n".join(rules) + "\n"


def normalize(name: str) -> str:
    """Имена регионов между годами пишутся по-разному: «г.Алматы» и «г. Алматы»."""
    return (
        name.lower()
        .replace("ё", "е")
        .replace("г.", "")
        .replace("область", "")
        .replace(" ", "")
        .replace("-", "")
        .strip()
    )


def nice_step(top: float) -> float:
    """Шаг сетки: круглое число, которое даёт 3-5 линий."""
    raw = top / 4
    magnitude = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 0.1
    for mult in (1, 2, 2.5, 5, 10):
        if magnitude * mult >= raw:
            return magnitude * mult
    return magnitude * 10


def chart_svg(
    values: list[float | None],
    prev: list[float | None],
    label: str,
    year: int,
    prev_year: int | None,
) -> str:
    """Сгруппированные столбики: бледный прошлый год, насыщенный текущий."""
    points = [v for v in list(values) + list(prev) if v]
    top = max(points) if points else 1
    step = nice_step(top)
    top = step * (int(top / step) + 1)
    inner_w = CHART_W - PAD_L - PAD_R
    inner_h = CHART_H - PAD_T - PAD_B
    group = inner_w / 12
    bar = group * 0.34

    parts = [
        f'<svg class="chart" viewBox="0 0 {CHART_W} {CHART_H}" role="img" '
        f'aria-label="{html.escape(label)}">'
    ]
    line = 0.0
    while line <= top + 1e-9:
        y = PAD_T + inner_h - line / top * inner_h
        parts.append(
            f'<line class="grid" x1="{PAD_L}" y1="{y:.1f}" x2="{CHART_W - PAD_R}" y2="{y:.1f}"/>'
        )
        parts.append(
            f'<text class="axis" x="{PAD_L - 6}" y="{y + 3:.1f}" text-anchor="end">'
            f"{fmt_num(line, 0)}</text>"
        )
        line += step

    for i in range(12):
        x0 = PAD_L + group * i
        parts.append(
            f'<text class="axis" x="{x0 + group / 2:.1f}" y="{CHART_H - 8}" '
            f'text-anchor="middle">{MONTH_SHORT[i]}</text>'
        )
        for kind, series, offset, series_year in (
            ("prev", prev, group * 0.13, prev_year),
            ("now", values, group * 0.5, year),
        ):
            value = series[i] if i < len(series) else None
            if not value:
                continue
            height = value / top * inner_h
            y = PAD_T + inner_h - height
            delay = i * 0.03
            parts.append(
                f'<rect class="bar-{kind}" x="{x0 + offset:.1f}" y="{y:.1f}" '
                f'width="{bar:.1f}" height="{height:.1f}" rx="2" '
                f'style="animation: bar-rise 0.45s cubic-bezier(0.2,0.7,0.3,1) {delay:.2f}s both">'
                f"<title>{MONTH_CASE[i]} {series_year}: {fmt_num(value, 0)} млрд тенге"
                f"</title></rect>"
            )
    parts.append("</svg>")
    return "".join(parts)


def series_stats(
    values: list[float | None], prev: list[float | None], share: float | None
) -> str:
    total = sum(v for v in values if v)
    peak_i = max(range(len(values)), key=lambda i: values[i] or 0)
    pairs = [
        (v, p) for v, p in zip(values, prev) if v and p
    ]  # сравниваем только месяцы, закрытые в обоих годах
    yoy = None
    if pairs:
        base = sum(p for _, p in pairs)
        yoy = (sum(v for v, _ in pairs) / base - 1) * 100 if base else None

    cells = [("За год", f"{fmt_num(total, 0)}", "")]
    cells.append((f"Пик · {MONTH_CASE[peak_i]}", fmt_num(values[peak_i] or 0, 0), ""))
    if yoy is not None:
        sign = "+" if yoy > 0 else ""
        tone = "up" if yoy > 0 else "down" if yoy < 0 else ""
        cells.append(
            (f"К прошлому году · {len(pairs)} мес.", f"{sign}{fmt_num(yoy, 1)}%", tone)
        )
    if share is not None:
        cells.append(("Доля в стране", f"{fmt_num(share, 1)}%", ""))

    body = "".join(
        f"<div><dt>{html.escape(name)}</dt>"
        f"<dd{f' class="{tone}"' if tone else ''}>{value}</dd></div>"
        for name, value, tone in cells
    )
    return f'<dl class="series-stats">{body}</dl>'


REGION_LABEL = {"КГД МФ РК": "КГД, центральный аппарат"}


def build_series(dynamics: dict) -> list[dict]:
    """Республика первой, дальше регионы по убыванию поступлений."""
    prev = dynamics.get("previous") or {}
    prev_total = prev.get("total") or [None] * 12
    prev_by_region = {
        normalize(r["name"]): r["values"] for r in prev.get("regions", [])
    }

    country = sum(v for v in dynamics["total"] if v)
    out = [
        {
            "name": "Республика",
            "values": dynamics["total"],
            "prev": prev_total,
            "share": 100.0 if country else None,
        }
    ]
    regions = sorted(
        dynamics["regions"], key=lambda r: -sum(v for v in r["values"] if v)
    )
    for region in regions:
        total = sum(v for v in region["values"] if v)
        out.append(
            {
                "name": REGION_LABEL.get(region["name"].strip(), region["name"].strip()),
                "values": region["values"],
                "prev": prev_by_region.get(normalize(region["name"]), [None] * 12),
                "share": total / country * 100 if country else None,
            }
        )
    return out


def drill_block(dynamics: dict) -> tuple[str, str]:
    series = build_series(dynamics)
    year = dynamics["year"]
    prev_year = (dynamics.get("previous") or {}).get("year")

    inputs = "".join(
        f'<input class="drill-radio" type="radio" name="drill-region" id="rg{i}"'
        f"{' checked' if i == 0 else ''}>"
        for i in range(len(series))
    )
    tabs = "".join(
        f'<label for="rg{i}">{html.escape(s["name"])}</label>'
        for i, s in enumerate(series)
    )
    legend = (
        f'<p class="series-legend"><span><i class="k-now"></i>{year}</span>'
        + (f'<span><i class="k-prev"></i>{prev_year}</span>' if prev_year else "")
        + "</p>"
    )
    stages = []
    for i, s in enumerate(series):
        label = f"{s['name']}: поступления по месяцам {year} года, млрд тенге"
        stages.append(
            f'<div class="series s{i}">'
            f'<div class="series-head"><div><span class="series-name">'
            f"{html.escape(s['name'])}</span> "
            f'<span class="series-sub">{year}, млрд тенге</span></div>'
            f"{series_stats(s['values'], s['prev'], s['share'])}</div>"
            f'<div class="chart-scroll">'
            f"{chart_svg(s['values'], s['prev'], label, year, prev_year)}</div>"
            f"{legend}</div>"
        )
    block = (
        '<div class="drill">'
        + inputs
        + f'<div class="drill-tabs" role="tablist">{tabs}</div>'
        + '<div class="drill-stage">'
        + "".join(stages)
        + "</div></div>"
    )
    return block, drill_rules(len(series))


def split_block(structure: dict) -> str:
    items = structure["items"]
    total = sum(i["value"] for i in items) or 1
    rows = []
    for n, item in enumerate(items):
        share = item["value"] / total * 100
        rows.append(
            f'<div class="split-row">'
            f'<span class="split-name">{html.escape(item["name"])}</span>'
            f'<span class="split-track"><i class="split-fill" '
            f'style="width: {share:.1f}%; animation-delay: {n * 0.05:.2f}s"></i></span>'
            f'<span class="split-val"><b>{fmt_num(item["value"], 1 if item["value"] < 10 else 0)}</b> '
            f"<span>{fmt_num(share, 1)}%</span></span></div>"
        )
    return f'<div class="split">{"".join(rows)}</div>'


def summary_cards(budget: dict) -> str:
    dynamics = budget["dynamics"]
    structure = budget.get("structure")
    series = build_series(dynamics)
    country, leader = series[0], series[1] if len(series) > 1 else None
    total = sum(v for v in country["values"] if v)
    pairs = [(v, p) for v, p in zip(country["values"], country["prev"]) if v and p]
    cards = [
        (
            f"Поступления за {dynamics['year']} год",
            f"{fmt_num(total, 0)} млрд ₸",
            "налоги и платежи в государственный бюджет",
        )
    ]
    if pairs:
        base = sum(p for _, p in pairs)
        change = (sum(v for v, _ in pairs) / base - 1) * 100
        sign = "+" if change > 0 else ""
        prev_year = (dynamics.get("previous") or {}).get("year")
        cards.append(
            (
                "К прошлому году",
                f"{sign}{fmt_num(change, 1)}%",
                f"за {len(pairs)} сопоставимых месяцев против {prev_year}",
            )
        )
    if leader:
        cards.append(
            (
                "Крупнейший источник",
                html.escape(leader["name"]),
                f"{fmt_num(leader['share'] or 0, 1)}% всех поступлений страны",
            )
        )
    if structure:
        top = structure["items"][0]
        share = top["value"] / sum(i["value"] for i in structure["items"]) * 100
        cards.append(
            (
                "Главный налог",
                html.escape(top["name"]),
                f"{fmt_num(share, 1)}% разреза за {period_label(structure)}",
            )
        )
    return (
        '<div class="bud-cards">'
        + "".join(
            f'<article class="card"><h3>{title}</h3>'
            f'<p class="value"><span class="num">{value}</span></p>'
            f'<p class="asof">{note}</p></article>'
            for title, value, note in cards
        )
        + "</div>"
    )


def period_label(structure: dict) -> str:
    """«январь-март 2025»: файлы КГД идут нарастающим итогом с начала года."""
    months = structure.get("months") or int(structure["period"][5:7])
    year = structure["year"]
    if months == 1:
        return f"{MONTH_CASE[0]} {year}"
    return f"{MONTH_CASE[0]}-{MONTH_CASE[months - 1]} {year}"


def budget_section(budget: dict) -> tuple[str, str]:
    """HTML блока и дополнительные CSS-правила под число регионов."""
    dynamics = budget.get("dynamics")
    if not dynamics:
        return "", ""
    structure = budget.get("structure")
    drill, rules = drill_block(dynamics)
    parts = [
        "<h2>Сколько собирают на самом деле</h2>",
        '<p class="lede">Ставки в таблицах выше это норма. Ниже фактические поступления '
        "в государственный бюджет по данным Комитета государственных доходов: помесячно, "
        "с переключением на любой регион.</p>",
        summary_cards(budget),
        f"<h3>Помесячно, {dynamics['year']} год</h3>",
        '<p class="lede">Выберите регион. Столбик поменьше это тот же месяц прошлого года, '
        "наведение показывает точную сумму.</p>",
        drill,
    ]
    if structure:
        parts += [
            f"<h3>Разрез по видам налогов, {period_label(structure)}</h3>",
            '<p class="lede">Нарастающим итогом с начала года, млрд тенге. '
            "Группы даны по кодам бюджетной классификации.</p>",
            split_block(structure),
        ]
    notes = ["<li>Суммы приведены в млрд тенге, источник публикует тысячи.</li>"]
    if structure and structure.get("skipped"):
        notes.append(
            "<li>Пропущены файлы, у которых дата правки не совпадает с заявленным "
            f"периодом: {html.escape(', '.join(structure['skipped']))}. Такие ссылки на "
            "сайте источника ведут на прошлогодний файл, и их цифры не публикуются здесь.</li>"
        )
    notes.append(
        "<li>Периоды разреза и помесячной динамики различаются: источник обновляет их "
        "разными файлами и с разной задержкой. Каждый подписан своей датой.</li>"
    )
    parts.append(
        "<details><summary>Как читать эти цифры</summary>"
        f'<div class="details-body"><ul>{"".join(notes)}</ul></div></details>'
    )
    return "\n".join(parts), rules
