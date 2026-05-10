"""
Scatter plot: bank branches (RBI DBIE) vs nighttime light intensity (VIIRS 2023).

Each dot is one Indian district. Question: does economic activity (proxied by
night light) predict banking infrastructure?

Outputs:
  public/charts/branches_vs_nightlights.png         — static PNG (matplotlib)
  public/charts/branches_vs_nightlights.html        — interactive (Plotly via vanilla JS)
  public/charts/branches_vs_nightlights_data.json   — joined data for the interactive chart
"""
import json
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ─── Load data ───────────────────────────────────────────────────────
print("Loading RBI banking outlets...")
rbi = json.load(open(ROOT / 'public/indicators/rbi_banking_outlets/static.json'))
print(f"  {len(rbi['districts'])} districts")

print("Loading VIIRS nightlights 2023...")
viirs = json.load(open(ROOT / 'public/indicators/viirs_nightlights/2023-12.json'))
print(f"  {len(viirs['districts'])} districts")


# ─── Join (district, state) ──────────────────────────────────────────
def norm(s):
    return (s or '').upper().replace('-', ' ').replace('.', '').strip()

# Build VIIRS lookup keyed by (district_upper, state_upper)
viirs_lookup = {}
for r in viirs['districts']:
    key = (norm(r['district']), norm(r['state']))
    viirs_lookup[key] = (r['nl_mean'], r['nl_sum'], r['nl_max'])

joined = []
for r in rbi['districts']:
    key = (norm(r['district']), norm(r['state']))
    if key not in viirs_lookup:
        continue
    branches = int(float(r.get('rbi_outlets__branch', 0)))
    bcs = int(float(r.get('rbi_outlets__bc', 0)))
    total = int(float(r.get('rbi_outlets__total', 0)))
    nl_mean, nl_sum, nl_max = viirs_lookup[key]
    if branches < 1 or nl_mean <= 0:
        continue
    joined.append({
        'district': r['district'].title(),
        'state': r['state'].title(),
        'branches': branches,
        'bcs': bcs,
        'total_outlets': total,
        'nl_mean': nl_mean,
        'nl_sum': nl_sum,
    })

print(f"Joined: {len(joined)} districts")

# ─── Save joined data for interactive ────────────────────────────────
out_dir = ROOT / 'public/charts'
out_dir.mkdir(exist_ok=True)
data_path = out_dir / 'branches_vs_nightlights_data.json'
with open(data_path, 'w') as f:
    json.dump({
        'count': len(joined),
        'note': 'RBI Banking Outlet Locator (branches per district) vs VIIRS Annual Nightlights 2023 (mean intensity per district). Source: RBI DBIE + SHRUG v2.1, Development Data Lab.',
        'districts': joined,
    }, f, separators=(',', ':'))
print(f"Wrote {data_path} ({data_path.stat().st_size/1024:.1f} KB)")


# ─── Static PNG via matplotlib ────────────────────────────────────────
print("Plotting static PNG...")
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(11, 8), dpi=130)

xs = [d['nl_mean'] for d in joined]
ys = [d['branches'] for d in joined]

ax.scatter(xs, ys, s=12, alpha=0.55, c='#b8603e', edgecolors='none')
ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xlabel('Mean nighttime light intensity (VIIRS 2023, nW/cm²/sr)', fontsize=11)
ax.set_ylabel('Number of bank branches (RBI DBIE)', fontsize=11)
ax.set_title('Banking infrastructure vs nighttime light intensity, by Indian district',
             fontsize=13, weight='bold', loc='left', pad=14)
ax.grid(True, which='both', linestyle=':', alpha=0.3)

# Annotate top 12 districts (by branches)
top = sorted(joined, key=lambda d: -d['branches'])[:12]
for d in top:
    ax.annotate(f"{d['district']}", (d['nl_mean'], d['branches']),
                fontsize=8, color='#3d2a1c', alpha=0.85,
                xytext=(5, 4), textcoords='offset points')

# Footer
fig.text(0.99, 0.01,
         "Sources: RBI DBIE Banking Outlet Locator · VIIRS via SHRUG v2.1 (DDL, CC BY-NC-SA 4.0)",
         fontsize=8, color='#888', ha='right', va='bottom')
fig.text(0.01, 0.01, f"n = {len(joined)} districts · projectfiner.com",
         fontsize=8, color='#888', ha='left', va='bottom')

plt.tight_layout(rect=(0, 0.03, 1, 0.97))
png_path = out_dir / 'branches_vs_nightlights.png'
plt.savefig(png_path, dpi=130, bbox_inches='tight', facecolor='#fdfcfa')
print(f"Wrote {png_path} ({png_path.stat().st_size/1024:.1f} KB)")


