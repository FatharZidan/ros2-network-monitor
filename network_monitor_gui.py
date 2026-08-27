"""
ROS 2 Network Monitor with Web Dashboard for BRONE robot project.
"""

import csv
import io
import struct
import time
import json
import statistics
import threading
from datetime import datetime
from typing import List, Dict, Any
from collections import deque
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from std_msgs.msg import UInt8MultiArray


def get_timestamp_ns(topology: str):
    """Return the appropriate timestamp function based on topology."""
    if topology in ('nuc2nuc', 'jetson2jetson'):
        return time.perf_counter_ns
    elif topology in ('nuc2jetson', 'jetson2nuc'):
        return time.time_ns
    else:
        raise ValueError(f"Topology tidak valid: {topology}")


def calculate_percentile(data: list, p: float) -> float:
    """Calculate percentile without external libraries."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    index = (p / 100) * (n - 1)
    lower = int(index)
    upper = min(lower + 1, n - 1)
    fraction = index - lower
    return sorted_data[lower] + fraction * (sorted_data[upper] - sorted_data[lower])


class MonitorNode(Node):
    def __init__(self):
        super().__init__('network_monitor_gui')
        
        # ROS parameters
        self.declare_parameter('topic_name', '/test_topic')
        self.declare_parameter('report_interval', 1.0)
        self.declare_parameter('http_port', 8765)
        self.declare_parameter('topology', 'nuc2nuc')
        self.declare_parameter('qos', 'best_effort')
        
        topic_name = self.get_parameter('topic_name').value
        report_interval = self.get_parameter('report_interval').value
        self.http_port = self.get_parameter('http_port').value
        topology = self.get_parameter('topology').value
        
        self._ts_func = get_timestamp_ns(topology)
        
        self._latencies: List[float] = []
        self._msg_count = 0
        self._window_start = time.time()
        self._total_received = 0
        self._negative_count = 0
        self._clock_skew_warned = False
        self._cuda_active = False
        self._last_latency = 0.0
        self._first_seq = -1
        self._last_seq = -1
        self._total_gaps = 0
        self._all_latencies: List[float] = []
        self._last_payload_size = 128
        
        self._lock = threading.Lock()
        
        self._current_stats = {
            'hz': 0.0,
            'count': 0,
            'avg_lat': 0.0,
            'min_lat': 0.0,
            'max_lat': 0.0,
            'std_lat': 0.0,
            'total': 0,
            'clock_skew': False,
            'negative_count': 0,
            'elapsed': 0.0,
            'timestamp': time.time(),
            'cuda_active': False,
            'p95_lat': 0.0,
            'p99_lat': 0.0,
            'miss_rate_percent': 0.0,
            'last_latency': 0.0,
            'total_gaps': 0,
        }
        
        self._history = deque(maxlen=120)
        
        qos_str = self.get_parameter('qos').value
        qos_map = {
            'best_effort': QoSReliabilityPolicy.BEST_EFFORT,
            'reliable': QoSReliabilityPolicy.RELIABLE,
        }
        qos_profile = QoSProfile(
            reliability=qos_map.get(qos_str, QoSReliabilityPolicy.BEST_EFFORT),
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
        )
        
        self.create_subscription(UInt8MultiArray, topic_name, self._listener_callback, qos_profile)
        self.create_timer(report_interval, self._report_callback)

    def _listener_callback(self, msg):
        raw = bytes(msg.data)
        if len(raw) < 16:
            self.get_logger().warn('Received message too short')
            return
            
        seq, ts_ns = struct.unpack('!Qq', raw[:16])
        recv_ns = self._ts_func()
        latency_ms = (recv_ns - ts_ns) / 1_000_000.0
        
        self._last_latency = latency_ms
        
        if latency_ms < 0:
            self._negative_count += 1
            if not self._clock_skew_warned:
                self.get_logger().warn('Negative latency detected, potential clock skew')
                self._clock_skew_warned = True
                
        if self._first_seq == -1:
            self._first_seq = seq
            self._last_seq = seq
        else:
            if seq > self._last_seq + 1:
                self._total_gaps += seq - self._last_seq - 1
            self._last_seq = seq
            
        self._latencies.append(latency_ms)
        self._all_latencies.append(latency_ms)
        self._last_payload_size = len(raw)
        self._msg_count += 1
        self._total_received += 1

    def _report_callback(self):
        now = time.time()
        elapsed = now - self._window_start
        
        count = self._msg_count
        latencies = self._latencies
        
        if count > 0 and elapsed > 0:
            hz = count / elapsed
            avg_lat = statistics.mean(latencies)
            min_lat = min(latencies)
            max_lat = max(latencies)
            std_lat = statistics.stdev(latencies) if count > 1 else 0.0
            p95 = calculate_percentile(latencies, 95.0)
            p99 = calculate_percentile(latencies, 99.0)
        else:
            hz = 0.0
            avg_lat = 0.0
            min_lat = 0.0
            max_lat = 0.0
            std_lat = 0.0
            p95 = 0.0
            p99 = 0.0
            
        if self._first_seq >= 0:
            total_expected = self._last_seq - self._first_seq + 1
            if total_expected > 0:
                miss_rate = (self._total_gaps / total_expected) * 100.0
            else:
                miss_rate = 0.0
        else:
            miss_rate = 0.0
            
        stats = {
            'hz': round(hz, 2),
            'count': count,
            'avg_lat': round(avg_lat, 3),
            'min_lat': round(min_lat, 3),
            'max_lat': round(max_lat, 3),
            'std_lat': round(std_lat, 3),
            'total': self._total_received,
            'clock_skew': self._negative_count > 0,
            'negative_count': self._negative_count,
            'elapsed': round(elapsed, 3),
            'timestamp': round(now, 3),
            'cuda_active': self._cuda_active,
            'p95_lat': round(p95, 3),
            'p99_lat': round(p99, 3),
            'miss_rate_percent': round(miss_rate, 2),
            'last_latency': round(self._last_latency, 3),
            'total_gaps': self._total_gaps,
        }
        
        with self._lock:
            self._current_stats = stats
            self._history.append(stats)
            
        self.get_logger().info(
            f"Hz: {stats['hz']} | Avg: {stats['avg_lat']}ms | "
            f"P95: {stats['p95_lat']}ms | Gaps: {stats['total_gaps']} | "
            f"Miss: {stats['miss_rate_percent']}%"
        )
        
        self._latencies.clear()
        self._msg_count = 0
        self._negative_count = 0
        self._window_start = now

    def get_api_data(self):
        with self._lock:
            return {
                'current': self._current_stats,
                'history': list(self._history),
            }

    def generate_csv(self):
        with self._lock:
            ts_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            iso_ts = datetime.now().isoformat()
            topology = self.get_parameter('topology').value
            qos_str = self.get_parameter('qos').value
            
            total_samples = len(self._all_latencies)
            total_expected = (self._last_seq - self._first_seq + 1) if self._first_seq != -1 else 0
            total_gaps = self._total_gaps
            miss_rate = (total_gaps / total_expected * 100.0) if total_expected > 0 else 0.0
            
            if self._all_latencies:
                avg_lat = sum(self._all_latencies) / len(self._all_latencies)
                min_lat = min(self._all_latencies)
                max_lat = max(self._all_latencies)
                p95_lat = calculate_percentile(self._all_latencies, 95.0)
                p99_lat = calculate_percentile(self._all_latencies, 99.0)
            else:
                avg_lat = min_lat = max_lat = p95_lat = p99_lat = 0.0
                
            freq_hz = self._current_stats.get('hz', 0.0)
            if freq_hz == 0.0 and self._history:
                hz_list = [h['hz'] for h in self._history if h.get('hz', 0) > 0]
                if hz_list:
                    freq_hz = round(sum(hz_list) / len(hz_list), 1)
            
            header = [
                "session_timestamp", "topology", "freq_hz", "payload_size_bytes", "qos_profile",
                "ros2_distro_note", "total_samples", "total_expected", "total_gaps",
                "miss_rate_percent", "avg_lat_ms", "min_lat_ms", "max_lat_ms", "p95_lat_ms", "p99_lat_ms"
            ]
            row = [
                iso_ts, topology, freq_hz, self._last_payload_size, qos_str,
                "NUC=Jazzy_Jetson=Humble", total_samples, total_expected, total_gaps,
                round(miss_rate, 2), round(avg_lat, 3), round(min_lat, 3), round(max_lat, 3), round(p95_lat, 3), round(p99_lat, 3)
            ]
            
            filename = f"brone_log_{topology}_{int(freq_hz)}hz_{self._last_payload_size}b_{qos_str}_{ts_str}.csv"
            
            output = io.StringIO()
            output.write("sep=,\n")
            writer = csv.writer(output)
            writer.writerow(header)
            writer.writerow(row)
            
            if self._history:
                output.write("\n# Detailed Window History (1s Interval)\n")
                hist_header = ["timestamp_iso", "hz", "samples_in_window", "avg_lat_ms", "min_lat_ms", "max_lat_ms", "p95_lat_ms", "p99_lat_ms", "miss_rate_pct", "total_accumulated"]
                writer.writerow(hist_header)
                for h in self._history:
                    h_ts = datetime.fromtimestamp(h['timestamp']).isoformat()
                    writer.writerow([
                        h_ts, h.get('hz', 0), h.get('count', 0), h.get('avg_lat', 0), h.get('min_lat', 0),
                        h.get('max_lat', 0), h.get('p95_lat', 0), h.get('p99_lat', 0), h.get('miss_rate_percent', 0), h.get('total', 0)
                    ])
                    
            return filename, output.getvalue()


    def generate_html_report(self):
        """Generate a complete standalone interactive Light-Mode HTML report with charts and event markers."""
        with self._lock:
            ts_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            iso_ts = datetime.now().isoformat()
            topology = self.get_parameter('topology').value
            qos_str = self.get_parameter('qos').value
            
            total_samples = len(self._all_latencies)
            total_expected = (self._last_seq - self._first_seq + 1) if self._first_seq != -1 else 0
            total_gaps = self._total_gaps
            miss_rate = (total_gaps / total_expected * 100.0) if total_expected > 0 else 0.0
            
            if self._all_latencies:
                avg_lat = sum(self._all_latencies) / len(self._all_latencies)
                min_lat = min(self._all_latencies)
                max_lat = max(self._all_latencies)
                p95_lat = calculate_percentile(self._all_latencies, 95.0)
                p99_lat = calculate_percentile(self._all_latencies, 99.0)
            else:
                avg_lat = min_lat = max_lat = p95_lat = p99_lat = 0.0
                
            freq_hz = self._current_stats.get('hz', 0.0)
            if freq_hz == 0.0 and self._history:
                hz_list = [h['hz'] for h in self._history if h.get('hz', 0) > 0]
                if hz_list:
                    freq_hz = round(sum(hz_list) / len(hz_list), 1)
                    
            history_list = list(self._history)
            events_list = list(self._events)
            
            report_data = {
                'filename': f"brone_log_{topology}_{int(freq_hz)}hz_{self._last_payload_size}b_{qos_str}_{ts_str}.csv",
                'metadata': {
                    'Session Timestamp': iso_ts,
                    'Topology': topology,
                    'Target Frequency': f"{freq_hz} Hz",
                    'Payload Size': f"{self._last_payload_size} Bytes",
                    'QoS Profile': qos_str
                },
                'summary': {
                    'avg_lat_ms': round(avg_lat, 3),
                    'p95_lat_ms': round(p95_lat, 3),
                    'p99_lat_ms': round(p99_lat, 3),
                    'min_lat_ms': round(min_lat, 3),
                    'max_lat_ms': round(max_lat, 3),
                    'avg_hz': freq_hz,
                    'total_samples': total_samples,
                    'total_gaps': total_gaps,
                    'duration_sec': len(history_list),
                },
                'history': history_list,
                'events': events_list
            }
            
            report_json = json.dumps(report_data, indent=2)
            filename = f"brone_report_{topology}_{int(freq_hz)}hz_{ts_str}.html"
            
            html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BRONE — Laporan Uji Latensi ROS 2 ({report_data['filename']})</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --bg-primary: #f8fafc;
            --bg-secondary: #ffffff;
            --border-subtle: #e2e8f0;
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
            --shadow-card: 0 1px 3px 0 rgba(0, 0, 0, 0.04);
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
        <p>File Sumber: <code>{report_data['filename']}</code> • Durasi: {len(history_list)} detik</p>
    </div>
    <button class="btn-print" onclick="window.print()">
        <span>🖨️ Cetak / Simpan PDF</span>
    </button>
</header>

<div class="metrics-grid">
    <div class="metric-card">
        <div class="metric-label">Avg Latency</div>
        <div class="metric-val">{avg_lat:.2f} <span class="metric-unit">ms</span></div>
    </div>
    <div class="metric-card">
        <div class="metric-label">p95 Latency</div>
        <div class="metric-val" style="color: var(--accent-amber);">{p95_lat:.2f} <span class="metric-unit">ms</span></div>
    </div>
    <div class="metric-card">
        <div class="metric-label">p99 Latency (Tail)</div>
        <div class="metric-val" style="color: var(--accent-red);">{p99_lat:.2f} <span class="metric-unit">ms</span></div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Throughput Rata-rata</div>
        <div class="metric-val" style="color: var(--accent-teal);">{freq_hz:.1f} <span class="metric-unit">Hz</span></div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Total Sampel</div>
        <div class="metric-val">{total_samples:,} <span class="metric-unit">pesan</span></div>
    </div>
    <div class="metric-card">
        <div class="metric-label">Total Paket Drop</div>
        <div class="metric-val" style="color: { 'var(--accent-red)' if total_gaps > 0 else 'var(--text-primary)' };">{total_gaps} <span class="metric-unit">gaps</span></div>
    </div>
</div>

{ f'''<div class="event-box">
    <h4>📌 Event / Perintah yang Ditandai Selama Pengujian</h4>
    <div class="event-list">
        {''.join([f'<span class="event-pill">📌 t={e["second"]}s: {e["label"]}</span>' for e in events_list])}
    </div>
</div>''' if events_list else '' }

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
    const reportData = {report_json};
    const history = reportData.history || [];

    const labels = history.map((h, i) => `${{h.elapsed || i + 1}}s`);
    const avgLats = history.map(h => h.avg_lat || 0);
    const minLats = history.map(h => h.min_lat || 0);
    const maxLats = history.map(h => h.max_lat || 0);
    const p95Lats = history.map(h => h.p95_lat || 0);
    const p99Lats = history.map(h => h.p99_lat || 0);
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
            return filename, html_content


_monitor_node = None


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/stats':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            if _monitor_node:
                data = _monitor_node.get_api_data()
            else:
                data = {'current': {}, 'history': [], 'events': []}
                
            self.wfile.write(json.dumps(data).encode('utf-8'))
            
        elif self.path.startswith('/api/export-csv'):
            if _monitor_node:
                filename, csv_content = _monitor_node.generate_csv()
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.end_headers()
                self.wfile.write(csv_content.encode('utf-8'))
            else:
                self.send_response(503)
                self.end_headers()
                
        elif self.path.startswith('/api/export-report'):
            if _monitor_node:
                filename, html_content = _monitor_node.generate_html_report()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.end_headers()
                self.wfile.write(html_content.encode('utf-8'))
            else:
                self.send_response(503)
                self.end_headers()
                
        elif self.path == '/':
            self.path = '/dashboard.html'
            super().do_GET()
        else:
            super().do_GET()

            
    def log_message(self, format, *args):
        # Suppress access logs
        pass


def main(args=None):
    global _monitor_node
    rclpy.init(args=args)
    
    _monitor_node = MonitorNode()
    
    ros_thread = threading.Thread(target=rclpy.spin, args=(_monitor_node,), daemon=True)
    ros_thread.start()
    
    server_address = ('0.0.0.0', _monitor_node.http_port)
    httpd = ThreadedHTTPServer(server_address, DashboardHandler)
    
    _monitor_node.get_logger().info(f"Serving HTTP on 0.0.0.0 port {_monitor_node.http_port} ...")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        try:
            _monitor_node.destroy_node()
        except Exception:
            pass
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
