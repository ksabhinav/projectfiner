"""
Scatter: Meta RWI vs PhonePe UPI transaction count + amount.

Outputs interactive HTML (Plotly, data inlined for file:// compatibility).
"""
import json, math, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

print("Loading...")
db = sqlite3.connect(ROOT / 'db/finer.db')
rwi = json.load(open(ROOT / 'public/indicators/facebook_rwi/2021-12.json'))


def norm(s):
    return (s or '').upper().replace('-', ' ').replace('.', '').strip()


# RWI lookup
rwi_lookup = {}
for r in rwi['districts']:
    rwi_lookup[(norm(r['district']), norm(r['state']))] = r['rwi_mean']

# Latest PhonePe quarter
latest_q = db.execute("""
    SELECT MAX(p.code) FROM phonepe_data ph JOIN periods p ON ph.period_id=p.id
""").fetchone()[0]
print(f"Latest PhonePe quarter: {latest_q}")

# Aggregate PhonePe to district
rows = db.execute("""
    SELECT ph.district_name_raw, ph.state_slug, ph.transaction_count, ph.transaction_amount
    FROM phonepe_data ph JOIN periods p ON ph.period_id=p.id
    WHERE p.code = ?
""", (latest_q,)).fetchall()

joined = []
no_match = 0
for d_raw, s_slug, cnt, amt in rows:
    key = (norm(d_raw), norm(s_slug))
    if key not in rwi_lookup:
        no_match += 1
        continue
    if cnt < 100: continue  # skip tiny districts
    joined.append({
        'district': d_raw.title() if d_raw else '?',
        'state': s_slug.replace('-', ' ').title() if s_slug else '?',
        'rwi': rwi_lookup[key],
        'txn_count': int(cnt),
        'txn_amount': float(amt),
    })
print(f"Joined: {len(joined)} districts ({no_match} unmatched)")
db.close()

# Stats
def pearson(xs, ys):
    n = len(xs); mx, my = sum(xs)/n, sum(ys)/n
    ssxy = sum((xs[i]-mx)*(ys[i]-my) for i in range(n))
    ssxx = sum((x-mx)**2 for x in xs)
    ssyy = sum((y-my)**2 for y in ys)
    return ssxy / math.sqrt(ssxx * ssyy)

r_cnt = pearson([d['rwi'] for d in joined], [math.log(d['txn_count']) for d in joined])
r_amt = pearson([d['rwi'] for d in joined], [math.log(d['txn_amount']) for d in joined])
print(f"  Linear-RWI vs log(txn_count)  Pearson r = {r_cnt:+.3f}")
print(f"  Linear-RWI vs log(txn_amount) Pearson r = {r_amt:+.3f}")

# Quick "transactions per RWI tier" stats
import statistics
buckets = {'rich (RWI>0.5)': [], 'mid (-0.1..0.5)': [], 'poor (RWI<-0.1)': []}
for d in joined:
    if d['rwi'] > 0.5: buckets['rich (RWI>0.5)'].append(d['txn_count'])
    elif d['rwi'] > -0.1: buckets['mid (-0.1..0.5)'].append(d['txn_count'])
    else: buckets['poor (RWI<-0.1)'].append(d['txn_count'])
