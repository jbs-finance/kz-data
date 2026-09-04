"""Сборка главной страницы радара jbs.finance/radar.

Верх страницы рассчитан на три секунды: семь показателей, у каждого четыре слоя
контекста (значение, изменение, место в диапазоне за пять лет, форма движения) и
одна строка о том, что это значит для бизнеса. Ниже лента событий, ближайшие релизы
и полный состав пульса.

Запуск: .venv/bin/python build_radar.py out/radar.html out/radar.json out/pulse.json out/trade.json
"""

from __future__ import annotations

import html
import json
import sys
from datetime import date, datetime
from pathlib import Path
from layout import CTA_STYLE, HEADER_STYLE, cta_block, meta_tags, site_header

from build_pulse import (
    BNS_ORDER,
    FX_ORDER,
    MACRO_ORDER,
    STYLE,
    card,
    digits_for,
    fmt_date,
    fmt_num,
    pct_change,
    sources_rows,
    spark,
)

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "out" / "radar.html"

RANGE_YEARS = 5

RADAR_STYLE = """
.hero { padding-block: clamp(1.5rem, 5vw, 2.5rem) 1rem; }
.hero .next { display: inline-flex; align-items: center; gap: 0.5rem; margin-top: 0.6rem; padding: 0.35rem 0.7rem;
  background: var(--card); border: 1px solid var(--muted); border-radius: 999px; font-size: 0.8125rem; }
.hero .next .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }
.scan { display: grid; gap: var(--sp); grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); }
.scan .card { animation: rise var(--dur-in) var(--ease-out) both; }
.scan .card:nth-child(2) { animation-delay: 40ms; } .scan .card:nth-child(3) { animation-delay: 80ms; }
.scan .card:nth-child(4) { animation-delay: 120ms; } .scan .card:nth-child(5) { animation-delay: 160ms; }
.scan .card:nth-child(6) { animation-delay: 200ms; } .scan .card:nth-child(7) { animation-delay: 240ms; }
@keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.range { margin-top: 0.5rem; }
.range .track { position: relative; height: 4px; background: var(--muted); border-radius: 2px; }
.range .pin { position: absolute; top: -4px; width: 12px; height: 12px; border-radius: 50%; background: var(--accent);
  border: 2px solid var(--card); transform: translateX(-50%); }
.range .ends { display: flex; justify-content: space-between; font-size: 0.6875rem; color: var(--muted-fg); margin-top: 0.3rem;
  font-family: "JetBrains Mono", ui-monospace, monospace; }
.signal { margin: 0.5rem 0 0; padding: 0.55rem 0.7rem; background: var(--bg); border-radius: 6px; font-size: 0.8125rem;
  line-height: 1.45; }
.two-col { display: grid; gap: var(--sp); grid-template-columns: 1fr; }
@media (min-width: 900px) { .two-col { grid-template-columns: 3fr 2fr; } }
.feed { background: var(--card); border: 1px solid var(--muted); border-radius: var(--radius); padding: 1rem 1.15rem; }
.feed h2 { margin: 0 0 0.75rem; font-size: 1.125rem; }
.feed ol { list-style: none; margin: 0; padding: 0; }
.feed li { display: grid; grid-template-columns: 6.5rem 1fr; gap: 0.75rem; padding: 0.55rem 0; border-top: 1px solid var(--muted);
  font-size: 0.9rem; align-items: baseline; }
.feed li:first-child { border-top: 0; }
.feed time { font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 0.8125rem; color: var(--muted-fg); white-space: nowrap; }
.feed .kind { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-inline-end: 0.45rem; vertical-align: middle; }
.kind-rate { background: var(--accent); } .kind-inflation { background: var(--down); } .kind-fx { background: var(--up); }
.kind-stat { background: var(--line); }
.feed .empty { color: var(--muted-fg); font-size: 0.875rem; margin: 0; }
.feed a { color: inherit; text-decoration: none; border-bottom: 1px solid var(--muted); }
.feed a:hover, .feed a:focus-visible { border-bottom-color: var(--accent); }
.feed .type { color: var(--muted-fg); font-size: 0.8125rem; }
h2.section { margin-top: 2.5rem; }
"""


