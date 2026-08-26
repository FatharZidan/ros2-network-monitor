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
from std_msgs.msg import UInt8MultiArray, String


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
        self._start_time = time.time()
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
        
        # Event Markers List: [{'second': float, 'label': str, 'timestamp_iso': str}]
        self._events: List[Dict[str, Any]] = []
        self._pending_events_for_window: List[str] = []
        
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
            'events': [],
        }
        
        self._history = deque(maxlen=3600)  # Simpan hingga 1 jam per detik
        
        # QoS Profile setup
        qos_param = self.get_parameter('qos').value
        if qos_param == 'reliable':
            qos_profile = QoSProfile(
                reliability=QoSReliabilityPolicy.RELIABLE,
                history=QoSHistoryPolicy.KEEP_LAST,
                depth=100
            )
        else:
            qos_profile = QoSProfile(
                reliability=QoSReliabilityPolicy.BEST_EFFORT,
                history=QoSHistoryPolicy.KEEP_LAST,
                depth=100
            )
            
        self._sub = self.create_subscription(
            UInt8MultiArray,
            topic_name,
            self._msg_callback,
            qos_profile
        )
        
        # Auto-subscribe to BRONE command & event topics for automatic markers
        self._sub_cmd = self.create_subscription(
            String,
            '/brone/command',
            self._command_callback,
            10
        )
        self._sub_event = self.create_subscription(
            String,
            '/brone/event_marker',
            self._event_marker_callback,
            10
        )
        
        self._timer = self.create_timer(report_interval, self._calculate_stats)
        
        self.get_logger().info(
            f"Monitor GUI Node aktif pada topik: {topic_name} (QoS: {qos_param}, Topologi: {topology})"
        )

    def _command_callback(self, msg: String):
        """Auto-mark when a BRONE command is executed (e.g. init, wave, eyefollow, talk)."""
        cmd_text = msg.data.strip()
        if cmd_text:
            self.add_event_marker(f"CMD: {cmd_text}")
            self.get_logger().info(f"[EVENT MARKER AUTO] Topik /brone/command ➔ {cmd_text}")

    def _event_marker_callback(self, msg: String):
        """Auto-mark when custom event is published on /brone/event_marker."""
        event_text = msg.data.strip()
        if event_text:
            self.add_event_marker(event_text)
            self.get_logger().info(f"[EVENT MARKER AUTO] Topik /brone/event_marker ➔ {event_text}")

    def add_event_marker(self, label: str):
        """Add an event marker at the current elapsed second."""
        now = time.time()
        elapsed = round(now - self._start_time, 2)
        event_entry = {
            'second': elapsed,
            'label': label,
            'timestamp_iso': datetime.now().isoformat(),
        }
        with self._lock:
            self._events.append(event_entry)
            self._pending_events_for_window.append(label)
            self._current_stats['events'] = list(self._events)
        return event_entry

    def _msg_callback(self, msg: UInt8MultiArray):
        t_recv = self._ts_func()
        data_bytes = bytes(msg.data)
        
        if len(data_bytes) < 16:
            self.get_logger().warn(f"Payload terlalu kecil ({len(data_bytes)} bytes), minimal 16 bytes")
            return
            
        seq, t_send = struct.unpack('!Qq', data_bytes[:16])
        
        if len(data_bytes) >= 17:
            self._cuda_active = (data_bytes[16] == 1)
        else:
            self._cuda_active = False
            
        self._last_payload_size = len(data_bytes)
        
        diff_ns = t_recv - t_send
        lat_ms = diff_ns / 1_000_000.0
        
        with self._lock:
            if self._first_seq == -1:
                self._first_seq = seq
                self._last_seq = seq
            else:
                if seq > self._last_seq + 1:
                    gap = seq - (self._last_seq + 1)
                    self._total_gaps += gap
                self._last_seq = seq
                
            self._latencies.append(lat_ms)
            self._all_latencies.append(lat_ms)
            self._msg_count += 1
            self._total_received += 1
            self._last_latency = lat_ms
            
            if lat_ms < 0:
                self._negative_count += 1
                if not self._clock_skew_warned:
                    self._clock_skew_warned = True
                    self.get_logger().error(
                        f"Clock skew terdeteksi: latency = {lat_ms:.2f}ms. "
                        "Sinkronkan jam dengan chrony!"
                    )

    def _calculate_stats(self):
        now = time.time()
        elapsed = now - self._start_time
        window_duration = now - self._window_start
        
        with self._lock:
            latencies = list(self._latencies)
            count = self._msg_count
            event_labels = list(self._pending_events_for_window)
            self._pending_events_for_window.clear()
            
        hz = round(count / window_duration, 1) if window_duration > 0 else 0.0
        
        if latencies:
            avg_lat = statistics.mean(latencies)
            min_lat = min(latencies)
            max_lat = max(latencies)
            std_lat = statistics.stdev(latencies) if len(latencies) > 1 else 0.0
            p95 = calculate_percentile(latencies, 95.0)
            p99 = calculate_percentile(latencies, 99.0)
            jitter = max_lat - min_lat
        else:
            avg_lat = min_lat = max_lat = std_lat = p95 = p99 = jitter = 0.0
            
        total_expected = (self._last_seq - self._first_seq + 1) if self._first_seq != -1 else 0
        miss_rate = (self._total_gaps / total_expected * 100.0) if total_expected > 0 else 0.0
        
        event_str = " | ".join(event_labels) if event_labels else ""
        
        stats = {
            'hz': hz,
            'count': count,
            'avg_lat': round(avg_lat, 3),
            'min_lat': round(min_lat, 3),
            'max_lat': round(max_lat, 3),
            'std_lat': round(std_lat, 3),
            'jitter': round(jitter, 3),
            'total': self._total_received,
            'clock_skew': self._negative_count > 0,
            'negative_count': self._negative_count,
            'elapsed': round(elapsed, 1),
            'timestamp': round(now, 3),
            'cuda_active': self._cuda_active,
            'p95_lat': round(p95, 3),
            'p99_lat': round(p99, 3),
            'miss_rate_percent': round(miss_rate, 2),
            'last_latency': round(self._last_latency, 3),
            'total_gaps': self._total_gaps,
            'event_marker': event_str,
            'events': list(self._events),
        }
        
        with self._lock:
            self._current_stats = stats
            self._history.append(stats)
            
        log_msg = (
            f"Detik: {stats['elapsed']}s | Hz: {stats['hz']} | Avg: {stats['avg_lat']}ms | "
            f"P95: {stats['p95_lat']}ms | P99: {stats['p99_lat']}ms | Gaps: {stats['total_gaps']} | "
            f"Miss: {stats['miss_rate_percent']}%"
        )
        if event_str:
            log_msg += f" | 📌 [EVENT: {event_str}]"
        self.get_logger().info(log_msg)
        
        self._latencies.clear()
        self._msg_count = 0
        self._negative_count = 0
        self._window_start = now

    def get_api_data(self):
        with self._lock:
            return {
                'current': self._current_stats,
                'history': list(self._history),
                'events': list(self._events),
            }

    def generate_csv(self):
        """Generate clean, continuous time-series CSV with event markers."""
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
                overall_jitter = max_lat - min_lat
            else:
                avg_lat = min_lat = max_lat = p95_lat = p99_lat = overall_jitter = 0.0
                
            freq_hz = self._current_stats.get('hz', 0.0)
            if freq_hz == 0.0 and self._history:
                hz_list = [h['hz'] for h in self._history if h.get('hz', 0) > 0]
                if hz_list:
                    freq_hz = round(sum(hz_list) / len(hz_list), 1)
            
            filename = f"brone_log_{topology}_{int(freq_hz)}hz_{self._last_payload_size}b_{qos_str}_{ts_str}.csv"
            
            output = io.StringIO()
            output.write("sep=,\n")
            
            # Clean Metadata Headers (Prefixed with #)
            output.write(f"# BRONE ROS 2 Latency Benchmark Log — Single Session Continuous Time-Series\n")
            output.write(f"# Session Timestamp: {iso_ts}\n")
            output.write(f"# Topology: {topology}\n")
            output.write(f"# Target Frequency: {freq_hz} Hz\n")
            output.write(f"# Payload Size: {self._last_payload_size} Bytes\n")
            output.write(f"# QoS Profile: {qos_str}\n")
            output.write(f"# Overall Summary: Avg={avg_lat:.3f}ms | p95={p95_lat:.3f}ms | p99={p99_lat:.3f}ms | Jitter={overall_jitter:.3f}ms | MissRate={miss_rate:.2f}% | TotalSamples={total_samples}\n")
            output.write(f"#\n")
            
            # Clean Continuous Time-Series Table
            writer = csv.writer(output)
            header = [
                "timestamp_iso", "second", "hz", "avg_lat_ms", "min_lat_ms", "max_lat_ms",
                "p95_lat_ms", "p99_lat_ms", "jitter_ms", "gaps_count", "total_samples", "event_marker"
            ]
            writer.writerow(header)
            
            if self._history:
                for h in self._history:
                    h_ts = datetime.fromtimestamp(h['timestamp']).isoformat()
                    sec = h.get('elapsed', 0)
                    jitter = round(h.get('max_lat', 0) - h.get('min_lat', 0), 3)
                    writer.writerow([
                        h_ts,
                        sec,
                        h.get('hz', 0),
                        h.get('avg_lat', 0),
                        h.get('min_lat', 0),
                        h.get('max_lat', 0),
                        h.get('p95_lat', 0),
                        h.get('p99_lat', 0),
                        jitter,
                        h.get('total_gaps', 0),
                        h.get('total', 0),
                        h.get('event_marker', '')
                    ])
                    
            return filename, output.getvalue()


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
        elif self.path == '/':
            self.path = '/dashboard.html'
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/event':
            content_length = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_length)
            try:
                payload = json.loads(post_body.decode('utf-8'))
                label = payload.get('label', '').strip()
                if label and _monitor_node:
                    event_entry = _monitor_node.add_event_marker(label)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'ok', 'event': event_entry}).encode('utf-8'))
                    return
            except Exception as e:
                pass
            self.send_response(400)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
            
    def log_message(self, format, *args):
        # Suppress access logs
        pass


def run_http_server(port: int, dashboard_dir: str):
    import os
    os.chdir(dashboard_dir)
    server = ThreadedHTTPServer(('0.0.0.0', port), DashboardHandler)
    server.serve_forever()


def main(args=None):
    global _monitor_node
    rclpy.init(args=args)
    
    _monitor_node = MonitorNode()
    
    dashboard_dir = Path(__file__).resolve().parent
    http_thread = threading.Thread(
        target=run_http_server,
        args=(_monitor_node.http_port, str(dashboard_dir)),
        daemon=True
    )
    http_thread.start()
    
    _monitor_node.get_logger().info(
        f"Web Dashboard siap diakses: http://0.0.0.0:{_monitor_node.http_port} "
        f"(atau http://localhost:{_monitor_node.http_port})"
    )
    
    try:
        rclpy.spin(_monitor_node)
    except KeyboardInterrupt:
        pass
    finally:
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
