import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from std_msgs.msg import UInt8MultiArray
import argparse
import struct
import os
import time
import threading
import sys
import array

try:
    import cv2
except ImportError:
    cv2 = None

def get_timestamp_ns(topology: str):
    """Return timestamp function based on topology."""
    if topology in ('nuc2nuc', 'jetson2jetson'):
        return time.perf_counter_ns
    elif topology in ('nuc2jetson', 'jetson2nuc'):
        return time.time_ns
    else:
        raise ValueError(f"Topology tidak valid: {topology}. Pilihan: nuc2nuc, jetson2jetson, nuc2jetson, jetson2nuc")

_last_cpu_idle = 0.0
_last_cpu_total = 0.0


def get_system_health() -> dict:
    """Read Linux system thermal, CPU, and RAM metrics without external dependencies."""
    global _last_cpu_idle, _last_cpu_total
    
    cpu_temp = 0.0
    gpu_temp = 0.0
    cpu_pct = 0.0
    ram_used_mb = 0.0
    ram_total_mb = 0.0
    ram_pct = 0.0
    
    try:
        thermal_dir = "/sys/class/thermal"
        if os.path.exists(thermal_dir):
            for zone in sorted(os.listdir(thermal_dir)):
                if zone.startswith("thermal_zone"):
                    type_file = os.path.join(thermal_dir, zone, "type")
                    temp_file = os.path.join(thermal_dir, zone, "temp")
                    if os.path.exists(temp_file):
                        with open(temp_file, "r") as f:
                            raw_val = f.read().strip()
                            if raw_val:
                                t_val = float(raw_val) / 1000.0
                            else:
                                continue
                        
                        if not (0.0 <= t_val <= 125.0):
                            continue

                        t_type = ""
                        if os.path.exists(type_file):
                            with open(type_file, "r") as tf:
                                t_type = tf.read().strip().lower()
                        
                        if "gpu" in t_type:
                            gpu_temp = max(gpu_temp, t_val)
                        elif any(k in t_type for k in ["cpu", "x86", "soc", "core"]):
                            cpu_temp = max(cpu_temp, t_val)
                        elif cpu_temp == 0.0:
                            cpu_temp = t_val
    except Exception:
        pass

    try:
        if os.path.exists("/proc/stat"):
            with open("/proc/stat", "r") as f:
                first_line = f.readline()
            fields = [float(x) for x in first_line.split()[1:]]
            if len(fields) >= 5:
                idle = fields[3] + fields[4]
                total = sum(fields)
                
                idle_delta = idle - _last_cpu_idle
                total_delta = total - _last_cpu_total
                _last_cpu_idle = idle
                _last_cpu_total = total
                
                if total_delta > 0:
                    cpu_pct = round((1.0 - idle_delta / total_delta) * 100.0, 1)
    except Exception:
        pass

    try:
        if os.path.exists("/proc/meminfo"):
            mem_info = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val_str = parts[1].strip().split()[0]
                        mem_info[key] = float(val_str)
            if "MemTotal" in mem_info and "MemAvailable" in mem_info:
                total_kb = mem_info["MemTotal"]
                avail_kb = mem_info["MemAvailable"]
                if total_kb > 0:
                    used_kb = total_kb - avail_kb
                    ram_total_mb = round(total_kb / 1024.0, 1)
                    ram_used_mb = round(used_kb / 1024.0, 1)
                    ram_pct = round((used_kb / total_kb) * 100.0, 1)
    except Exception:
        pass

    return {
        "cpu_temp_c": round(cpu_temp, 1),
        "gpu_temp_c": round(gpu_temp, 1),
        "cpu_pct": cpu_pct,
        "ram_pct": ram_pct
    }


