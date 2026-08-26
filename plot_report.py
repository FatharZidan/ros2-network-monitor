#!/usr/bin/env python3
"""
plot_report.py — Single-Session Continuous Time-Series Report Generator for BRONE ROS 2 Network Monitor

Membaca file CSV log BRONE dan secara otomatis menghasilkan:
  1. Grafik PNG Resolusi Tinggi (300 DPI Light Mode) dengan time-series kontinu & garis vertikal event marker.
  2. Laporan Interaktif HTML (Light Mode, responsif, siap dicetak / export PDF).

Penggunaan:
  # 1. Otomatis mencari dan memproses file CSV terbaru di direktori saat ini:
  python3 plot_report.py

  # 2. Memproses file CSV tertentu:
  python3 plot_report.py brone_log_jetson2nuc_50hz_128b_best_effort_20260826_201015.csv
"""

import sys
import os
import glob
import csv
import json
from datetime import datetime
from pathlib import Path


def parse_brone_csv(filepath: str) -> dict:
    """Parse a BRONE benchmark CSV file, extracting metadata and continuous time-series rows."""
    result = {
        'filepath': filepath,
        'filename': Path(filepath).name,
        'metadata': {},
        'history': [],
        'events': [],
    }

    if not os.path.exists(filepath):
        return result

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        raw_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('sep=')]

    if not raw_lines:
        return result

    # 1. Parse comments/metadata lines
    data_lines = []
    for line in raw_lines:
        if line.startswith('#'):
            clean_comment = line.lstrip('#').strip()
            if ':' in clean_comment:
                k, v = clean_comment.split(':', 1)
                result['metadata'][k.strip()] = v.strip()
        else:
            data_lines.append(line)

    if not data_lines:
        return result

    # 2. Parse CSV Table
    reader = csv.reader(data_lines)
    header = None

    for row in reader:
        if not row:
            continue
        if header is None:
            header = [c.strip() for c in row]
            continue

        entry = {}
        for h, val in zip(header, row):
            v_clean = val.strip()
            try:
                if '.' in v_clean:
                    entry[h] = float(v_clean)
                else:
                    entry[h] = int(v_clean)
            except ValueError:
                entry[h] = v_clean

        # Normalize seconds field
        sec = entry.get('second', entry.get('elapsed', len(result['history']) + 1))
        entry['second'] = sec

        # Collect event marker if present
        marker = entry.get('event_marker', '')
        if marker:
            result['events'].append({
                'second': sec,
                'label': marker,
                'timestamp_iso': entry.get('timestamp_iso', '')
            })

        result['history'].append(entry)

    # 3. Calculate Overall Aggregated Statistics
    if result['history']:
        avg_lats = [h.get('avg_lat_ms', h.get('avg_lat', 0)) for h in result['history'] if h.get('avg_lat_ms', h.get('avg_lat', 0)) > 0]
        p95_lats = [h.get('p95_lat_ms', h.get('p95_lat', 0)) for h in result['history'] if h.get('p95_lat_ms', h.get('p95_lat', 0)) > 0]
        p99_lats = [h.get('p99_lat_ms', h.get('p99_lat', 0)) for h in result['history'] if h.get('p99_lat_ms', h.get('p99_lat', 0)) > 0]
        min_lats = [h.get('min_lat_ms', h.get('min_lat', 0)) for h in result['history'] if h.get('min_lat_ms', h.get('min_lat', 0)) > 0]
        max_lats = [h.get('max_lat_ms', h.get('max_lat', 0)) for h in result['history'] if h.get('max_lat_ms', h.get('max_lat', 0)) > 0]
        hz_vals = [h.get('hz', 0) for h in result['history'] if h.get('hz', 0) > 0]
        
        last_entry = result['history'][-1]
        
        result['summary'] = {
            'avg_lat_ms': round(sum(avg_lats) / len(avg_lats), 3) if avg_lats else 0.0,
            'p95_lat_ms': round(sum(p95_lats) / len(p95_lats), 3) if p95_lats else 0.0,
            'p99_lat_ms': round(sum(p99_lats) / len(p99_lats), 3) if p99_lats else 0.0,
            'min_lat_ms': round(min(min_lats), 3) if min_lats else 0.0,
            'max_lat_ms': round(max(max_lats), 3) if max_lats else 0.0,
            'avg_hz': round(sum(hz_vals) / len(hz_vals), 1) if hz_vals else 0.0,
            'total_samples': last_entry.get('total_samples', last_entry.get('total', 0)),
            'total_gaps': last_entry.get('gaps_count', last_entry.get('total_gaps', 0)),
            'duration_sec': len(result['history']),
        }
    else:
        result['summary'] = {}

    return result


