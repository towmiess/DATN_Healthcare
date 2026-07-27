HEAD = '''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="DejaVu Sans, sans-serif">
<rect width="{w}" height="{h}" fill="white"/>
<defs>
  <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L0,6 L9,3 z" fill="#333"/>
  </marker>
</defs>
'''
TAIL = '</svg>'

def actor(x, y, label, scale=1.0):
    s = scale
    head_r = 10*s
    parts = []
    cy_head = y + head_r
    parts.append(f'<circle cx="{x}" cy="{cy_head}" r="{head_r}" fill="none" stroke="#333" stroke-width="2"/>')
    body_top = cy_head + head_r
    body_bot = body_top + 28*s
    parts.append(f'<line x1="{x}" y1="{body_top}" x2="{x}" y2="{body_bot}" stroke="#333" stroke-width="2"/>')
    parts.append(f'<line x1="{x-16*s}" y1="{body_top+10*s}" x2="{x+16*s}" y2="{body_top+10*s}" stroke="#333" stroke-width="2"/>')
    parts.append(f'<line x1="{x}" y1="{body_bot}" x2="{x-14*s}" y2="{body_bot+22*s}" stroke="#333" stroke-width="2"/>')
    parts.append(f'<line x1="{x}" y1="{body_bot}" x2="{x+14*s}" y2="{body_bot+22*s}" stroke="#333" stroke-width="2"/>')
    for i, line in enumerate(label.split("\\n")):
        parts.append(f'<text x="{x}" y="{body_bot+22*s+18*s+i*15*s}" font-size="{13*s}" font-weight="bold" text-anchor="middle" fill="#111">{line}</text>')
    return "\n".join(parts), (body_bot+22*s)

def usecase(cx, cy, rx, ry, lines, fill="#EAF2FF", stroke="#2F6FDE", fs=13):
    parts = [f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>']
    n = len(lines)
    start_y = cy - (n-1)*(fs+3)/2
    for i, line in enumerate(lines):
        parts.append(f'<text x="{cx}" y="{start_y+i*(fs+3)+4}" font-size="{fs}" text-anchor="middle" fill="#0b2b57">{line}</text>')
    return "\n".join(parts)

def boundary(x, y, w, h, label, fs=15):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#FAFCFF" stroke="#666" stroke-width="1.5" rx="6"/>'
            f'<text x="{x+w/2}" y="{y+26}" font-size="{fs}" font-weight="bold" text-anchor="middle" fill="#222">{label}</text>')

def line(x1, y1, x2, y2, dashed=False, arrow=False, label=None, label_dx=0, label_dy=-6, color="#333", stroke_width=1.5):
    dash = ' stroke-dasharray="6,4"' if dashed else ''
    mk = ' marker-end="url(#arrow)"' if arrow else ''
    parts = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{stroke_width}"{dash}{mk}/>']
    if label:
        mx, my = (x1+x2)/2 + label_dx, (y1+y2)/2 + label_dy
        parts.append(f'<text x="{mx}" y="{my}" font-size="11" font-style="italic" text-anchor="middle" fill="#555">{label}</text>')
    return "\n".join(parts)

def title(x, y, text, fs=20):
    return f'<text x="{x}" y="{y}" font-size="{fs}" font-weight="bold" text-anchor="middle" fill="#111">{text}</text>'