class DummyPublisher(Node):
    def __init__(self, args, stop_event):
        super().__init__('dummy_publisher')
        self.args = args
        self.stop_event = stop_event
        self.seq = 0
        
        self.ts_func = get_timestamp_ns(self.args.topology)
        
        # Cache health to update every 1 second (zero overhead during high-frequency publish)
        self._cached_health = get_system_health()
        self.create_timer(1.0, self._update_health_cache)
        
        qos_map = {
            'best_effort': QoSReliabilityPolicy.BEST_EFFORT,
            'reliable': QoSReliabilityPolicy.RELIABLE,
        }
        qos_profile = QoSProfile(
            reliability=qos_map[self.args.qos],
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
        )
        
        self.publisher_ = self.create_publisher(UInt8MultiArray, '/test_topic', qos_profile)
        
        timer_period = 1.0 / self.args.freq
        self.timer = self.create_timer(timer_period, self.timer_callback)
        
        self.cuda_enabled = False
        if cv2 is not None and hasattr(cv2, 'cuda'):
            try:
                if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                    self.cuda_enabled = True
            except Exception:
                pass
        
        if self.cuda_enabled:
            self.get_logger().info("[GPU] CUDA AKTIF")
            self.gpu_thread = threading.Thread(target=self.cuda_workload, daemon=True)
            self.gpu_thread.start()
        else:
            self.get_logger().info("[GPU] CUDA tidak tersedia")
            
    def _update_health_cache(self):
        """Update system health cache every 1s."""
        self._cached_health = get_system_health()

    def cuda_workload(self):
        import numpy as np
        try:
            dummy_mat = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)
            gpu_mat = cv2.cuda_GpuMat()
            gpu_mat.upload(dummy_mat)
        except Exception as e:
            self.get_logger().error(f"CUDA Init Error: {e}")
            return
            
        while not self.stop_event.is_set():
            try:
                gpu_mat.upload(dummy_mat)
                gray_gpu = cv2.cuda.cvtColor(gpu_mat, cv2.COLOR_BGR2GRAY)
                _ = gray_gpu.download()
            except Exception as e:
                self.get_logger().error(f"CUDA Error: {e}")
            time.sleep(0.02)

    def timer_callback(self):
        if self.stop_event.is_set():
            return
            
        if self.args.samples > 0 and self.seq >= self.args.samples:
            self.timer.cancel()
            self.get_logger().info(f"Mencapai target samples: {self.args.samples}. Menghentikan...")
            self.stop_event.set()
            return
            
        ts_ns = self.ts_func()
        
        # 24-byte Header: seq (Q, 8b), ts_ns (q, 8b), cpu_temp*10 (H, 2b), gpu_temp*10 (H, 2b), cpu_pct*10 (H, 2b), ram_pct*10 (H, 2b)
        h = self._cached_health
        c_temp_u16 = min(65535, max(0, int(h['cpu_temp_c'] * 10)))
        g_temp_u16 = min(65535, max(0, int(h['gpu_temp_c'] * 10)))
        c_pct_u16 = min(65535, max(0, int(h['cpu_pct'] * 10)))
        r_pct_u16 = min(65535, max(0, int(h['ram_pct'] * 10)))
        
        header = struct.pack('!QqHHHH', self.seq, ts_ns, c_temp_u16, g_temp_u16, c_pct_u16, r_pct_u16)
        padding_size = max(0, self.args.payload - len(header))
        payload_bytes = header + os.urandom(padding_size)
        
        msg = UInt8MultiArray()
        msg.data = array.array('B', payload_bytes)
        
        self.publisher_.publish(msg)
        
        if self.seq % self.args.freq == 0:
            self.get_logger().info(f"Published seq: {self.seq}, payload: {len(payload_bytes)} bytes (Pub Suhu: {h['cpu_temp_c']}°C)")
            
        self.seq += 1

def parse_args():
    parser = argparse.ArgumentParser(description="Dummy Publisher ROS 2")
    parser.add_argument('--freq', type=int, default=50, help="Publish frequency (Hz)")
    parser.add_argument('--payload', type=int, default=128, help="Payload size in bytes")
    parser.add_argument('--warmup-seconds', type=int, default=3, help="Warmup seconds")
    parser.add_argument('--qos', type=str, choices=['best_effort', 'reliable'], default='best_effort', help="QoS Profile")
    parser.add_argument('--topology', type=str, required=True, choices=['nuc2nuc', 'jetson2jetson', 'nuc2jetson', 'jetson2nuc'], help="Topology type")
    parser.add_argument('--samples', type=int, default=1000, help="Number of samples to publish (0 = unlimited)")
    return parser.parse_args()

def main():
    args = parse_args()
    if args.payload < 16:
        raise ValueError(f"Payload minimum 16 bytes, diberikan: {args.payload}")
        
    rclpy.init()
    stop_event = threading.Event()
    node = DummyPublisher(args, stop_event)
    
    try:
        while rclpy.ok() and not stop_event.is_set():
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        stop_event.set()
        if hasattr(node, 'gpu_thread') and node.gpu_thread.is_alive():
            node.gpu_thread.join(timeout=0.3)
        try:
            node.destroy_node()
        except Exception:
            pass
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass
        raise SystemExit(0)

if __name__ == '__main__':
    main()
