"""
Two scatter plots: Meta Relative Wealth Index (RWI) vs:
  1. Bank branches (RBI DBIE)
  2. Banking Correspondents — BCs (RBI DBIE)

Each dot is one Indian district.

Outputs:
  public/charts/rwi_vs_branches.png
  public/charts/rwi_vs_bcs.png
"""
import json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

print("Loading...")
rbi = json.load(open(ROOT / 'public/indicators/rbi_banking_outlets/static.json'))
rwi = json.load(open(ROOT / 'public/indicators/facebook_rwi/2021-12.json'))


def norm(s):
    return (s or '').upper().replace('-', ' ').replace('.', '').strip()


# Build RWI lookup keyed by (district_upper, state_upper)
rwi_lookup = {}
for r in rwi['districts']:
    rwi_lookup[(norm(r['district']), norm(r['state']))] = r['rwi_mean']

joined = []
for r in rbi['districts']:
    key = (norm(r['district']), norm(r['state']))
    if key not in rwi_lookup: continue
    branches = int(float(r.get('rbi_outlets__branch', 0)))
    bcs = int(float(r.get('rbi_outlets__bc', 0)))
    if branches < 1: continue
    joined.append({
        'district': r['district'].title(),
        'state': r['state'].title(),
        'branches': branches,
        'bcs': bcs,
        'rwi': rwi_lookup[key],
    })

print(f"Joined: {len(joined)} districts")

# Stats helper
def loglog_stats(xs, ys, label):
    log_xs = [math.log(x) for x in xs if x > 0]
    log_ys = [math.log(y) for y in ys if y > 0]
    n = min(len(log_xs), len(log_ys))
    log_xs, log_ys = log_xs[:n], log_ys[:n]
    mx, my = sum(log_xs)/n, sum(log_ys)/n
    ssxy = sum((log_xs[i]-mx)*(log_ys[i]-my) for i in range(n))
    ssxx = sum((x-mx)**2 for x in log_xs)
    ssyy = sum((y-my)**2 for y in log_ys)
    r = ssxy / math.sqrt(ssxx * ssyy)
    print(f"  {label}: n={n}, log-log Pearson r={r:+.3f}")


# ─── PLOTS ───
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out_dir = ROOT / 'public/charts'
out_dir.mkdir(exist_ok=True)