def generate_single_session_matplotlib_png(parsed_data: dict, output_png: str):
    """Generate high-res 300 DPI Light Mode PNG plots for a single continuous session."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("[INFO] matplotlib belum terinstall. Lewati pembuatan file PNG.")
        return False

    history = parsed_data['history']
    if not history:
        print(f"[WARN] Tidak ada data time-series dalam {parsed_data['filename']}")
        return False

    # Extract time series arrays
    seconds = [h.get('second', i + 1) for i, h in enumerate(history)]
    avg_lat = [h.get('avg_lat_ms', h.get('avg_lat', 0)) for h in history]
    min_lat = [h.get('min_lat_ms', h.get('min_lat', 0)) for h in history]
    max_lat = [h.get('max_lat_ms', h.get('max_lat', 0)) for h in history]
    p95_lat = [h.get('p95_lat_ms', h.get('p95_lat', 0)) for h in history]
    p99_lat = [h.get('p99_lat_ms', h.get('p99_lat', 0)) for h in history]
    hz_vals = [h.get('hz', 0) for h in history]
    gaps_vals = [h.get('gaps_count', 0) for h in history]
    events = parsed_data['events']
    summary = parsed_data.get('summary', {})
    meta = parsed_data.get('metadata', {})

    # Create figure with 3 stacked subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 11), sharex=True, gridspec_kw={'height_ratios': [2.5, 1.2, 0.8]})
    
    # Light Mode Theme Styling
    fig.patch.set_facecolor('#f8fafc')
    for ax in (ax1, ax2, ax3):
        ax.set_facecolor('#ffffff')
        ax.grid(True, linestyle='--', alpha=0.5, color='#cbd5e1')
        ax.tick_params(colors='#1e293b', labelsize=10)
        for spine in ax.spines.values():
            spine.set_color('#cbd5e1')

    # Subplot 1: Continuous Latency & Tail Latencies + Event Markers
    ax1.fill_between(seconds, min_lat, max_lat, color='#e0e7ff', alpha=0.6, label='Rentang Jitter (Min - Max)')
    ax1.plot(seconds, avg_lat, color='#0284c7', linewidth=2.2, label='Avg Latency (Rata-rata)')
    ax1.plot(seconds, p95_lat, color='#d97706', linewidth=2.0, linestyle='-', label='p95 Latency')
    ax1.plot(seconds, p99_lat, color='#dc2626', linewidth=2.2, linestyle='-', label='p99 Latency (Tail / Spike)')

    # Add Event Marker Vertical Lines
    y_max_lat = max(max_lat) if max_lat else 5.0
    ax1.set_ylim(bottom=0, top=max(y_max_lat * 1.25, 6.0))

    if events:
        for idx, evt in enumerate(events):
            t = evt['second']
            lbl = evt['label']
            ax1.axvline(x=t, color='#7c3aed', linestyle='--', linewidth=1.8, alpha=0.85)
            # Add text box on top
            ax1.text(
                t, y_max_lat * 1.05, f" 📌 t={t}s: {lbl} ",
                rotation=0, verticalalignment='bottom', horizontalalignment='left',
                fontsize=9, fontweight='bold', color='#4c1d95',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#ede9fe', edgecolor='#a78bfa', alpha=0.95)
            )

    ax1.set_ylabel("Latensi Komunikasi (ms)", fontsize=11, fontweight='bold', color='#0f172a', labelpad=8)
    ax1.set_title(
        f"Laporan Pengukuran Latensi Kontinu ROS 2 — {parsed_data['filename']}\n"
        f"Avg: {summary.get('avg_lat_ms', 0):.2f} ms | p95: {summary.get('p95_lat_ms', 0):.2f} ms | "
        f"p99: {summary.get('p99_lat_ms', 0):.2f} ms | Total Sampel: {summary.get('total_samples', 0):,}",
        fontsize=12, fontweight='bold', color='#0f172a', pad=12
    )
    ax1.legend(loc='upper right', framealpha=0.9, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9)

    # Subplot 2: Message Frequency Throughput (Hz)
    target_hz = float(meta.get('Target Frequency', '50').replace('Hz', '').strip() or 50)
    ax2.plot(seconds, hz_vals, color='#0d9488', linewidth=2.0, label=f'Frekuensi Aktual (Rata-rata: {summary.get("avg_hz", 50):.1f} Hz)')
    ax2.axhline(y=target_hz, color='#eab308', linestyle=':', linewidth=1.8, label=f'Target Baseline ({target_hz:.0f} Hz)')
    ax2.set_ylabel("Frekuensi (Hz)", fontsize=11, fontweight='bold', color='#0f172a', labelpad=8)
    ax2.set_ylim(bottom=0, top=max(max(hz_vals) if hz_vals else target_hz, target_hz) * 1.25)
    ax2.legend(loc='upper right', framealpha=0.9, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9)

    # Subplot 3: Packet Drops / Gaps Count
    ax3.bar(seconds, gaps_vals, color='#ef4444', width=0.8, alpha=0.75, label='Paket Tercecer / Drop (Gaps)')
    ax3.set_ylabel("Paket Drop", fontsize=11, fontweight='bold', color='#0f172a', labelpad=8)
    ax3.set_xlabel("Waktu Pengujian (Detik) / Elapsed Time (s)", fontsize=11, fontweight='bold', color='#0f172a', labelpad=8)
    ax3.set_ylim(bottom=0, top=max(max(gaps_vals) if gaps_vals else 1, 3))
    ax3.legend(loc='upper right', framealpha=0.9, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9)

    plt.tight_layout()
    plt.savefig(output_png, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"[SUKSES] Grafik PNG Resolusi Tinggi (300 DPI) tersimpan di: {output_png}")
    return True


def generate_single_session_html_report(parsed_data: dict, output_filename: str):
    """Generate modern, interactive Light Mode HTML report for a single continuous benchmark session."""
    history = parsed_data['history']
    summary = parsed_data.get('summary', {})
    meta = parsed_data.get('metadata', {})
    events = parsed_data.get('events', [])
    data_json = json.dumps(parsed_data, indent=2)

    html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BRONE — Laporan Uji Latensi ROS 2 ({parsed_data['filename']})</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --bg-primary: #f8fafc;
            --bg-secondary: #ffffff;
            --border-subtle: #e2e8f0;
            --border-glow: #cbd5e1;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --accent-blue: #0284c7;
            --accent-teal: #0d9488;
            --accent-amber: #d97706;
            --accent-red: #dc2626;
            --accent-purple: #7c3aed;
            --radius: 16px;
            --radius-sm: 10px;
            --shadow-card: 0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.04);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            padding: 24px;
            max-width: 1360px;
            margin: 0 auto;
            line-height: 1.5;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg-secondary);
            padding: 18px 24px;
            border-radius: var(--radius);
            border: 1px solid var(--border-subtle);
            box-shadow: var(--shadow-card);
            margin-bottom: 20px;
        }}
        .header-title h1 {{ font-size: 20px; font-weight: 700; color: var(--text-primary); }}
        .header-title p {{ font-size: 13px; color: var(--text-secondary); margin-top: 2px; }}
        .btn-print {{
            padding: 8px 16px;
            background: var(--bg-primary);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-sm);
            color: var(--text-primary);
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .btn-print:hover {{ background: #e2e8f0; }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 14px;
            margin-bottom: 20px;
        }}
        .metric-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius);
            padding: 16px 18px;
            box-shadow: var(--shadow-card);
        }}
        .metric-label {{ font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px; }}
        .metric-val {{ font-family: 'JetBrains Mono', monospace; font-size: 24px; font-weight: 700; color: var(--text-primary); }}
        .metric-unit {{ font-size: 12px; color: var(--text-muted); font-weight: 500; }}
        .chart-box {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius);
            padding: 20px;
            box-shadow: var(--shadow-card);
            margin-bottom: 20px;
        }}
        .chart-box h3 {{ font-size: 14px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px; }}
        .chart-box p {{ font-size: 12px; color: var(--text-secondary); margin-bottom: 14px; }}
        .chart-canvas-container {{ position: relative; height: 260px; width: 100%; }}
        .event-box {{
            background: #faf5ff;
            border: 1px solid #e9d5ff;
            border-radius: var(--radius);
            padding: 14px 18px;
            margin-bottom: 20px;
        }}
        .event-box h4 {{ font-size: 12px; font-weight: 700; color: #6b21a8; text-transform: uppercase; margin-bottom: 8px; }}
        .event-list {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .event-pill {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            padding: 4px 10px;
            background: #ffffff;
            border: 1px solid #d8b4fe;
            border-radius: 6px;
            color: #7e22ce;
            font-weight: 600;
        }}
        footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            padding: 16px;
            border-top: 1px solid var(--border-subtle);
        }}
    </style>
</head>
<body>

<header>
    <div class="header-title">
        <h1>📊 Laporan Uji Latensi Kontinu ROS 2 (BRONE)</h1>
        <p>File Sumber: <code>{parsed_data['filename']}</code> • Durasi: {summary.get('duration_sec', 0)} detik</p>
    </div>
    <button class="btn-print" onclick="window.print()">
        <span>🖨️ Cetak / Simpan PDF</span>
    </button>
</header>

<div class="metrics-grid">
    <div class="metric-card">
        <div class="metric-label">Avg Latency</div>
        <div class="metric-val">{summary.get('avg_lat_ms', 0):.2f} <span class="metric-unit">ms</span></div>
    </div>
    <div class="metric-card">
        <div class="metric-label">p95 Latency</div>
        <div class="metric-val" style="color: var(--accent-amber);">{summary.get('p95_lat_ms', 0):.2f} <span class="metric-unit">ms</span></div>
    </div>
    <div class="metric-card">
        <div class="metric-label">p99 Latency (Tail)</div>
        <div class="metric-val" style="color: var(--accent-red);">{summary.get('p99_lat_ms', 0):.2f} <span class="metric-unit">ms</span></div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Throughput Rata-rata</div>
        <div class="metric-val" style="color: var(--accent-teal);">{summary.get('avg_hz', 50):.1f} <span class="metric-unit">Hz</span></div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Total Sampel</div>
        <div class="metric-val">{summary.get('total_samples', 0):,} <span class="metric-unit">pesan</span></div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Total Paket Drop</div>
        <div class="metric-val" style="color: { 'var(--accent-red)' if summary.get('total_gaps', 0) > 0 else 'var(--text-primary)' };">{summary.get('total_gaps', 0)} <span class="metric-unit">gaps</span></div>
    </div>
</div>

{ f'''<div class="event-box">
    <h4>📌 Event / Perintah yang Ditandai Selama Pengujian</h4>
    <div class="event-list">
        {''.join([f'<span class="event-pill">📌 t={e["second"]}s: {e["label"]}</span>' for e in events])}
    </div>
</div>''' if events else '' }

<div class="chart-box">
    <h3>1. Fluktuasi Latensi Kontinu (Detik demi Detik)</h3>
    <p>Grafik garis waktu menunjukkan nilai rata-rata, p95, p99, dan sebaran jitter per detik.</p>
    <div class="chart-canvas-container">
        <canvas id="chartLatency"></canvas>
    </div>
</div>

<div class="chart-box">
    <h3>2. Kestabilan Throughput Frekuensi (Hz)</h3>
    <p>Kestabilan laju pengiriman paket per detik terhadap baseline target frekuensi.</p>
    <div class="chart-canvas-container">
        <canvas id="chartHz"></canvas>
    </div>
</div>

<footer>
    BRONE ROS 2 Network Monitor • Universitas Brawijaya • Laporan Dihasilkan Secara Otomatis
</footer>

<script>
    const reportData = {data_json};
    const history = reportData.history || [];
    const events = reportData.events || [];

    const labels = history.map((h, i) => `${{h.second || i + 1}}s`);
    const avgLats = history.map(h => h.avg_lat_ms || h.avg_lat || 0);
    const minLats = history.map(h => h.min_lat_ms || h.min_lat || 0);
    const maxLats = history.map(h => h.max_lat_ms || h.max_lat || 0);
    const p95Lats = history.map(h => h.p95_lat_ms || h.p95_lat || 0);
    const p99Lats = history.map(h => h.p99_lat_ms || h.p99_lat || 0);
    const hzVals  = history.map(h => h.hz || 0);

    Chart.defaults.color = '#475569';
    Chart.defaults.font.family = "'JetBrains Mono', monospace";
    Chart.defaults.font.size = 11;

    // Chart Latency
    new Chart(document.getElementById('chartLatency'), {{
        type: 'line',
        data: {{
            labels: labels,
            datasets: [
                {{
                    label: 'Avg Latency',
                    data: avgLats,
                    borderColor: '#0284c7',
                    backgroundColor: 'rgba(2, 132, 199, 0.08)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.2,
                    pointRadius: 0
                }},
                {{
                    label: 'p95 Latency',
                    data: p95Lats,
                    borderColor: '#d97706',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.2,
                    pointRadius: 0
                }},
                {{
                    label: 'p99 Latency (Tail)',
                    data: p99Lats,
                    borderColor: '#dc2626',
                    borderWidth: 2.2,
                    fill: false,
                    tension: 0.2,
                    pointRadius: 0
                }},
                {{
                    label: 'Max Latency',
                    data: maxLats,
                    borderColor: '#f97316',
                    borderWidth: 1,
                    borderDash: [3, 3],
                    fill: false,
                    pointRadius: 0
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            scales: {{
                x: {{
                    title: {{ display: true, text: 'Waktu Pengujian (Detik) / Elapsed Time (s)', color: '#475569', font: {{ weight: '600' }} }},
                    grid: {{ color: 'rgba(0, 0, 0, 0.04)' }}
                }},
                y: {{
                    beginAtZero: true,
                    title: {{ display: true, text: 'Latensi Komunikasi (ms)', color: '#475569', font: {{ weight: '600' }} }},
                    grid: {{ color: 'rgba(0, 0, 0, 0.05)' }}
                }}
            }}
        }}
    }});

    // Chart Hz
    new Chart(document.getElementById('chartHz'), {{
        type: 'line',
        data: {{
            labels: labels,
            datasets: [
                {{
                    label: 'Frekuensi Aktual (Hz)',
                    data: hzVals,
                    borderColor: '#0d9488',
                    backgroundColor: 'rgba(13, 148, 136, 0.08)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.2,
                    pointRadius: 0
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            scales: {{
                x: {{
                    title: {{ display: true, text: 'Waktu Pengujian (Detik) / Elapsed Time (s)', color: '#475569', font: {{ weight: '600' }} }},
                    grid: {{ color: 'rgba(0, 0, 0, 0.04)' }}
                }},
                y: {{
                    beginAtZero: true,
                    title: {{ display: true, text: 'Throughput Frekuensi (Hz)', color: '#475569', font: {{ weight: '600' }} }},
                    grid: {{ color: 'rgba(0, 0, 0, 0.05)' }}
                }}
            }}
        }}
    }});
</script>

</body>
</html>
"""
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"[SUKSES] Laporan Interaktif HTML tersimpan di: {output_filename}")


