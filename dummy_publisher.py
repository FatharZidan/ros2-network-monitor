#!/usr/bin/env python3
"""
dummy_publisher.py — ROS 2 Mock/Dummy Publisher (Bagian TDD)

Mempublikasikan pesan ke /test_topic pada frekuensi presisi tinggi (50 Hz).
Setiap pesan berisi timestamp epoch (time.time()) agar node monitor
dapat menghitung latency secara akurat.

Penggunaan:
    ros2 run <package_name> dummy_publisher
    — atau —
    python3 dummy_publisher.py
"""

import time
import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class DummyPublisher(Node):
    """Node publisher yang mengirim pesan berisi timestamp ke /test_topic."""

    # ------------------------------------------------------------------ #
    #  Konstanta default — mudah diubah untuk eksperimen frekuensi lain   #
    # ------------------------------------------------------------------ #
    TARGET_HZ: float = 50.0          # Frekuensi target (Hz)
    TOPIC_NAME: str = "/test_topic"
    QOS_DEPTH: int = 10

    def __init__(self) -> None:
        super().__init__("dummy_publisher")

        # --- Deklarasi parameter ROS 2 agar bisa di-override saat runtime ---
        self.declare_parameter("target_hz", self.TARGET_HZ)
        self.declare_parameter("topic_name", self.TOPIC_NAME)

        target_hz: float = (
            self.get_parameter("target_hz").get_parameter_value().double_value
        )
        topic_name: str = (
            self.get_parameter("topic_name").get_parameter_value().string_value
        )

        timer_period_sec: float = 1.0 / target_hz

        # --- Publisher & Timer ---
        self.publisher_ = self.create_publisher(String, topic_name, self.QOS_DEPTH)
        self.timer_ = self.create_timer(timer_period_sec, self._timer_callback)

        self._seq: int = 0  # Penghitung sequence number

        self.get_logger().info(
            f"[DummyPublisher] AKTIF — Target: {target_hz:.1f} Hz "
            f"| Periode: {timer_period_sec * 1000:.2f} ms "
            f"| Topik: {topic_name}"
        )

    # ------------------------------------------------------------------ #
    #  Callback                                                           #
    # ------------------------------------------------------------------ #
    def _timer_callback(self) -> None:
        """Kirim pesan JSON berisi timestamp dan sequence number."""
        now: float = time.time()  # epoch timestamp (detik, presisi mikrodetik)

        payload: dict = {
            "seq": self._seq,
            "stamp": now,           # Waktu pengiriman (epoch seconds)
        }

        msg = String()
        msg.data = json.dumps(payload)

        self.publisher_.publish(msg)
        self._seq += 1

        # Log setiap 1 detik agar terminal tidak banjir
        if self._seq % int(self.TARGET_HZ) == 0:
            self.get_logger().info(
                f"[PUB] seq={self._seq}  stamp={now:.6f}"
            )


# ====================================================================== #
#  Entry‐point                                                            #
# ====================================================================== #
def main(args=None) -> None:
    rclpy.init(args=args)
    node = DummyPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("[DummyPublisher] Dihentikan oleh pengguna (Ctrl+C).")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
