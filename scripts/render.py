#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — erzeugt das AI-Briefing als STATISCHE HTML-Seiten (ohne JavaScript).

Liest eine einzige Datenquelle (data/briefing.json) und schreibt:
  site/index.html           — Übersicht aller Themenbereiche
  site/<topic-id>.html      — je Themenbereich ein Detail-Report mit Radar

Design, Radar-Mathematik und CSS folgen dem Tech-Radar-Prinzip und sind auf die
AI-Themen sowie eine Mehrquellen-Darstellung angepasst. Keine Abhängigkeiten außer stdlib.

Aufruf:
    python3 scripts/render.py
"""

import json, math, html as _html, datetime, re
from pathlib import Path

import history as history_mod

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "briefing.json"
SITE = ROOT / "site"

# ---- Kategorien (Radar-Segmente). Reihenfolge = Segment-Reihenfolge im Radar ----
CATS = [
    ("modelle",  "Modelle",              "#0075de"),
    ("tools",    "Tools & IDEs",         "#2a9d99"),
    ("agents",   "Agents & Frameworks",  "#213183"),
    ("lokal",    "Open Weight / Lokal",  "#1aae39"),
    ("security", "Security & Governance","#dd5b00"),
    ("business", "Business & Markt",     "#ff64c8"),
]
CAT_NAME = {k: n for k, n, _ in CATS}
CAT_COLOR = {k: c for k, _, c in CATS}
CAT_INDEX = {k: i for i, (k, _, _) in enumerate(CATS)}
RINGS = [(5, "Game-Changer"), (4, "Stark"), (3, "Relevant"), (2, "Nennenswert"), (1, "Routine")]

SIZE, CX, CY, MAXR = 800, 400, 400, 320
RING_OUT = [f * MAXR for f in (0.26, 0.45, 0.62, 0.80, 1.0)]
RING_IN = [0, RING_OUT[0], RING_OUT[1], RING_OUT[2], RING_OUT[3]]
SECTORS = len(CATS)
SEC_DEG = 360 / SECTORS
START = -90
INK, BLUE, GRID, CARD = "#1f1d1b", "#0075de", "#e3e0dc", "#ffffff"
BAND_FILL = ["rgba(0,117,222,.06)", "rgba(49,48,46,.055)", "rgba(49,48,46,.038)",
             "rgba(49,48,46,.022)", "rgba(49,48,46,.012)"]


def esc(s):
    return _html.escape(str(s), quote=True)


def pt(deg, r):
    a = deg * math.pi / 180
    return CX + r * math.sin(a), CY - r * math.cos(a)


def lum(hexc):
    n = int(hexc[1:], 16)
    r, g, b = (n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast_text(hexc):
    return "#ffffff" if lum(hexc) < 0.30 else "#1f1d1b"


def dots(imp):
    return "●" * imp + "○" * (5 - imp)


def fmt(n):
    return f"{n:.2f}".rstrip("0").rstrip(".")


def build_radar_svg(entries):
    out = ['<svg viewBox="-70 -20 940 860" role="img" aria-label="AI-Radar">']
    for j in range(len(RING_OUT) - 1, -1, -1):
        out.append(f'<circle cx="{CX}" cy="{CY}" r="{fmt(RING_OUT[j])}" '
                   f'fill="{BAND_FILL[j]}" stroke="{GRID}" stroke-width="1"/>')
    for i in range(SECTORS):
        x, y = pt(START + i * SEC_DEG, MAXR)
        out.append(f'<line x1="{CX}" y1="{CY}" x2="{fmt(x)}" y2="{fmt(y)}" stroke="{GRID}" stroke-width="1"/>')
    out.append(f'<circle cx="{CX}" cy="{CY}" r="3" fill="{BLUE}"/>')
    label_deg = START + SEC_DEG
    for j, (_, name) in enumerate(RINGS):
        r = RING_OUT[j] - 13
        x, y = pt(label_deg, r)
        w = len(name) * 6.4 + 16
        out.append('<g>')
        out.append(f'<rect x="{fmt(x - w/2)}" y="{fmt(y - 9)}" width="{fmt(w)}" height="16" rx="8" '
                   f'fill="#ffffff" opacity="0.94" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{fmt(x)}" y="{fmt(y + 3)}" class="axis-label" text-anchor="middle">{esc(name)}</text>')
        out.append('</g>')
    for i, (_, name, _) in enumerate(CATS):
        mid = START + i * SEC_DEG + SEC_DEG / 2
        x, y = pt(mid, MAXR + 30)
        s = math.sin(mid * math.pi / 180)
        norm = abs(((mid % 360) + 360) % 360 - 180)
        anchor = "middle" if norm < 1 else ("start" if s > 0.08 else ("end" if s < -0.08 else "middle"))
        out.append(f'<text x="{fmt(x)}" y="{fmt(y + 4)}" class="sector-label" '
                   f'text-anchor="{anchor}" fill="{INK}">{esc(name)}</text>')
    cells = {}
    for e in entries:
        si = CAT_INDEX.get(e.get("category"), -1)
        ri = 5 - int(e.get("impact", 0))
        if si < 0 or ri < 0 or ri > 4:
            continue
        cells.setdefault((si, ri), []).append(e)
    for (si, ri), lst in cells.items():
        K = len(lst)
        sec_start = START + si * SEC_DEG
        r_mid = (RING_IN[ri] + RING_OUT[ri]) / 2
        band = RING_OUT[ri] - RING_IN[ri]
        color = CATS[si][2]
        for k, e in enumerate(lst):
            ang = sec_start + SEC_DEG * (k + 1) / (K + 1)
            r_off = (k - (K - 1) / 2) * min(16, band * 0.22)
            x, y = pt(ang, r_mid + r_off)
            out.append('<g>')
            out.append(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="13" fill="{color}" stroke="{CARD}" stroke-width="2"/>')
            out.append(f'<text x="{fmt(x)}" y="{fmt(y + 4)}" class="blip-num" '
                       f'text-anchor="middle" fill="{contrast_text(color)}">{esc(e["n"])}</text>')
            out.append('</g>')
    out.append('</svg>')
    return "\n".join(out)


def sources_html(item):
    srcs = item.get("sources") or []
    if not srcs:
        return ""
    links = " · ".join(
        f'<a class="dlink" href="{esc(s["url"])}" target="_blank" rel="noopener">'
        f'{esc(s["label"])} <span class="arw">→</span></a>'
        for s in srcs)
    return f'<div class="dsources"><span class="dsources-k">Quellen:</span> {links}</div>'


def build_detail(entries):
    cards = []
    for e in sorted(entries, key=lambda x: x["n"]):
        color = CAT_COLOR.get(e["category"], BLUE)
        cname = CAT_NAME.get(e["category"], e["category"])
        primary_src = (e.get("sources") or [{}])[0].get("label", "")
        primary_url = (e.get("sources") or [{}])[0].get("url", "")
        cat_badge = (f'<span class="cat-badge" style="background:{color}1f;color:{color}">'
                     f'{esc(cname)}</span>')
        src_meta = f'<span class="dmeta-src">{esc(primary_src)} · {esc(e["date"])}</span> · ' if primary_src else f'<span class="dmeta-src">{esc(e["date"])}</span> · '
        title_html = (f'<a class="dtitle-link" href="{esc(primary_url)}" target="_blank" rel="noopener">{esc(e["title"])}</a>'
                      if primary_url else esc(e["title"]))
        cards.append(f'''  <div class="dcard">
    <span class="dnum" style="background:{color};color:{contrast_text(color)}">{esc(e["n"])}</span>
    <div class="dbody">
      <h3 class="dtitle">{title_html}</h3>
      <div class="dmeta">{cat_badge}{src_meta}<span class="dots">{dots(int(e["impact"]))}</span> <span class="dmeta-imp">{esc(e["impact"])}/5</span></div>
      <p>{esc(e["summary"])}</p>
      {sources_html(e)}
    </div>
  </div>''')
    return "\n".join(cards)


def scale_with_context(ctx):
    return (f"Bewertet wird aus dem Blickwinkel <b>{esc(ctx)}</b>. Leitfrage je Meldung: "
            f"Wie stark verändert sie die tägliche Arbeit, die Werkzeuge oder die Entscheidungen "
            f"im Bereich {esc(ctx)}? Eine allgemein große AI-Meldung kann hier niedrig liegen — und "
            f"umgekehrt. Daraus ergibt sich der Ring (innen = wichtiger).")


CSS = """  :root{
    --blue:#0075de;
    --blue-active:#005bab;
    --badge-bg:#f2f9ff;
    --badge-text:#097fe8;
    --white:#ffffff;
    --wg10:#f6f5f4;
    --wg20:#efedea;
    --wg40:rgba(0,0,0,0.10);
    --wg60:#a39e98;
    --wg90:#615d59;
    --ink:#31302e;
    --wg100:rgba(0,0,0,0.95);
    --radius:12px;
    --radius-lg:16px;
    --pad:24px;
    --shadow-card:rgba(0,0,0,0.04) 0px 4px 18px, rgba(0,0,0,0.027) 0px 2.025px 7.84688px, rgba(0,0,0,0.02) 0px 0.8px 2.925px, rgba(0,0,0,0.01) 0px 0.175px 1.04062px;
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{background:var(--white);color:var(--wg100);
    font-family:Inter,-apple-system,system-ui,"Segoe UI",Helvetica,Arial,sans-serif;
    font-feature-settings:"lnum","locl";
    -webkit-font-smoothing:antialiased;padding:48px clamp(16px,4vw,56px) 64px;line-height:1.5}
  .sheet{max-width:1280px;margin:0 auto}
  .impuls{display:none}
  header.top{padding-bottom:20px;border-bottom:1px solid var(--wg40)}
  .top h1{font-weight:700;font-size:clamp(30px,3.6vw,46px);color:var(--wg100);
    letter-spacing:-0.03em;margin:0;line-height:1.04}
  .subrow{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;
    flex-wrap:wrap;margin-top:12px}
  .subs{display:flex;flex-direction:column;gap:6px;min-width:0}
  .sub{font-size:14px;font-weight:500;color:var(--wg90);line-height:1.43}
  .meta-right{font-size:13px;color:var(--wg90);text-align:right;line-height:1.6;font-weight:500;flex:none}
  .nav{margin:18px 0 0;font-size:13px;font-weight:500}
  .nav a{color:var(--wg90);text-decoration:none;margin-right:14px;transition:color .2s ease}
  .nav a:hover{color:var(--blue)}
  .nav a.active{color:var(--wg100);font-weight:700}
  .range-sw{font-weight:500}
  .range-sw a{color:var(--wg90);text-decoration:none;margin-left:12px;transition:color .2s ease}
  .range-sw a:first-child{margin-left:0}
  .range-sw a:hover{color:var(--blue)}
  .range-sw a.active{color:var(--wg100);font-weight:700}
  .range-period{color:var(--wg60)}
  .lede{font-size:clamp(17px,1.9vw,20px);color:var(--wg100);font-weight:500;max-width:70ch;
    margin:24px 0 32px;line-height:1.5;letter-spacing:-0.0125em}
  .board{margin:8px 0 0}
  @media (min-width:960px){
    .board{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);
      gap:clamp(28px,3.5vw,56px);align-items:start}
  }
  .panel{background:var(--wg10);border:1px solid var(--wg40);border-radius:var(--radius-lg);
    box-shadow:var(--shadow-card);padding:clamp(18px,3vw,32px);margin:0}
  svg{width:100%;height:auto;display:block;overflow:visible}
  .panel svg{max-width:600px;margin-left:auto;margin-right:auto}
  .sector-label{font-family:Inter,Arial,sans-serif;font-weight:700;font-size:13px;letter-spacing:-0.01em}
  .axis-label{font-family:Inter,Arial,sans-serif;font-size:10.5px;font-weight:600;fill:var(--wg90);letter-spacing:0}
  .blip-num{font-family:Inter,Arial,sans-serif;font-weight:700;font-size:12px}
  .key{display:flex;justify-content:center;gap:22px;flex-wrap:wrap;margin:18px 0 0;
    font-size:13px;color:var(--wg90);font-weight:500}
  .key b{color:var(--wg100);font-weight:600}
  .section{margin:48px 0 20px}
  .section h2{font-weight:700;font-size:clamp(24px,3vw,32px);color:var(--wg100);margin:0;letter-spacing:-0.03em;line-height:1.05}
  .scale{max-width:none;margin:0;background:var(--wg10);border:1px solid var(--wg40);
    border-radius:var(--radius-lg);box-shadow:var(--shadow-card);padding:24px 26px}
  .scale h3{font-weight:700;font-size:18px;color:var(--wg100);margin:0 0 8px;letter-spacing:-0.0125em}
  .scale .scale-lead{font-size:14px;color:var(--wg90);margin:0 0 16px;line-height:1.5}
  .scale ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:9px}
  .scale li{display:flex;gap:14px;align-items:baseline;font-size:14px;line-height:1.45}
  .scale .sc-dots{letter-spacing:1px;color:var(--ink);flex:none;min-width:64px;font-weight:700}
  .scale .sc-name{font-weight:600;color:var(--wg100)}
  .scale .sc-desc{color:var(--wg90)}
  .scale .sc-note{font-size:13px;color:var(--wg90);margin:15px 0 0;line-height:1.5}
  .detail-list{display:flex;flex-direction:column}
  @media (min-width:1200px){
    .detail-list{display:grid;grid-template-columns:1fr 1fr;column-gap:clamp(40px,4vw,72px)}
    .detail-list .dcard:nth-child(2){border-top:none}
    .dcard p{max-width:none}
  }
  .dcard{display:flex;gap:16px;padding:24px 0;border-top:1px solid var(--wg40)}
  .dcard:first-child{border-top:none}
  .dnum{flex:none;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:14px;margin-top:2px}
  .dbody{flex:1;min-width:0}
  .dtitle{font-weight:700;font-size:clamp(19px,2.2vw,22px);line-height:1.27;letter-spacing:-0.0125em;color:var(--wg100);margin:0 0 9px}
  .dtitle-link{color:inherit;text-decoration:none}
  .dtitle-link:hover{color:var(--blue);text-decoration:underline}
  .dmeta{font-size:13px;color:var(--wg90);font-weight:500;margin-bottom:13px;display:flex;align-items:center;flex-wrap:wrap;gap:8px}
  .cat-badge{display:inline-flex;align-items:center;border-radius:9999px;padding:3px 10px;
    font-size:12px;font-weight:600;letter-spacing:0.0125em;line-height:1.33}
  .dmeta-src{color:var(--wg90)}
  .dmeta-imp{color:var(--wg90);font-weight:600}
  .dcard p{margin:0 0 14px;font-size:16px;line-height:1.55;color:var(--wg100);max-width:68ch}
  .dsources{font-size:14px;color:var(--wg90);display:flex;flex-wrap:wrap;align-items:center;gap:8px}
  .dsources-k{font-weight:600;color:var(--wg90)}
  .dots{letter-spacing:1px;color:var(--ink)}
  .dlink{display:inline-flex;align-items:center;gap:6px;font-size:14px;font-weight:600;color:var(--blue);
    text-decoration:none;transition:color .2s ease}
  .dlink .arw{transition:transform .2s ease}
  .dlink:hover{text-decoration:underline;color:var(--blue-active)}
  .dlink:hover .arw{transform:translateX(3px)}
  .skip{margin-top:16px;background:var(--wg10);border:1px solid var(--wg40);border-radius:var(--radius-lg);
    box-shadow:var(--shadow-card);padding:22px 26px}
  .skip-lead{margin:0 0 16px;font-size:14px;color:var(--wg90);line-height:1.55}
  .skip ul{margin:0;padding-left:20px}
  .skip li{font-size:15px;line-height:1.6;color:var(--wg100);margin-bottom:11px}
  .skip li::marker{color:var(--wg60)}
  .skip li:last-child{margin-bottom:0}
  .skip li b{font-weight:600;color:var(--wg100)}
  .footer{margin-top:48px;padding-top:20px;border-top:1px solid var(--wg40);font-size:13px;color:var(--wg90);line-height:1.6}
  .footer a{color:var(--blue);text-decoration:none}
  .footer a:hover{text-decoration:underline}
  .ov-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:20px;margin-top:12px}
  .ov-card{background:var(--white);border:1px solid var(--wg40);border-radius:var(--radius-lg);
    box-shadow:var(--shadow-card);padding:22px 24px;display:flex;flex-direction:column;
    transition:border-color .2s ease, box-shadow .2s ease}
  .ov-card:hover{border-color:var(--wg60);box-shadow:rgba(0,0,0,.07) 0px 8px 24px}
  .ov-card-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:8px}
  .ov-card h3{margin:0;font-size:19px;font-weight:700;color:var(--wg100);letter-spacing:-0.0125em}
  .ov-count{flex:none;font-size:12px;font-weight:600;color:var(--wg90);background:var(--wg10);
    border:1px solid var(--wg40);border-radius:9999px;padding:2px 10px;white-space:nowrap}
  .ov-card .ov-sub{font-size:13px;font-weight:500;color:var(--wg90);line-height:1.45;margin-bottom:14px;
    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  .ov-list{list-style:none;margin:0 0 16px;padding:0;display:flex;flex-direction:column;gap:10px;flex:1}
  .ov-list li{display:flex;gap:10px;align-items:baseline;font-size:14px;line-height:1.4}
  .ov-dot{flex:none;width:9px;height:9px;border-radius:50%;margin-top:5px}
  .ov-item-t{color:var(--wg100);font-weight:500;text-decoration:none}
  a.ov-item-t:hover{color:var(--blue);text-decoration:underline}
  .ov-item-d{color:var(--ink);letter-spacing:1px;font-size:11px;font-weight:700;white-space:nowrap;margin-left:auto;padding-left:8px}
  .ov-link{align-self:flex-start;display:inline-flex;align-items:center;gap:6px;font-size:14px;font-weight:600;color:var(--blue);text-decoration:none;transition:color .2s ease}
  .ov-link:hover{text-decoration:underline;color:var(--blue-active)}
  .ov-empty{font-size:14px;color:var(--wg90);font-style:italic;flex:1}
  .ov-group{margin:44px 0 0}
  .ov-group h2{font-weight:700;font-size:clamp(19px,2.2vw,24px);color:var(--wg100);margin:0;letter-spacing:-0.02em}
  .ov-group:first-of-type{margin-top:10px}
  .repo-list{display:flex;flex-direction:column;margin-top:8px}
  .repo{display:flex;gap:16px;padding:22px 0;border-top:1px solid var(--wg40)}
  .repo:first-child{border-top:none}
  .repo-rank{flex:none;width:30px;height:30px;border-radius:8px;display:grid;place-items:center;font-weight:700;font-size:14px;background:var(--wg10);border:1px solid var(--wg40);color:var(--wg90);margin-top:2px}
  .repo-body{flex:1;min-width:0}
  .repo-name{font-weight:700;font-size:clamp(18px,2.1vw,21px);margin:0 0 8px;letter-spacing:-0.0125em}
  .repo-name a{color:var(--blue);text-decoration:none}
  .repo-name a:hover{text-decoration:underline;color:var(--blue-active)}
  .repo-meta{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
  .repo-badge{display:inline-flex;align-items:center;gap:5px;border-radius:9999px;padding:3px 11px;font-size:12px;font-weight:600;color:var(--wg100);background:var(--wg10);border:1px solid var(--wg40)}
  .repo-badge.area{background:#f2f9ff;border-color:#cfe6fb;color:var(--badge-text)}
  .repo-badge.week{background:#eaf6ec;border-color:#cfe8d3;color:#1a7f37}
  .repo-body p{margin:0 0 8px;font-size:16px;line-height:1.55;color:var(--wg100);max-width:68ch}
  .repo-note{font-size:13px;color:var(--wg90)}"""

SCALE_BLOCK = """  <div class="scale">
    <h3>Wie sich der Impact bestimmt</h3>
    <p class="scale-lead">{scale_lead}</p>
    <ul>
      <li><span class="sc-dots">●○○○○</span><span><span class="sc-name">1 — Routine.</span> <span class="sc-desc">kleines Update, Bugfix, inkrementell.</span></span></li>
      <li><span class="sc-dots">●●○○○</span><span><span class="sc-name">2 — Nennenswert.</span> <span class="sc-desc">neues Feature, aber eher Nische.</span></span></li>
      <li><span class="sc-dots">●●●○○</span><span><span class="sc-name">3 — Relevant.</span> <span class="sc-desc">spürbare Verbesserung, betrifft viele.</span></span></li>
      <li><span class="sc-dots">●●●●○</span><span><span class="sc-name">4 — Stark.</span> <span class="sc-desc">verändert, wie man arbeitet, oder eröffnet eine neue Möglichkeit.</span></span></li>
      <li><span class="sc-dots">●●●●●</span><span><span class="sc-name">5 — Game-Changer.</span> <span class="sc-desc">grundlegender Sprung.</span></span></li>
    </ul>
    <p class="sc-note">Impact 1 (Routine) ist der äußerste Ring; solche Meldungen führen wir meist nur unter „Überspringen" auf — der äußere Ring bleibt daher oft leer.</p>
  </div>"""


RANGES = [
    ("today", "Heute", None),
    ("7d", "7 Tage", 7),
    ("14d", "14 Tage", 14),
    ("30d", "30 Tage", 30),
]


def range_switcher_html(page, active_key, period=""):
    """Zeitraum-Umschalter für den Meta-Block oben rechts: Links auf dieselbe
    Seite in den anderen Ansichten, darunter die konkreten Daten."""
    to_root = "" if active_key == "today" else "../"
    links = []
    for key, label, _ in RANGES:
        cls = ' class="active"' if key == active_key else ""
        href = f"{to_root}{page}.html" if key == "today" else f"{to_root}{key}/{page}.html"
        links.append(f'<a href="{href}"{cls}>{label}</a>')
    period_line = f'<div class="range-period">{esc(period)}</div>' if period else ""
    return f'<nav class="range-sw">{"".join(links)}</nav>{period_line}'


def nav_html(topics, active_id):
    ov_cls = ' class="active"' if active_id == "index" else ""
    links = [f'<a href="index.html"{ov_cls}>Übersicht</a>']
    for t in topics:
        cls = ' class="active"' if t["id"] == active_id else ""
        links.append(f'<a href="{t["id"]}.html"{cls}>{esc(t["name"])}</a>')
    return '<nav class="nav">' + "".join(links) + '</nav>'


GERMAN_MONTHS = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)


def generated_date_text(value):
    """Formatiert ein kanonisches ISO-Datum; ungültige Werte bleiben unsichtbar."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return ""
    try:
        date = datetime.date.fromisoformat(value)
    except ValueError:
        return ""
    return f"Zuletzt aktualisiert: {date.day}. {GERMAN_MONTHS[date.month - 1]} {date.year}"


def footer_html(meta):
    updated = generated_date_text(meta.get("generated"))
    updated_line = f'<br><span class="footer-updated">{esc(updated)}</span>' if updated else ""
    return (f'<div class="footer">{esc(meta.get("disclaimer", ""))}<br>'
            f'Aufbau nach dem Tech-Radar-Prinzip (Ringe = Impact, Segmente = Kategorie). '
            f'Statischer Export, kein JavaScript. Auswahl per Recherche — keine Gewähr auf Vollständigkeit.'
            f'{updated_line}</div>')


def build_topic_page(topic, meta, topics, range_key="today"):
    zeitraum = meta.get("period", "")
    ctx = topic.get("angle", "")
    entries = topic.get("items", [])
    skip = topic.get("skip", [])
    skip_items = "\n".join(
        f'      <li><b>{esc(s["reason"])}:</b> {esc(s["text"])}</li>' for s in skip)
    skip_block = (f'''  <div class="section"><h2>Überspringen kannst du in diesem Zeitraum</h2></div>
  <div class="skip">
    <p class="skip-lead">Themen, die durch die Presse gingen, aber keinen eigenen Eintrag bekommen — hier kurz erklärt, warum.</p>
    <ul>
{skip_items}
    </ul>
  </div>''') if skip else ""

    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI-Radar — {esc(topic["name"])} — {esc(zeitraum)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{CSS}
</style>
</head>
<body>
<div class="sheet">
  <header class="top">
    <h1>AI-Radar · {esc(topic["name"])}</h1>
    <div class="subrow">
      <div class="subs">
        <div class="sub">Briefing-Infografik · Stand der AI-Welt für {esc(topic["name"])}</div>
        <div class="sub">Blickwinkel: {esc(ctx)}</div>
      </div>
      <div class="meta-right">
        {range_switcher_html(topic["id"], range_key, zeitraum)}
      </div>
    </div>
  </header>
  {nav_html(topics, topic["id"])}

  <p class="lede">{esc(topic.get("summary", ""))}</p>

  <div class="board">
    <div class="board-left">
      <div class="panel">
{build_radar_svg(entries)}
      </div>
      <div class="key">
        <span><b>Ringe</b> = Impact (innen = wichtiger)</span>
        <span><b>Segmente</b> = Kategorie</span>
        <span><b>Nummer</b> = siehe Meldungen unten</span>
      </div>
    </div>
{SCALE_BLOCK.format(scale_lead=scale_with_context(ctx))}
  </div>

  <div class="section"><h2>Die Meldungen im Detail</h2></div>
  <div class="detail-list">
{build_detail(entries)}
  </div>

{skip_block}

  {footer_html(meta)}
</div>
</body>
</html>
'''


def ov_card(topic):
    top = sorted(topic.get("items", []), key=lambda e: -int(e.get("impact", 0)))[:3]
    if top:
        def title_html(e):
            url = (e.get("sources") or [{}])[0].get("url")
            if url:
                return (f'<a class="ov-item-t" href="{esc(url)}" target="_blank" rel="noopener">'
                        f'{esc(e["title"])}</a>')
            return f'<span class="ov-item-t">{esc(e["title"])}</span>'
        items = "\n".join(
            f'      <li><span class="ov-dot" style="background:{CAT_COLOR.get(e["category"], "#0075de")}"></span>'
            f'{title_html(e)}'
            f'<span class="ov-item-d">{dots(int(e["impact"]))}</span></li>'
            for e in top)
        body = f'<ul class="ov-list">\n{items}\n    </ul>'
    else:
        body = '<p class="ov-empty">In diesem Zeitraum keine eigenständigen Meldungen.</p>'
    count = len(topic.get("items", []))
    count_label = "Meldung" if count == 1 else "Meldungen"
    return f'''  <div class="ov-card">
    <div class="ov-card-head">
      <h3>{esc(topic["name"])}</h3>
      <span class="ov-count">{count} {count_label}</span>
    </div>
    <div class="ov-sub">{esc(topic.get("angle",""))}</div>
    {body}
    <a class="ov-link" href="{topic["id"]}.html">Zum Feld-Report <span>→</span></a>
  </div>'''


def build_overview(briefing, range_key="today"):
    meta = briefing["meta"]
    topics = briefing["topics"]
    order = []
    for t in topics:
        g = t.get("group") or "Weitere"
        if g not in order:
            order.append(g)
    blocks = []
    for g in order:
        grp = [t for t in topics if (t.get("group") or "Weitere") == g]
        cards = "\n".join(ov_card(t) for t in grp)
        blocks.append(f'  <div class="ov-group"><h2>{esc(g)}</h2></div>\n  <div class="ov-grid">\n{cards}\n  </div>')

    body = "\n".join(blocks)

    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(meta.get("title","AI-Briefing"))} Übersicht — {esc(meta.get("period",""))}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{CSS}
</style>
</head>
<body>
<div class="sheet">
  <header class="top">
    <h1>{esc(meta.get("title","AI-Briefing"))} — Übersicht</h1>
    <div class="subrow">
      <div class="subs">
        <div class="sub">{esc(meta.get("subtitle",""))}</div>
        <div class="sub">{len(topics)} Themenbereich(e)</div>
      </div>
      <div class="meta-right">
        {range_switcher_html("index", range_key, meta.get("period", ""))}
      </div>
    </div>
  </header>
  {nav_html(topics, "index")}

  <p class="lede">{esc(meta.get("intro",""))}</p>

{body}

  {footer_html(meta)}
</div>
</body>
</html>
'''


def main():
    briefing = json.loads(DATA.read_text(encoding="utf-8"))

    # Ingest: aktuelles Briefing in den kumulativen Pool mergen (idempotent)
    hist = history_mod.load_history()
    history_mod.ingest(hist, briefing)
    history_mod.save_history(hist)

    SITE.mkdir(exist_ok=True)
    dirs = [SITE] + [SITE / key for key, _, _ in RANGES[1:]]
    for d in dirs:
        d.mkdir(exist_ok=True)
        for old in d.glob("*.html"):
            try:
                old.unlink()
            except OSError:
                pass  # Mount erlaubt evtl. kein unlink; write_text überschreibt ohnehin

    topics = briefing["topics"]

    # Heute-Ansicht: aktuelles Briefing unverändert (wie bisher)
    (SITE / "index.html").write_text(build_overview(briefing), encoding="utf-8")
    for t in topics:
        (SITE / f'{t["id"]}.html').write_text(
            build_topic_page(t, briefing["meta"], topics), encoding="utf-8")

    # Zeitraum-Ansichten aus dem Pool
    end_iso = history_mod.parse_date(briefing["meta"].get("generated")) \
        or datetime.date.today().isoformat()
    for key, _, days in RANGES[1:]:
        rmeta = dict(briefing["meta"], period=history_mod.format_period(end_iso, days))
        rtopics = []
        for t in topics:
            rt = dict(t)
            rt["items"] = history_mod.items_for_range(hist, t["id"], end_iso, days)
            rt["summary"] = history_mod.latest_summary(hist, t["id"], end_iso) \
                or t.get("summary", "")
            rt["skip"] = []  # Skip-Block ist tagesbezogen → nur in der Heute-Ansicht
            rtopics.append(rt)
        rbriefing = {"meta": rmeta, "topics": rtopics}
        outdir = SITE / key
        (outdir / "index.html").write_text(
            build_overview(rbriefing, range_key=key), encoding="utf-8")
        for rt in rtopics:
            (outdir / f'{rt["id"]}.html').write_text(
                build_topic_page(rt, rmeta, rtopics, range_key=key), encoding="utf-8")

    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    total = sum(len(t.get("items", [])) for t in topics)
    n_hist = len(hist["items"])
    print(f"Fertig: 4 Ansichten (Heute/7d/14d/30d), {total} Meldungen heute, "
          f"{n_hist} im Pool.")
    for t in topics:
        print(f"  [{t['id']}] {len(t.get('items', []))} Meldung(en) heute")


if __name__ == "__main__":
    main()