def make_html(joined, ykey, ylabel, title, html_name, color, x_axis_label='Meta Relative Wealth Index (RWI), 2021'):
    """Interactive Plotly HTML, data inlined for file:// compatibility."""
    sub = [d for d in joined if d[ykey] > 0]
    inline_data = json.dumps({'count': len(sub), 'districts': sub}, separators=(',', ':'))
    plot_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title} · Project FINER</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap">
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    body {{ font-family: 'Inter', sans-serif; background: #fdfcfa; color: #1a1410; max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}
    h1 {{ font-family: 'Playfair Display', serif; font-size: 28px; margin: 0 0 8px; }}
    .lede {{ color: #6b6058; font-size: 14px; line-height: 1.55; max-width: 720px; }}
    .meta {{ font-size: 11px; color: #999; margin-top: 24px; line-height: 1.55; }}
    .meta a {{ color: #b8603e; text-decoration: none; }}
    .meta a:hover {{ text-decoration: underline; }}
    #chart {{ margin: 24px 0; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class="lede">Each dot is an Indian district. X axis: Meta's Relative Wealth Index (RWI), where 0 ≈ India average. Y axis: <strong>{ylabel}</strong> (log scale). Hover for details.</p>

  <div id="chart" style="width:100%;height:640px;"></div>

  <p class="meta">
    n = <span id="n">—</span> districts ·
    Sources: Meta RWI 2021 (<em>Chi et al., PNAS 2022</em>) via <a href="https://www.devdatalab.org/shrug" target="_blank">SHRUG v2.1</a> (Development Data Lab, CC BY-NC-SA 4.0) ·
    <a href="https://dbie.rbi.org.in/" target="_blank">RBI DBIE Banking Outlet Locator</a>
  </p>

  <script>
    const data = {inline_data};
    document.getElementById('n').textContent = data.count.toLocaleString();
    const districts = data.districts;
    const trace = {{
      x: districts.map(d => d.rwi),
      y: districts.map(d => d['{ykey}']),
      mode: 'markers', type: 'scatter',
      marker: {{ size: 7, color: '{color}', opacity: 0.55, line: {{ width: 0 }} }},
      text: districts.map(d => `<b>${{d.district}}</b>, ${{d.state}}<br>RWI: ${{d.rwi.toFixed(2)}}<br>Branches: ${{d.branches.toLocaleString()}}<br>BCs: ${{d.bcs.toLocaleString()}}`),
      hovertemplate: '%{{text}}<extra></extra>',
    }};
    const layout = {{
      xaxis: {{ title: '{x_axis_label}', gridcolor: '#eee', zeroline: true, zerolinecolor: '#aaa' }},
      yaxis: {{ title: '{ylabel}', type: 'log', gridcolor: '#eee' }},
      hovermode: 'closest',
      plot_bgcolor: '#fdfcfa', paper_bgcolor: '#fdfcfa',
      font: {{ family: 'Inter, sans-serif', size: 12, color: '#1a1410' }},
      margin: {{ l: 70, r: 30, t: 24, b: 60 }},
      shapes: [{{ type: 'line', x0: 0, x1: 0, yref: 'paper', y0: 0, y1: 1, line: {{ color: '#aaa', dash: 'dash', width: 1 }} }}],
      annotations: [{{ x: 0, xref: 'x', y: 1, yref: 'paper', text: 'India avg', showarrow: false, font: {{ size: 9, color: '#888' }}, xshift: -8, yshift: -4, xanchor: 'right' }}],
    }};
    Plotly.newPlot('chart', [trace], layout, {{ responsive: true }});
  </script>
</body>
</html>"""
    path = out_dir / html_name
    with open(path, 'w') as f:
        f.write(plot_html)
    print(f"  → {path.name} ({path.stat().st_size/1024:.0f} KB, {len(sub)} pts)")


def make_plot(joined, ykey, ylabel, title, png_name, color):
    fig, ax = plt.subplots(figsize=(11, 8), dpi=130)
    sub = [d for d in joined if d[ykey] > 0]
    xs = [d['rwi'] for d in sub]
    ys = [d[ykey] for d in sub]
    ax.scatter(xs, ys, s=12, alpha=0.55, c=color, edgecolors='none')
    ax.set_yscale('log')
    ax.set_xlabel('Meta Relative Wealth Index (RWI), 2021', fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=13, weight='bold', loc='left', pad=14)
    ax.grid(True, which='both', linestyle=':', alpha=0.3)
    ax.axvline(0, color='#888', linestyle='--', linewidth=0.7, alpha=0.5)
    ax.text(0.02, 0.98, 'RWI = 0 ≈ India avg', transform=ax.transAxes,
            fontsize=8, color='#888', va='top', alpha=0.7)
    # Label top 12 by y
    top = sorted(sub, key=lambda d: -d[ykey])[:12]
    for d in top:
        ax.annotate(d['district'], (d['rwi'], d[ykey]),
                    fontsize=8, color='#3d2a1c', alpha=0.85,
                    xytext=(5, 4), textcoords='offset points')
    fig.text(0.99, 0.01,
             "Sources: Meta RWI 2021 (Chi et al. PNAS 2022) via SHRUG/DDL · RBI DBIE Banking Outlet Locator",
             fontsize=8, color='#888', ha='right', va='bottom')
    fig.text(0.01, 0.01, f"n = {len(sub)} districts · projectfiner.com",
             fontsize=8, color='#888', ha='left', va='bottom')
    plt.tight_layout(rect=(0, 0.03, 1, 0.97))
    path = out_dir / png_name
    plt.savefig(path, dpi=130, bbox_inches='tight', facecolor='#fdfcfa')
    plt.close()
    print(f"  → {path.name}  ({path.stat().st_size/1024:.0f} KB)")
    return sub


print("\nPlot 1: RWI vs Bank Branches")
sub1 = make_plot(joined, 'branches', 'Number of bank branches (RBI DBIE)',
                 'Bank branches vs Relative Wealth Index, by Indian district',
                 'rwi_vs_branches.png', '#b8603e')
make_html(joined, 'branches', 'Bank branches', 'Bank branches vs RWI', 'rwi_vs_branches.html', '#b8603e')
loglog_stats([d['rwi']+3 for d in sub1], [d['branches'] for d in sub1],
             'RWI(shifted)→branches')

print("\nPlot 2: RWI vs Banking Correspondents (BCs)")
sub2 = make_plot(joined, 'bcs', 'Number of Business Correspondents (RBI DBIE)',
                 'Business Correspondents vs Relative Wealth Index, by Indian district',
                 'rwi_vs_bcs.png', '#3d7a8e')
make_html(joined, 'bcs', 'Business Correspondents', 'Business Correspondents vs RWI', 'rwi_vs_bcs.html', '#3d7a8e')
loglog_stats([d['rwi']+3 for d in sub2], [d['bcs'] for d in sub2],
             'RWI(shifted)→BCs')

# Pearson r on RWI directly (linear) vs log(branches/BCs)
def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs)/n, sum(ys)/n
    ssxy = sum((xs[i]-mx)*(ys[i]-my) for i in range(n))
    ssxx = sum((x-mx)**2 for x in xs)
    ssyy = sum((y-my)**2 for y in ys)
    return ssxy / math.sqrt(ssxx * ssyy)


r_b = pearson([d['rwi'] for d in sub1], [math.log(d['branches']) for d in sub1])
r_bc = pearson([d['rwi'] for d in sub2], [math.log(d['bcs']) for d in sub2])
print(f"\nLinear-RWI vs log-branches Pearson r = {r_b:+.3f}")
print(f"Linear-RWI vs log-BCs    Pearson r = {r_bc:+.3f}")

# Top/bottom RWI districts and their branch/BC counts
print("\nTop 5 RWI districts:")
for d in sorted(joined, key=lambda x: -x['rwi'])[:5]:
    print(f"  RWI {d['rwi']:+.2f}  {d['district']:<25} branches={d['branches']:>5}  BCs={d['bcs']:>5}")
print("Bottom 5 RWI districts:")
for d in sorted(joined, key=lambda x: x['rwi'])[:5]:
    print(f"  RWI {d['rwi']:+.2f}  {d['district']:<25} branches={d['branches']:>5}  BCs={d['bcs']:>5}")