# ─── Interactive HTML ────────────────────────────────────────────────
print("Writing interactive HTML...")
html_path = out_dir / 'branches_vs_nightlights.html'
html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Bank branches vs nighttime light · Project FINER</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap">
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    body { font-family: 'Inter', sans-serif; background: #fdfcfa; color: #1a1410; max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
    h1 { font-family: 'Playfair Display', serif; font-size: 28px; margin: 0 0 8px; }
    .lede { color: #6b6058; font-size: 14px; line-height: 1.55; max-width: 720px; }
    .meta { font-size: 11px; color: #999; margin-top: 24px; line-height: 1.55; }
    .meta a { color: #b8603e; text-decoration: none; }
    .meta a:hover { text-decoration: underline; }
    #chart { margin: 24px 0; }
  </style>
</head>
<body>
  <h1>Bank branches vs nighttime light intensity</h1>
  <p class="lede">Each dot is an Indian district. Horizontal axis: mean nighttime light radiance from VIIRS satellite imagery in 2023 (a proxy for economic activity / electrification). Vertical axis: number of bank branches in the district per RBI's DBIE database. Both axes log-scale.</p>

  <div id="chart" style="width:100%;height:640px;"></div>

  <p class="meta">
    n = <span id="n-districts"></span> districts.
    Sources:
    <a href="https://dbie.rbi.org.in/" target="_blank">RBI DBIE Banking Outlet Locator</a> ·
    VIIRS Annual Nightlights via <a href="https://www.devdatalab.org/shrug" target="_blank">SHRUG v2.1</a> (Development Data Lab, CC BY-NC-SA 4.0).
    Plaintext citations:
    Asher, Lunt, Matsuura, Novosad — World Bank Economic Review 2021.
  </p>

  <script>
    fetch('branches_vs_nightlights_data.json').then(r => r.json()).then(data => {
      document.getElementById('n-districts').textContent = data.count.toLocaleString();
      const districts = data.districts;
      const trace = {
        x: districts.map(d => d.nl_mean),
        y: districts.map(d => d.branches),
        mode: 'markers',
        type: 'scatter',
        marker: {
          size: 7, color: '#b8603e', opacity: 0.55,
          line: { width: 0 },
        },
        text: districts.map(d => `<b>${d.district}</b>, ${d.state}<br>Branches: ${d.branches.toLocaleString()}<br>BCs: ${d.bcs.toLocaleString()}<br>Total outlets: ${d.total_outlets.toLocaleString()}<br>Nightlight (mean): ${d.nl_mean.toFixed(2)}`),
        hovertemplate: '%{text}<extra></extra>',
      };
      const layout = {
        xaxis: { title: 'Mean nighttime light intensity (VIIRS 2023)', type: 'log', gridcolor: '#eee' },
        yaxis: { title: 'Bank branches per district (RBI)', type: 'log', gridcolor: '#eee' },
        hovermode: 'closest',
        plot_bgcolor: '#fdfcfa',
        paper_bgcolor: '#fdfcfa',
        font: { family: 'Inter, sans-serif', size: 12, color: '#1a1410' },
        margin: { l: 70, r: 30, t: 24, b: 60 },
      };
      Plotly.newPlot('chart', [trace], layout, { responsive: true, displayModeBar: 'hover' });
    });
  </script>
</body>
</html>"""
with open(html_path, 'w') as f:
    f.write(html)
print(f"Wrote {html_path} ({html_path.stat().st_size/1024:.1f} KB)")


# ─── Quick analysis ───────────────────────────────────────────────────
import statistics
log_xs = [math.log(x) for x in xs]
log_ys = [math.log(y) for y in ys]
n = len(log_xs)
mean_x = sum(log_xs) / n
mean_y = sum(log_ys) / n
ssxy = sum((log_xs[i]-mean_x)*(log_ys[i]-mean_y) for i in range(n))
ssxx = sum((x-mean_x)**2 for x in log_xs)
ssyy = sum((y-mean_y)**2 for y in log_ys)
r = ssxy / math.sqrt(ssxx * ssyy)
slope = ssxy / ssxx

print()
print(f"=== Scatter analysis ===")
print(f"  n districts: {n}")
print(f"  log-log Pearson r: {r:.3f}")
print(f"  log-log slope: {slope:.3f}  (i.e. branches ~ nightlights^{slope:.2f})")
print(f"  Top 5 by branches: {[d['district'] for d in sorted(joined, key=lambda x:-x['branches'])[:5]]}")
print(f"  Top 5 by nightlight: {[d['district'] for d in sorted(joined, key=lambda x:-x['nl_mean'])[:5]]}")