def window(obs: list[dict], freq: str) -> list[dict]:
    per_year = {"A": 1, "Q": 4, "M": 12, "D": 12}.get(freq, 12)
    n = RANGE_YEARS * per_year
    return obs[-n:] if len(obs) > n else obs


def range_markup(series: dict, digits: int) -> str:
    """Положение текущего значения между минимумом и максимумом за пять лет."""
    obs = window(series["obs"], series["freq"])
    values = [o["value"] for o in obs]
    if len(values) < 3:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    pos = (values[-1] - lo) / span * 100
    return f"""        <div class="range" aria-label="Диапазон за {RANGE_YEARS} лет">
          <div class="track"><span class="pin" style="left: {pos:.1f}%"></span></div>
          <div class="ends"><span>{fmt_num(lo, digits)}</span><span>{RANGE_YEARS} лет</span><span>{fmt_num(hi, digits)}</span></div>
        </div>"""


def scan_card(series: dict, digits: int, period_label: str, signal: str) -> str:
    last = series["obs"][-1]
    change = pct_change(series, 365)
    if series["freq"] == "D" and series["series_id"] == "kz.rate.base":
        # У ставки изменение считается в процентных пунктах к прошлому решению.
        prev = series["obs"][-2]["value"] if len(series["obs"]) > 1 else None
        delta = (
            (
                f'<p class="delta delta-{"down" if prev is not None and last["value"] < prev else "up" if prev is not None and last["value"] > prev else "flat"}">'
                f'<span class="delta-value">{"" if prev is None else ("%+.2f" % (last["value"] - prev)).replace(".", ",")} п.п.</span> '
                f'<span class="delta-note">к прошлому решению</span></p>'
            )
            if prev is not None
            else ""
        )
    elif change is None:
        delta = '<p class="delta delta-none">база для сравнения недоступна</p>'
    else:
        tone = "up" if change > 0 else "down" if change < 0 else "flat"
        sign = "+" if change > 0 else ""
        word = "выше" if change > 0 else "ниже" if change < 0 else "без изменения"
        delta = (
            f'<p class="delta delta-{tone}"><span class="delta-value">{sign}{fmt_num(change, 1)}%</span> '
            f'<span class="delta-note">{word}, чем {period_label}</span></p>'
        )
    badge = (
        '<span class="badge badge-stale">данные устарели</span>'
        if series.get("stale")
        else '<span class="badge badge-fresh">актуально</span>'
    )
    signal_html = f'<p class="signal">{html.escape(signal)}</p>' if signal else ""
    return f"""      <article class="card">
        <header class="card-head"><h3>{html.escape(series["name_ru"])}</h3>{badge}</header>
        <p class="value"><span class="num">{fmt_num(last["value"], digits)}</span>
          <span class="unit">{html.escape(series["unit"])}</span></p>
        {delta}
        {spark(window(series["obs"], series["freq"]))}
{range_markup(series, digits)}
        {signal_html}
        <p class="asof">на {fmt_date(last["date"])}, источник: {html.escape(series["source"])}</p>
      </article>"""


def events_markup(events: list[dict]) -> str:
    if not events:
        return '<p class="empty">За последние полтора месяца заметных изменений не было.</p>'
    items = "\n".join(
        f'          <li><time datetime="{e["date"]}">{fmt_date(e["date"])}</time>'
        f'<span><span class="kind kind-{html.escape(e["kind"])}"></span>{html.escape(e["text"])}</span></li>'
        for e in events
    )
    return f"        <ol>\n{items}\n        </ol>"


def calendar_markup(calendar: list[dict]) -> str:
    if not calendar:
        return '<p class="empty">Календарь релизов на ближайшие дни пуст.</p>'
    items = "\n".join(
        f'          <li><time datetime="{e["date"]}">{fmt_date(e["date"])}</time>'
        f'<span><span class="kind kind-{"rate" if e["kind"] == "rate" else "stat"}"></span>'
        f'<a href="{html.escape(e["url"])}" rel="noopener">{html.escape(e["title"])}</a>'
        f' <span class="type">{html.escape(e.get("type", ""))}</span></span></li>'
        for e in calendar
    )
    return f"        <ol>\n{items}\n        </ol>"