def main():
    args = sys.argv[1:]
    csv_files = []

    if args:
        for a in args:
            matches = glob.glob(a)
            if matches:
                csv_files.extend(matches)
            elif os.path.exists(a):
                csv_files.append(a)
    else:
        # Cari file CSV terbaru di direktori saat ini
        all_logs = sorted(glob.glob("brone_log_*.csv"), key=os.path.getmtime, reverse=True)
        if all_logs:
            csv_files = [all_logs[0]]  # Ambil yang terbaru

    if not csv_files:
        print("[ERROR] Tidak ditemukan file CSV log BRONE (brone_log_*.csv) untuk di-plot.")
        print("Penggunaan: python3 plot_report.py <nama_file_log.csv>")
        sys.exit(1)

    print(f"=== BRONE Visual Report Generator (Single Session Continuous Mode) ===")
    print(f"Ditemukan {len(csv_files)} file CSV log untuk diproses.")

    for filepath in csv_files:
        print(f"\nMemproses file: {filepath}")
        data = parse_brone_csv(filepath)
        if not data['history']:
            print(f"[LEWAT] File {filepath} kosong atau tidak memiliki riwayat data time-series.")
            continue

        base_name = Path(filepath).stem
        output_png = f"{base_name}_plot.png"
        output_html = f"{base_name}_report.html"

        # Generate 300 DPI PNG
        generate_single_session_matplotlib_png(data, output_png)

        # Generate HTML Report
        generate_single_session_html_report(data, output_html)

    print("\n✅ Seluruh proses visualisasi selesai!")


if __name__ == '__main__':
    main()
