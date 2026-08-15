#!/usr/bin/env python3
"""
plot_report.py — Visual Report Generator for BRONE ROS 2 Network Monitor

Membaca file CSV log BRONE dan secara otomatis menghasilkan:
  1. Grafik PNG Resolusi Tinggi (jika matplotlib terinstall)
  2. Laporan Interaktif HTML (dapat dibuka langsung di browser Windows/Linux)
  3. Tabel Perbandingan Multi-Skenario (jika diberikan lebih dari 1 file CSV)

Penggunaan:
  # 1. Otomatis mencari dan memproses file CSV terbaru di direktori saat ini:
  python3 plot_report.py

  # 2. Memproses file CSV tertentu:
  python3 plot_report.py brone_log_jetson2jetson_50hz_128b_best_effort_20260815_132811.csv

  # 3. Membandingkan beberapa pengujian sekaligus:
  python3 plot_report.py brone_log_nuc2nuc_*.csv brone_log_jetson2jetson_*.csv brone_log_jetson2nuc_*.csv
"""

import sys
import os
import glob
import csv
import json
from datetime import datetime
from pathlib import Path


def parse_brone_csv(filepath: str) -> dict:
    """Parse a BRONE benchmark CSV file, extracting summary and window history if present."""
    result = {
        'filepath': filepath,
        'filename': Path(filepath).name,
        'summary': {},
        'history': [],
    }

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return result

    # Read summary section (first table)
    reader = csv.reader(lines)
    header = None
    summary_row = None
    in_history = False
    history_header = None

    for row in reader:
        if not row:
            continue
        first_val = row[0].strip()

        if first_val.startswith('# Detailed Window History'):
            in_history = True
            continue

        if not in_history:
            if header is None:
                header = [c.strip() for c in row]
            elif summary_row is None:
                summary_row = [c.strip() for c in row]
                for h, val in zip(header, summary_row):
                    # Try to parse numbers
                    try:
                        if '.' in val:
                            result['summary'][h] = float(val)
                        else:
                            result['summary'][h] = int(val)
                    except ValueError:
                        result['summary'][h] = val
        else:
            if history_header is None:
                history_header = [c.strip() for c in row]
            else:
                entry = {}
                for h, val in zip(history_header, row):
                    try:
                        entry[h] = float(val) if '.' in val else int(val)
                    except ValueError:
                        entry[h] = val
                result['history'].append(entry)

    return result