print("\nMedian PhonePe txn count per district by RWI tier:")
for label, vs in buckets.items():
    if vs:
        med = sorted(vs)[len(vs)//2]
        print(f"  {label:<22} n={len(vs):>3}  median {med:>12,.0f}")

# ─── Interactive HTML ───
out_dir = ROOT / 'public/charts'
out_dir.mkdir(exist_ok=True)
inline = json.dumps({'count': len(joined), 'period': latest_q, 'districts': joined}, separators=(',', ':'))

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>UPI transactions vs Wealth Index · Project FINER</title>
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
  .toggle {{ display: inline-flex; gap: 0; border: 1px solid #e0dcd4; border-radius: 6px; overflow: hidden; margin-top: 16px; }}
  .toggle button {{ background: transparent; border: 0; padding: 8px 16px; font-family: 'Inter', sans-serif; font-size: 12px; font-weight: 500; color: #6b6058; cursor: pointer; transition: all 0.15s; }}
  .toggle button.active {{ background: #b8603e; color: white; }}
  .toggle button:not(.active):hover {{ background: #f5f0e8; }}
  #chart {{ margin: 16px 0 0; }}
  .stat-pill {{ display: inline-block; margin: 8px 8px 0 0; padding: 4px 10px; background: #f5f0e8; border-radius: 12px; font-size: 11px; color: #6b4c2a; }}
</style>
</head>
<body>
<h1>UPI transactions vs Relative Wealth Index</h1>
<p class="lede">Each dot is an Indian district. X axis: Meta's Relative Wealth Index (RWI), where 0 ≈ India average. Y axis (log): PhonePe UPI volume (toggle between transaction count and ₹ amount).</p>

<div>
  <span class="stat-pill">RWI × log(count) · r = {r_cnt:+.2f}</span>
  <span class="stat-pill">RWI × log(amount) · r = {r_amt:+.2f}</span>
  <span class="stat-pill">{len(joined)} districts · PhonePe {latest_q}</span>
</div>

<div class="toggle">
  <button id="btn-count" class="active" onclick="setMetric('count')">Transaction count</button>
  <button id="btn-amount" onclick="setMetric('amount')">Transaction amount (₹)</button>
</div>

<div id="chart" style="width:100%;height:640px;"></div>

<p class="meta">
  Sources: Meta RWI 2021 (<em>Chi et al., PNAS 2022</em>) via <a href="https://www.devdatalab.org/shrug" target="_blank">SHRUG v2.1</a> (Development Data Lab, CC BY-NC-SA 4.0) ·
  <a href="https://www.phonepe.com/pulse/" target="_blank">PhonePe Pulse</a>, {latest_q}
</p>

<script>
  const data = {inline};
  let currentMetric = 'count';

  function plot() {{
    const districts = data.districts;
    const yvals = districts.map(d => currentMetric === 'count' ? d.txn_count : d.txn_amount);
    const ylabel = currentMetric === 'count' ? 'PhonePe UPI transactions' : 'PhonePe UPI amount (₹)';
    const trace = {{
      x: districts.map(d => d.rwi), y: yvals,
      mode: 'markers', type: 'scatter',
      marker: {{ size: 7, color: '#5a7a3a', opacity: 0.55 }},
      text: districts.map(d => `<b>${{d.district}}</b>, ${{d.state}}<br>RWI: ${{d.rwi.toFixed(2)}}<br>UPI count: ${{d.txn_count.toLocaleString()}}<br>UPI amount: ₹${{(d.txn_amount/1e7).toFixed(1)}} cr`),
      hovertemplate: '%{{text}}<extra></extra>',
    }};
    Plotly.newPlot('chart', [trace], {{
      xaxis: {{ title: 'Meta RWI (2021)', gridcolor: '#eee' }},
      yaxis: {{ title: ylabel, type: 'log', gridcolor: '#eee' }},
      plot_bgcolor: '#fdfcfa', paper_bgcolor: '#fdfcfa',
      font: {{ family: 'Inter, sans-serif', size: 12, color: '#1a1410' }},
      margin: {{ l: 80, r: 30, t: 20, b: 60 }},
      shapes: [{{ type: 'line', x0: 0, x1: 0, yref: 'paper', y0: 0, y1: 1, line: {{ color: '#aaa', dash: 'dash', width: 1 }} }}],
    }}, {{ responsive: true }});
  }}

  function setMetric(m) {{
    currentMetric = m;
    document.getElementById('btn-count').classList.toggle('active', m === 'count');
    document.getElementById('btn-amount').classList.toggle('active', m === 'amount');
    plot();
  }}

  plot();
</script>
</body>
</html>"""

path = out_dir / 'rwi_vs_phonepe.html'
with open(path, 'w') as f:
    f.write(html)
print(f"\nWrote {path.name} ({path.stat().st_size/1024:.0f} KB)")
