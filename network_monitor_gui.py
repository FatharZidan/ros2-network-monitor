#!/usr/bin/env python3
"""
network_monitor_gui.py — ROS 2 Network Monitor dengan Web Dashboard

Subscriber ROS 2 + HTTP server built-in Python.
Buka http://localhost:8080 di browser untuk melihat dashboard real-time.

Fitur:
  • Grafik real-time Hz & Latency (Chart.js)
  • Kartu metrik: Hz, Avg/Min/Max Latency, Jitter, Total Pesan
  • Deteksi otomatis clock skew
  • History 2 menit terakhir
  • Zero extra pip dependencies (hanya rclpy + std_msgs)

Penggunaan:
    python3 network_monitor_gui.py
    → Buka browser: http://localhost:8080

    Ganti port:
    python3 network_monitor_gui.py --ros-args -p http_port:=9090
"""

import os
import sys
import time
import json
import math
import statistics
import threading
from typing import List, Dict, Any
from collections import deque
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


# ====================================================================== #
#  ROS 2 Node: Monitor + Data Aggregator                                  #
# ====================================================================== #
class MonitorNode(Node):
    """Node subscriber yang mengukur frekuensi & latency, menyimpan history."""

    TOPIC_NAME: str = "/test_topic"
    QOS_DEPTH: int = 10
    REPORT_INTERVAL_SEC: float = 1.0
    HISTORY_MAX: int = 120  # Simpan 120 data point (2 menit)

    def __init__(self) -> None:
        super().__init__("network_monitor_gui")

        # --- Parameter ROS 2 ---
        self.declare_parameter("topic_name", self.TOPIC_NAME)
        self.declare_parameter("report_interval", self.REPORT_INTERVAL_SEC)
        self.declare_parameter("http_port", 8080)

        topic_name: str = (
            self.get_parameter("topic_name").get_parameter_value().string_value
        )
        self._report_interval: float = (
            self.get_parameter("report_interval").get_parameter_value().double_value
        )
        self.http_port: int = (
            self.get_parameter("http_port").get_parameter_value().integer_value
        )

        # --- Akumulator statistik per jendela ---
        self._latencies: List[float] = []
        self._msg_count: int = 0
        self._window_start: float = time.time()
        self._total_received: int = 0
        self._negative_count: int = 0
        self._clock_skew_warned: bool = False

        # --- Data terbaru & history (thread-safe via GIL untuk reads) ---
        self._lock = threading.Lock()
        self._current_stats: Dict[str, Any] = {
            "hz": 0.0,
            "count": 0,
            "avg_lat": 0.0,
            "min_lat": 0.0,
            "max_lat": 0.0,
            "std_lat": 0.0,
            "total": 0,
            "clock_skew": False,
            "negative_count": 0,
            "elapsed": 0.0,
            "timestamp": time.time(),
        }
        self._history: deque = deque(maxlen=self.HISTORY_MAX)

        # --- Subscriber ---
        self.subscription_ = self.create_subscription(
            String, topic_name, self._listener_callback, self.QOS_DEPTH
        )

        # --- Timer laporan periodik ---
        self.report_timer_ = self.create_timer(
            self._report_interval, self._report_callback
        )

        self.get_logger().info(
            f"[MonitorGUI] AKTIF — Topik: {topic_name} "
            f"| Dashboard: http://localhost:{self.http_port}"
        )

    # ------------------------------------------------------------------ #
    #  Callback: setiap pesan masuk                                       #
    # ------------------------------------------------------------------ #
    def _listener_callback(self, msg: String) -> None:
        t_recv: float = time.time()
        try:
            payload: dict = json.loads(msg.data)
            t_send: float = payload["stamp"]
        except (json.JSONDecodeError, KeyError) as exc:
            self.get_logger().warn(f"Payload tidak valid: {exc}")
            return

        latency_ms: float = (t_recv - t_send) * 1000.0

        if latency_ms < 0.0:
            self._negative_count += 1
            if not self._clock_skew_warned:
                self.get_logger().warn(
                    "⚠ CLOCK SKEW TERDETEKSI! Sinkronkan jam (chrony/NTP)."
                )
                self._clock_skew_warned = True

        self._latencies.append(latency_ms)
        self._msg_count += 1
        self._total_received += 1

    # ------------------------------------------------------------------ #
    #  Callback: laporan periodik + update data untuk dashboard           #
    # ------------------------------------------------------------------ #
    def _report_callback(self) -> None:
        now: float = time.time()
        elapsed: float = now - self._window_start

        if elapsed <= 0.0:
            return

        count = self._msg_count
        hz = count / elapsed if elapsed > 0 else 0.0

        if self._latencies:
            avg_lat = statistics.mean(self._latencies)
            min_lat = min(self._latencies)
            max_lat = max(self._latencies)
            std_lat = (
                statistics.stdev(self._latencies)
                if len(self._latencies) > 1
                else 0.0
            )
        else:
            avg_lat = min_lat = max_lat = std_lat = 0.0

        stats = {
            "hz": round(hz, 2),
            "count": count,
            "avg_lat": round(avg_lat, 3),
            "min_lat": round(min_lat, 3),
            "max_lat": round(max_lat, 3),
            "std_lat": round(std_lat, 3),
            "total": self._total_received,
            "clock_skew": self._negative_count > 0,
            "negative_count": self._negative_count,
            "elapsed": round(elapsed, 3),
            "timestamp": round(now, 3),
        }

        with self._lock:
            self._current_stats = stats
            self._history.append(stats)

        # Log ke terminal juga
        self.get_logger().info(
            f"Hz={hz:>7.2f}  "
            f"Lat avg={avg_lat:>7.3f} min={min_lat:>7.3f} "
            f"max={max_lat:>7.3f} std={std_lat:>7.3f} ms  "
            f"Total={self._total_received}"
        )

        # Reset jendela
        self._latencies.clear()
        self._msg_count = 0
        self._negative_count = 0
        self._window_start = now

    # ------------------------------------------------------------------ #
    #  API: ambil data untuk HTTP handler                                 #
    # ------------------------------------------------------------------ #
    def get_api_data(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current": self._current_stats,
                "history": list(self._history),
            }