def generate_html_report(parsed_data: list, output_filename: str):
    """Generate a modern, standalone interactive HTML visual report."""
    reports_json = json.dumps(parsed_data, indent=2)

    html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BRONE — ROS 2 Network Latency Benchmark Report</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --bg-primary: #0a0a12;
            --bg-secondary: #12121f;
            --bg-card: rgba(255, 255, 255, 0.04);
            --border-subtle: rgba(255, 255, 255, 0.08);
            --text-primary: #e8e8f0;
            --text-secondary: #8888a0;
            --accent-blue: #38bdf8;
            --accent-green: #00d4aa;
            --accent-orange: #f59e0b;
            --accent-red: #ef4444;
            --accent-purple: #8b5cf6;
            --radius: 16px;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            padding: 32px 24px;
            max-width: 1280px;
            margin: 0 auto;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-subtle);
            padding-bottom: 24px;
            margin-bottom: 32px;
        }}
        .header-title h1 {{
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(135deg, #fff, #8888a0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header-title p {{
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}
        .badge-distro {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            padding: 6px 12px;
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: 20px;
            color: var(--accent-blue);
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius);
            padding: 20px;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .card-title {{
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
        }}
        .card-topology {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 6px;
            background: rgba(56, 189, 248, 0.1);
            color: var(--accent-blue);
        }}
        .metric-main {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 32px;
            font-weight: 700;
            color: var(--accent-green);
            margin-bottom: 12px;
        }}
        .metric-sub-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            padding-top: 12px;
            border-top: 1px solid var(--border-subtle);
        }}
        .metric-sub-item .label {{
            font-size: 11px;
            color: var(--text-secondary);
        }}
        .metric-sub-item .val {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            font-weight: 600;
            margin-top: 2px;
        }}
        .table-container {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius);
            overflow-x: auto;
            margin-bottom: 32px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }}
        th, td {{
            padding: 14px 18px;
            border-bottom: 1px solid var(--border-subtle);
        }}
        th {{
            background: rgba(255, 255, 255, 0.02);
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
        }}
        td {{ font-family: 'JetBrains Mono', monospace; }}
        tr:last-child td {{ border-bottom: none; }}
        .charts-container {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 32px;
        }}
        .chart-box {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius);
            padding: 20px;
            min-height: 320px;
        }}
        .chart-box h3 {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 16px;
        }}
        .btn-print {{
            padding: 8px 16px;
            border-radius: 8px;
            background: var(--accent-blue);
            color: #000;
            font-weight: 600;
            border: none;
            cursor: pointer;
            font-size: 13px;
            transition: opacity 0.2s;
        }}
        .btn-print:hover {{ opacity: 0.9; }}
        @media (max-width: 900px) {{
            .charts-container {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-title">
            <h1>🚀 BRONE Network Latency Benchmark Report</h1>
            <p>Laporan Pengujian Komunikasi DDS Terdistribusi (CycloneDDS Unicast)</p>
        </div>
        <div style="display: flex; gap: 12px; align-items: center;">
            <span class="badge-distro">NUC=Jazzy ↔ Jetson=Humble</span>
            <button class="btn-print" onclick="window.print()">🖨️ Cetak / Simpan PDF</button>
        </div>
    </header>

    <div class="section-title">📊 Rangkuman Sesi Pengujian</div>
    <div class="summary-grid" id="summaryCards"></div>

    <div class="section-title">📋 Tabel Metrik Lengkap</div>
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Topologi</th>
                    <th>Frekuensi (Hz)</th>
                    <th>Payload (B)</th>
                    <th>QoS</th>
                    <th>Avg Lat (ms)</th>
                    <th>p95 Lat (ms)</th>
                    <th>p99 Lat (ms)</th>
                    <th>Min / Max (ms)</th>
                    <th>Total Sampel</th>
                    <th>Miss Rate (%)</th>
                </tr>
            </thead>
            <tbody id="summaryTableBody"></tbody>
        </table>
    </div>

    <div class="section-title">📈 Visualisasi Performa</div>
    <div class="charts-container">
        <div class="chart-box">
            <h3>Perbandingan Latensi Rata-rata vs p95 vs p99 (ms)</h3>
            <canvas id="chartLatencyComparison"></canvas>
        </div>
        <div class="chart-box">
            <h3>Stabilitas Frekuensi (Hz) & Miss Rate (%)</h3>
            <canvas id="chartHzComparison"></canvas>
        </div>
    </div>

    <div class="chart-box" id="timeSeriesBox" style="display: none; margin-bottom: 32px;">
        <h3>Rekaman Riwayat Latensi per Detik (Time Series History)</h3>
        <canvas id="chartTimeSeries" style="max-height: 280px;"></canvas>
    </div>

    <script>
        const data = {reports_json};

        // Render Summary Cards & Table
        const cardsContainer = document.getElementById('summaryCards');
        const tableBody = document.getElementById('summaryTableBody');

        const topLabels = [];
        const avgLats = [];
        const p95Lats = [];
        const p99Lats = [];
        const freqs = [];
        const missRates = [];

        data.forEach((item, idx) => {{
            const s = item.summary;
            const top = s.topology || 'unknown';
            const avg = typeof s.avg_lat_ms === 'number' ? s.avg_lat_ms.toFixed(3) : (s.avg_lat_ms || '-');
            const p95 = typeof s.p95_lat_ms === 'number' ? s.p95_lat_ms.toFixed(3) : (s.p95_lat_ms || '-');
            const p99 = typeof s.p99_lat_ms === 'number' ? s.p99_lat_ms.toFixed(3) : (s.p99_lat_ms || '-');
            const min = typeof s.min_lat_ms === 'number' ? s.min_lat_ms.toFixed(3) : (s.min_lat_ms || '-');
            const max = typeof s.max_lat_ms === 'number' ? s.max_lat_ms.toFixed(3) : (s.max_lat_ms || '-');
            const hz  = typeof s.freq_hz === 'number' ? s.freq_hz.toFixed(1) : (s.freq_hz || '-');
            const miss = typeof s.miss_rate_percent === 'number' ? s.miss_rate_percent.toFixed(2) : (s.miss_rate_percent || '0.00');
            const total = s.total_samples || s.total || 0;

            topLabels.push(`${{top}} (${{s.freq_hz || 50}}Hz)`);
            avgLats.push(s.avg_lat_ms || 0);
            p95Lats.push(s.p95_lat_ms || 0);
            p99Lats.push(s.p99_lat_ms || 0);
            freqs.push(s.freq_hz || 0);
            missRates.push(s.miss_rate_percent || 0);

            // Card
            const card = document.createElement('div');
            card.className = 'card';
            card.innerHTML = `
                <div class="card-header">
                    <span class="card-title">Latency Summary</span>
                    <span class="card-topology">${{top}}</span>
                </div>
                <div class="metric-main">${{avg}} <span style="font-size: 16px; font-weight: normal; color: var(--text-secondary);">ms</span></div>
                <div class="metric-sub-grid">
                    <div class="metric-sub-item"><div class="label">p95 Latency</div><div class="val" style="color: var(--accent-orange);">${{p95}} ms</div></div>
                    <div class="metric-sub-item"><div class="label">p99 Latency</div><div class="val" style="color: var(--accent-red);">${{p99}} ms</div></div>
                    <div class="metric-sub-item"><div class="label">Miss Rate</div><div class="val">${{miss}}%</div></div>
                </div>
            `;
            cardsContainer.appendChild(card);

            // Table Row
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong style="color: var(--accent-blue);">${{top}}</strong></td>
                <td>${{hz}}</td>
                <td>${{s.payload_size_bytes || 128}}</td>
                <td>${{s.qos_profile || 'best_effort'}}</td>
                <td style="color: var(--accent-green); font-weight: 600;">${{avg}}</td>
                <td style="color: var(--accent-orange);">${{p95}}</td>
                <td style="color: var(--accent-red);">${{p99}}</td>
                <td>${{min}} / ${{max}}</td>
                <td>${{total.toLocaleString()}}</td>
                <td>${{miss}}%</td>
            `;
            tableBody.appendChild(tr);
        }});

        // Chart 1: Latency Comparison
        new Chart(document.getElementById('chartLatencyComparison'), {{
            type: 'bar',
            data: {{
                labels: topLabels,
                datasets: [
                    {{ label: 'Avg Latency (ms)', data: avgLats, backgroundColor: '#00d4aa' }},
                    {{ label: 'p95 Latency (ms)', data: p95Lats, backgroundColor: '#f59e0b' }},
                    {{ label: 'p99 Latency (ms)', data: p99Lats, backgroundColor: '#ef4444' }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{ beginAtZero: true, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                    x: {{ grid: {{ display: false }} }}
                }}
            }}
        }});

        // Chart 2: Hz and Miss Rate
        new Chart(document.getElementById('chartHzComparison'), {{
            type: 'bar',
            data: {{
                labels: topLabels,
                datasets: [
                    {{ label: 'Frekuensi (Hz)', data: freqs, backgroundColor: '#38bdf8', yAxisID: 'y' }},
                    {{ label: 'Miss Rate (%)', data: missRates, backgroundColor: '#ef4444', yAxisID: 'y1' }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{ type: 'linear', position: 'left', beginAtZero: true, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                    y1: {{ type: 'linear', position: 'right', beginAtZero: true, max: 10, grid: {{ display: false }} }}
                }}
            }}
        }});

        // Check if there is detailed history in any report
        const firstWithHistory = data.find(d => d.history && d.history.length > 0);
        if (firstWithHistory) {{
            document.getElementById('timeSeriesBox').style.display = 'block';
            const h = firstWithHistory.history;
            const labels = h.map((_, i) => `${{i+1}}s`);
            const hAvg = h.map(x => x.avg_lat_ms || x.avg_lat || 0);
            const hP95 = h.map(x => x.p95_lat_ms || x.p95_lat || 0);
            const hP99 = h.map(x => x.p99_lat_ms || x.p99_lat || 0);

            new Chart(document.getElementById('chartTimeSeries'), {{
                type: 'line',
                data: {{
                    labels: labels,
                    datasets: [
                        {{ label: 'Avg Latency (ms)', data: hAvg, borderColor: '#00d4aa', tension: 0.2 }},
                        {{ label: 'p95 Latency (ms)', data: hP95, borderColor: '#f59e0b', tension: 0.2 }},
                        {{ label: 'p99 Latency (ms)', data: hP99, borderColor: '#ef4444', tension: 0.2 }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{ beginAtZero: true, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                        x: {{ grid: {{ color: 'rgba(255,255,255,0.02)' }} }}
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>
"""

    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)


def generate_matplotlib_png(parsed_data: list, output_png: str):
    """Generate high-res PNG plots using matplotlib if installed."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("[INFO] matplotlib belum terinstall. Lewati pembuatan file PNG.")
        return False

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor('#0f0f17')
    for ax in (ax1, ax2):
        ax.set_facecolor('#161624')
        ax.tick_params(colors='#e8e8f0')
        ax.xaxis.label.set_color('#e8e8f0')
        ax.yaxis.label.set_color('#e8e8f0')
        ax.title.set_color('#e8e8f0')
        for spine in ax.spines.values():
            spine.set_color('#33334d')

    top_labels = []
    avg_lats = []
    p95_lats = []
    p99_lats = []
    freqs = []

    for item in parsed_data:
        s = item['summary']
        top = s.get('topology', 'unknown')
        hz = s.get('freq_hz', 50)
        top_labels.append(f"{top}\n({hz}Hz)")
        avg_lats.append(s.get('avg_lat_ms', 0.0))
        p95_lats.append(s.get('p95_lat_ms', 0.0))
        p99_lats.append(s.get('p99_lat_ms', 0.0))
        freqs.append(s.get('freq_hz', 0.0))

    x = range(len(top_labels))
    width = 0.25

    # Subplot 1: Latency Metrics
    ax1.bar([i - width for i in x], avg_lats, width=width, label='Avg Latency', color='#00d4aa')
    ax1.bar(x, p95_lats, width=width, label='p95 Latency', color='#f59e0b')
    ax1.bar([i + width for i in x], p99_lats, width=width, label='p99 Latency', color='#ef4444')
    ax1.set_ylabel('Latency (ms)')
    ax1.set_title('Perbandingan Latensi Antar Skenario (ms)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(top_labels)
    ax1.legend(facecolor='#161624', edgecolor='#33334d', labelcolor='#e8e8f0')
    ax1.grid(True, color='#252538', linestyle='--', alpha=0.5)

    # Subplot 2: Frequency Stability
    ax2.bar(x, freqs, width=0.4, label='Measured Hz', color='#38bdf8')
    ax2.axhline(50, color='#f59e0b', linestyle='--', label='Target 50 Hz')
    ax2.set_ylabel('Frekuensi (Hz)')
    ax2.set_title('Stabilitas Frekuensi Komunikasi (Hz)')
    ax2.set_xticks(x)
    ax2.set_xticklabels(top_labels)
    ax2.legend(facecolor='#161624', edgecolor='#33334d', labelcolor='#e8e8f0')
    ax2.grid(True, color='#252538', linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_png, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    return True


def main():
    args = sys.argv[1:]

    # If no files specified, search for all brone_log_*.csv in current dir
    if not args:
        csv_files = sorted(glob.glob("brone_log_*.csv"))
        if not csv_files:
            print("❌ Tidak ditemukan file 'brone_log_*.csv' di direktori saat ini.")
            print("Penggunaan: python3 plot_report.py <nama_file.csv>")
            sys.exit(1)
        print(f"🔍 Ditemukan {len(csv_files)} file CSV log.")
    else:
        csv_files = []
        for a in args:
            matches = glob.glob(a)
            if matches:
                csv_files.extend(matches)
            elif os.path.exists(a):
                csv_files.append(a)

    if not csv_files:
        print("❌ File CSV yang dicari tidak ditemukan.")
        sys.exit(1)

    parsed_reports = []
    for f in csv_files:
        p = parse_brone_csv(f)
        if p['summary']:
            parsed_reports.append(p)
            print(f"  ✓ Membaca log: {Path(f).name} (Topology: {p['summary'].get('topology')})")

    if not parsed_reports:
        print("❌ Tidak ada data valid di file CSV yang dibaca.")
        sys.exit(1)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_html = f"brone_report_{timestamp}.html"
    output_png = f"brone_report_{timestamp}.png"

    # 1. Generate HTML report
    generate_html_report(parsed_reports, output_html)
    print(f"\n✅ Laporan HTML Interaktif berhasil dibuat:")
    print(f"   👉 {output_html}")

    # 2. Generate Matplotlib PNG if installed
    if generate_matplotlib_png(parsed_reports, output_png):
        print(f"✅ Grafik PNG Resolusi Tinggi berhasil dibuat:")
        print(f"   👉 {output_png}")

    print("\n💡 Kamu bisa membuka file HTML tersebut di browser apa pun untuk melihat grafik interaktif dan langsung menyimpannya sebagai PDF (Ctrl+P / Print to PDF)!")


if __name__ == '__main__':
    main()
