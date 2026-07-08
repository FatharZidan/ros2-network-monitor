#!/usr/bin/env python3
"""
dummy_publisher.py — ROS 2 Mock/Dummy Publisher (Bagian TDD)

Mempublikasikan pesan ke /test_topic pada frekuensi presisi tinggi (50 Hz).
Setiap pesan berisi timestamp epoch (time.time()) agar node monitor
dapat menghitung latency secara akurat.

Fitur GPU Stress-Test:
  Jika OpenCV dengan CUDA tersedia (Jetson Orin Nano), node ini akan
  menjalankan beban GPU (upload → cvtColor → download) setiap callback
  SEBELUM pengambilan timestamp. Status CUDA disisipkan ke payload JSON.

Penggunaan:
    ros2 run <package_name> dummy_publisher
    — atau —
    python3 dummy_publisher.py
"""

import time
import json

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# ====================================================================== #
#  Auto-Detect CUDA via OpenCV                                            #
# ====================================================================== #
_CUDA_AVAILABLE: bool = False
_cv2 = None

try:
    import cv2 as _cv2
    if hasattr(_cv2, 'cuda') and _cv2.cuda.getCudaEnabledDeviceCount() > 0:
        _CUDA_AVAILABLE = True
except ImportError:
    _cv2 = None
except Exception:
    # cv2 ada tapi CUDA runtime gagal (misal: driver error)
    _CUDA_AVAILABLE = False


class DummyPublisher(Node):
    """Node publisher yang mengirim pesan berisi timestamp ke /test_topic."""

    # ------------------------------------------------------------------ #
    #  Konstanta default — mudah diubah untuk eksperimen frekuensi lain   #
    # ------------------------------------------------------------------ #
    TARGET_HZ: float = 50.0          # Frekuensi target (Hz)
    TOPIC_NAME: str = "/test_topic"
    QOS_DEPTH: int = 10
    GPU_IMG_H: int = 1080             # Resolusi matriks dummy (1080p)
    GPU_IMG_W: int = 1920

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

        # --- Inisialisasi GPU workload (jika CUDA tersedia) ---
        self._cuda_active: bool = _CUDA_AVAILABLE
        self._gpu_mat = None
        self._cpu_frame: np.ndarray = None

        if self._cuda_active:
            try:
                # Alokasi matriks dummy 1080p BGR (3 channel) di RAM
                self._cpu_frame = np.random.randint(
                    0, 256,
                    (self.GPU_IMG_H, self.GPU_IMG_W, 3),
                    dtype=np.uint8,
                )
                # Alokasi GpuMat di VRAM
                self._gpu_mat = _cv2.cuda_GpuMat()
                # Warm-up: satu kali upload untuk memastikan CUDA context aktif
                self._gpu_mat.upload(self._cpu_frame)
                self.get_logger().info(
                    f"[GPU] CUDA AKTIF — Device: {_cv2.cuda.getDevice()}, "
                    f"Matriks dummy: {self.GPU_IMG_W}x{self.GPU_IMG_H} BGR"
                )
            except Exception as exc:
                self.get_logger().warn(
                    f"[GPU] CUDA terdeteksi tapi gagal inisialisasi: {exc}. "
                    f"Fallback ke mode CPU."
                )
                self._cuda_active = False
                self._gpu_mat = None
                self._cpu_frame = None
        else:
            self.get_logger().info(
                "[GPU] CUDA tidak tersedia — berjalan dalam mode CPU murni."
            )

        self.get_logger().info(
            f"[DummyPublisher] AKTIF — Target: {target_hz:.1f} Hz "
            f"| Periode: {timer_period_sec * 1000:.2f} ms "
            f"| Topik: {topic_name} "
            f"| CUDA: {'ON' if self._cuda_active else 'OFF'}"
        )

    # ------------------------------------------------------------------ #
    #  GPU Workload: Simulasi beban compute vision                        #
    # ------------------------------------------------------------------ #
    def _run_gpu_workload(self) -> None:
        """Upload → cvtColor(BGR→GRAY) di GPU → Download kembali ke RAM."""
        # Upload: RAM → VRAM
        self._gpu_mat.upload(self._cpu_frame)

        # Eksekusi konversi warna di GPU
        gpu_gray = _cv2.cuda.cvtColor(self._gpu_mat, _cv2.COLOR_BGR2GRAY)

        # Download: VRAM → RAM (hasil dibuang, tujuannya memaksa GPU kerja)
        _ = gpu_gray.download()

    # ------------------------------------------------------------------ #
    #  Callback                                                           #
    # ------------------------------------------------------------------ #
    def _timer_callback(self) -> None:
        """Kirim pesan JSON berisi timestamp dan sequence number."""
        # --- Injeksi beban GPU SEBELUM timestamp (jika CUDA aktif) ---
        if self._cuda_active:
            self._run_gpu_workload()

        now: float = time.time()  # epoch timestamp (detik, presisi mikrodetik)

        payload: dict = {
            "seq": self._seq,
            "stamp": now,           # Waktu pengiriman (epoch seconds)
            "cuda": self._cuda_active,  # Status CUDA untuk dashboard
        }

        msg = String()
        msg.data = json.dumps(payload)

        self.publisher_.publish(msg)
        self._seq += 1

        # Log setiap 1 detik agar terminal tidak banjir
        if self._seq % int(self.TARGET_HZ) == 0:
            self.get_logger().info(
                f"[PUB] seq={self._seq}  stamp={now:.6f}"
                f"  cuda={'ON' if self._cuda_active else 'OFF'}"
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
