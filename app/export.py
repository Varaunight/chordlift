"""
PDF and TXT export generation.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# TXT export
# ---------------------------------------------------------------------------

def generate_txt(data: dict) -> str:
    title = data.get("title") or "Unknown Track"
    artist = data.get("artist") or "Unknown Artist"
    key = data.get("key") or "?"
    bpm = data.get("bpm")
    chords = data.get("chords", [])

    lines = [
        "╔══════════════════════════════════════════╗",
        "  ChordLift",
        f"  Song:    {title}",
        f"  Artist:  {artist}",
        f"  Key:     {key}  |  BPM: {int(bpm) if bpm else '?'}",
        "══════════════════════════════════════════╝",
        "",
        f"{'Time':<10}{'Standard':<14}NNS",
        "─" * 38,
    ]
    for c in chords:
        lines.append(f"{c['time']:<10}{c['chord']:<14}{c['nns']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PDF export (via WeasyPrint)
# ---------------------------------------------------------------------------

def generate_pdf(data: dict) -> bytes:
    from weasyprint import HTML

    html = _build_pdf_html(data)
    return HTML(string=html).write_pdf()


def _build_pdf_html(data: dict) -> str:
    title = data.get("title") or "Unknown Track"
    artist = data.get("artist") or "Unknown Artist"
    key = data.get("key") or "?"
    bpm = data.get("bpm")
    chords = data.get("chords", [])

    rows = "\n".join(
        f"<tr><td>{c['time']}</td><td>{c['chord']}</td><td>{c['nns']}</td></tr>"
        for c in chords
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
  body {{ font-family: 'Courier New', monospace; margin: 2cm; color: #111; }}
  h1 {{ font-family: sans-serif; font-size: 1.6rem; margin-bottom: 0.2rem; }}
  .meta {{ font-family: sans-serif; font-size: 0.9rem; color: #555; margin-bottom: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.95rem; }}
  th {{ text-align: left; border-bottom: 2px solid #333; padding: 0.4rem 0.8rem; font-family: sans-serif; font-size: 0.8rem; text-transform: uppercase; color: #555; }}
  td {{ padding: 0.35rem 0.8rem; border-bottom: 1px solid #e5e5e5; }}
  tr:nth-child(even) td {{ background: #f9f9f9; }}
</style>
</head>
<body>
  <h1>ChordLift</h1>
  <div class="meta">
    <strong>{title}</strong> — {artist}<br/>
    Key: {key} &nbsp;|&nbsp; BPM: {int(bpm) if bpm else '?'}
  </div>
  <table>
    <thead><tr><th>Time</th><th>Chord</th><th>NNS</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""