def build(radar: dict, pulse: dict, trade: dict) -> str:
    by_id = {s["series_id"]: s for s in pulse.get("series", [])}
    by_id.update({s["series_id"]: s for s in radar.get("series", [])})
    trade_by_id = {s["series_id"]: s for s in trade.get("series", [])}
    signals = radar.get("signals", {})
    generated = datetime.fromisoformat(radar["generated_at"])

    scan_spec = [
        ("kz.rate.base", by_id, 2, "прошлому решению", "rate"),
        ("kz.cpi.monthly", by_id, 1, "год назад", "inflation"),
        ("kz.fx.usd", by_id, 2, "год назад", "fx"),
        ("kz.gdp.growth", by_id, 1, "годом ранее", "growth"),
        ("kz.wage.avg", by_id, 0, "годом ранее", "wage"),
        ("kz.exports.usd", trade_by_id, 1, "годом ранее", "exports"),
        ("kz.unemployment", by_id, 2, "годом ранее", "unemployment"),
    ]
    scan = "\n".join(
        scan_card(source[sid], digits, label, signals.get(key, ""))
        for sid, source, digits, label, key in scan_spec
        if sid in source and source[sid].get("obs")
    )

    next_rate = radar.get("next_rate_decision")
    next_line = ""
    if next_rate:
        days = (date.fromisoformat(next_rate["date"]) - date.today()).days
        when = (
            "сегодня" if days == 0 else "завтра" if days == 1 else f"через {days} дн."
        )
        next_line = (
            f'<p class="next"><span class="dot"></span>Следующее решение по базовой ставке '
            f"{fmt_date(next_rate['date'])}, {when}</p>"
        )

    issues = (radar.get("issues") or []) + (pulse.get("issues") or [])
    issues_block = ""
    if issues:
        items = "".join(f"<li>{html.escape(i)}</li>" for i in issues)
        issues_block = (
            '<div class="notice" role="status"><p><strong>Часть данных не обновилась '
            "в последнем прогоне.</strong> Показаны предыдущие значения.</p>"
            f"<ul>{items}</ul></div>"
        )

    fx_cards = "\n".join(
        card(by_id[s], digits_for(s), "год назад", 365) for s in FX_ORDER if s in by_id
    )
    macro_cards = "\n".join(
        card(by_id[s], digits_for(s), "годом ранее", 365)
        for s in MACRO_ORDER
        if s in by_id
    )
    bns_cards = "\n".join(
        card(by_id[s], digits_for(s), "годом ранее", 365)
        for s in BNS_ORDER
        if s in by_id
    )

    all_series = list(pulse.get("series", [])) + list(radar.get("series", []))
    return TEMPLATE.format(
        style=STYLE + HEADER_STYLE + RADAR_STYLE + CTA_STYLE,
        meta=meta_tags(
            "Радар экономики Казахстана: ставка, инфляция, курс, зарплаты",
            "Ключевые показатели экономики Казахстана с ежедневным обновлением и разбором, что они значат для бизнеса. Базовая ставка, инфляция, курс тенге, рост ВВП, зарплаты, экспорт.",
            "/radar/",
        ),
        header=site_header("radar"),
        generated_human=generated.strftime("%d.%m.%Y %H:%M UTC"),
        generated_iso=generated.isoformat(),
        next_line=next_line,
        issues_block=issues_block,
        scan=scan,
        events=events_markup(radar.get("events", [])),
        calendar=calendar_markup(radar.get("calendar", [])),
        fx_cards=fx_cards,
        macro_cards=macro_cards,
        bns_cards=bns_cards,
        sources_rows=sources_rows(all_series),
        cta=cta_block(),
        year=date.today().year,
    )


TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Радар экономики Казахстана</title>
{meta}
<style>{style}</style>
</head>
<body>
{header}
<div class="wrap">
  <header class="top hero">
    <h1>Радар экономики Казахстана</h1>
    <p class="lede">Семь показателей, которые определяют условия для бизнеса, с ежедневным
      обновлением из первоисточников. У каждой цифры: изменение, место в диапазоне за пять лет
      и что она значит для ваших цен, зарплат и кредитов.</p>
    <p class="updated">Обновлено <time datetime="{generated_iso}">{generated_human}</time></p>
    {next_line}
  </header>

  {issues_block}

  <main>
    <h2 class="section" id="scan">Три секунды</h2>
    <div class="scan">
{scan}
    </div>

    <div class="two-col" style="margin-top: 2.5rem">
      <section class="feed" id="events" aria-labelledby="events-title">
        <h2 id="events-title">Что изменилось</h2>
{events}
      </section>
      <section class="feed" id="calendar" aria-labelledby="calendar-title">
        <h2 id="calendar-title">Ближайшие релизы</h2>
{calendar}
      </section>
    </div>

    <h2 class="section" id="fx">Официальные курсы валют</h2>
    <div class="grid">
{fx_cards}
    </div>

    <h2 class="section" id="macro">Экономика</h2>
    <div class="grid">
{macro_cards}
    </div>

    <h2 class="section" id="bns">Данные Бюро национальной статистики</h2>
    <p class="section-note">Национальный источник, в тенге и людях. Значения свежее, чем
      у международной базы, но приходят округлёнными до целых, поэтому проценты на этой
      странице взяты из международной базы, а не из БНС.</p>
    <div class="grid">
{bns_cards}
    </div>

{cta}

    <h2 class="section" id="sources">Источники и свежесть данных</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th scope="col">Показатель</th><th scope="col">Источник</th>
            <th scope="col">Точек</th><th scope="col">Последняя</th>
            <th scope="col">Забрано</th><th scope="col">Статус</th></tr>
        </thead>
        <tbody>
{sources_rows}
        </tbody>
      </table>
    </div>

    <details>
      <summary>Как читать эти цифры</summary>
      <div class="details-body">
        <ul>
          <li>Строка «что это значит» это правило по порогам, а не мнение аналитика: два
            снижения ставки подряд дают «цикл смягчения», инфляция выше цели НБРК даёт
            «закладывайте индексацию». Правила открыты в коде радара.</li>
          <li>Диапазон за пять лет показывает, где текущее значение стоит между минимумом и
            максимумом этого периода. Ось графика растянута по размаху, а не от нуля.</li>
          <li>Инфляция год к году берётся из ежемесячной публикации Бюро национальной
            статистики и накапливается с момента запуска радара: история удлиняется на одну
            точку в месяц.</li>
          <li>Курсы валют официальные, на первое число месяца и на дату сборки. Годовые
            показатели международной базы отстают примерно на год: это лаг источника.</li>
          <li>Если ряд не удалось обновить, показывается прошлое значение с пометкой
            «данные устарели», а не пустой график.</li>
        </ul>
      </div>
    </details>
  </main>

  <footer>
    <p>Данные собираются автоматически из открытых источников и приводятся без гарантии
      пригодности для конкретного решения. Для расчётов и отчётности сверяйтесь с первоисточником.</p>
    <p>&copy; {year} JB Solutions</p>
  </footer>
</div>
</body>
</html>
"""


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    radar_path = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "out" / "radar.json"
    pulse_path = Path(sys.argv[3]) if len(sys.argv) > 3 else HERE / "out" / "pulse.json"
    trade_path = Path(sys.argv[4]) if len(sys.argv) > 4 else HERE / "out" / "trade.json"
    radar = json.loads(radar_path.read_text(encoding="utf-8"))
    pulse = json.loads(pulse_path.read_text(encoding="utf-8"))
    trade = (
        json.loads(trade_path.read_text(encoding="utf-8"))
        if trade_path.exists()
        else {}
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(radar, pulse, trade), encoding="utf-8")
    print(f"Страница собрана: {out} ({out.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
