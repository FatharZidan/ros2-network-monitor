#!/usr/bin/env python3
"""
network_monitor.py — ROS 2 Network Performance Monitor

Subscribe ke /test_topic, mengekstrak timestamp dari payload,
lalu setiap 1 detik mencetak statistik:
  • Frekuensi aktual (Hz)
  • Total pesan diterima pada jendela tersebut
  • Rata-rata Latency (ms)
  • Min / Max Latency (ms)

Penggunaan:
    ros2 run <package_name> network_monitor
    — atau —
    python3 network_monitor.py
"""

import time
import json
import statistics
from typing import List

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class NetworkMonitor(Node):
    """Node subscriber yang mengukur frekuensi & latency dari /test_topic."""

    TOPIC_NAME: str = "/test_topic"
    QOS_DEPTH: int = 10
    REPORT_INTERVAL_SEC: float = 1.0   # Interval laporan statistik

    def __init__(self) -> None:
        super().__init__("network_monitor")

        # --- Parameter ROS 2 ---
        self.declare_parameter("topic_name", self.TOPIC_NAME)
        self.declare_parameter("report_interval", self.REPORT_INTERVAL_SEC)

        topic_name: str = (
            self.get_parameter("topic_name").get_parameter_value().string_value
        )
        self._report_interval: float = (
            self.get_parameter("report_interval").get_parameter_value().double_value
        )

        # --- Akumulator statistik per jendela ---
        self._latencies: List[float] = []      # Latency (ms) per pesan
        self._msg_count: int = 0                # Jumlah pesan diterima
        self._window_start: float = time.time() # Awal jendela pengukuran
        self._total_received: int = 0           # Kumulatif total pesan
        self._negative_count: int = 0           # Deteksi clock skew
        self._clock_skew_warned: bool = False   # Sudah pernah warn?

        # --- Subscriber ---
        self.subscription_ = self.create_subscription(
            String,
            topic_name,
            self._listener_callback,
            self.QOS_DEPTH,
        )

        # --- Timer laporan periodik ---
        self.report_timer_ = self.create_timer(
            self._report_interval, self._report_callback
        )

        self.get_logger().info(
            f"[NetworkMonitor] AKTIF — Topik: {topic_name} "
            f"| Interval laporan: {self._report_interval:.1f} s"
        )

    # ------------------------------------------------------------------ #
    #  Callback: setiap pesan masuk                                       #
    # ------------------------------------------------------------------ #
    def _listener_callback(self, msg: String) -> None:
        """Terima pesan, hitung latency, dan simpan ke akumulator."""
        t_recv: float = time.time()  # Waktu penerimaan

        try:
            payload: dict = json.loads(msg.data)
            t_send: float = payload["stamp"]
        except (json.JSONDecodeError, KeyError) as exc:
            self.get_logger().warn(
                f"[MONITOR] Payload tidak valid, diabaikan: {exc}"
            )
            return

        latency_ms: float = (t_recv - t_send) * 1000.0  # detik → milidetik

        # --- Deteksi clock skew (latency negatif = jam tidak sinkron) ---
        if latency_ms < 0.0:
            self._negative_count += 1
            if not self._clock_skew_warned:
                self.get_logger().warn(
                    "⚠ CLOCK SKEW TERDETEKSI! Latency negatif ditemukan. "
                    "Jam antar mesin TIDAK sinkron. "
                    "Jalankan: sudo ntpdate pool.ntp.org ATAU setup chrony. "
                    "Nilai latency TIDAK DAPAT DIPERCAYA sampai clock sync!"
                )
                self._clock_skew_warned = True

        self._latencies.append(latency_ms)
        self._msg_count += 1
        self._total_received += 1

    # ------------------------------------------------------------------ #
    #  Callback: laporan statistik periodik                               #
    # ------------------------------------------------------------------ #
    def _report_callback(self) -> None:
        """Cetak statistik frekuensi & latency setiap interval."""
        now: float = time.time()
        elapsed: float = now - self._window_start

        if elapsed <= 0.0:
            return

        count: int = self._msg_count
        hz: float = count / elapsed if elapsed > 0 else 0.0

        # --- Hitung statistik latency ---
        if self._latencies:
            avg_lat: float = statistics.mean(self._latencies)
            min_lat: float = min(self._latencies)
            max_lat: float = max(self._latencies)
            std_lat: float = (
                statistics.stdev(self._latencies) if len(self._latencies) > 1 else 0.0
            )
        else:
            avg_lat = min_lat = max_lat = std_lat = 0.0

        # --- Cetak laporan ---
        separator = "─" * 60
        self.get_logger().info(separator)
        self.get_logger().info(
            f"  Frekuensi  : {hz:>8.2f} Hz   "
            f"({count} pesan / {elapsed:.3f} s)"
        )
        self.get_logger().info(
            f"  Latency    : "
            f"avg={avg_lat:>7.3f} ms  "
            f"min={min_lat:>7.3f} ms  "
            f"max={max_lat:>7.3f} ms  "
            f"std={std_lat:>7.3f} ms"
        )
        self.get_logger().info(
            f"  Kumulatif  : {self._total_received} pesan total diterima"
        )
        # --- Peringatan clock skew jika ada latency negatif ---
        if self._negative_count > 0:
            self.get_logger().warn(
                f"  ⚠ CLOCK SKEW : {self._negative_count} pesan dengan "
                f"latency negatif! Sinkronkan jam mesin (chrony/NTP)."
            )
        self.get_logger().info(separator)

        # --- Reset jendela ---
        self._latencies.clear()
        self._msg_count = 0
        self._negative_count = 0
        self._window_start = now


# ====================================================================== #
#  Entry‐point                                                            #
# ====================================================================== #
def main(args=None) -> None:
    rclpy.init(args=args)
    node = NetworkMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info(
            f"[NetworkMonitor] Dihentikan. "
            f"Total pesan diterima: {node._total_received}"
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