# ====================================================================== #
#  HTTP Server: Dashboard + API                                           #
# ====================================================================== #
# Referensi global ke node (di-set di main)
_monitor_node: MonitorNode = None


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler: serve dashboard.html + JSON API."""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_dashboard()
        elif self.path == "/api/stats":
            self._serve_api()
        else:
            self.send_error(404)

    def _serve_dashboard(self):
        html_path = Path(__file__).parent / "dashboard.html"
        if not html_path.exists():
            self.send_error(500, "dashboard.html tidak ditemukan!")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_path.read_bytes())

    def _serve_api(self):
        global _monitor_node
        data = _monitor_node.get_api_data() if _monitor_node else {}
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # Suppress default access logs (terlalu noisy)
    def log_message(self, format, *args):
        pass


# ====================================================================== #
#  Entry-point                                                            #
# ====================================================================== #
def main(args=None) -> None:
    global _monitor_node

    rclpy.init(args=args)
    _monitor_node = MonitorNode()

    # --- Jalankan rclpy.spin di thread terpisah ---
    ros_thread = threading.Thread(target=rclpy.spin, args=(_monitor_node,), daemon=True)
    ros_thread.start()

    # --- Jalankan HTTP server di main thread (threaded agar tidak freeze) ---
    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    port = _monitor_node.http_port
    server = ThreadedHTTPServer(("0.0.0.0", port), DashboardHandler)
    _monitor_node.get_logger().info(
        f"Dashboard ready → http://localhost:{port}"
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _monitor_node.get_logger().info(
            f"[MonitorGUI] Dihentikan. Total: {_monitor_node._total_received} pesan."
        )
    finally:
        server.shutdown()
        _monitor_node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
