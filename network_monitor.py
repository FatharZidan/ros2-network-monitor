import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from std_msgs.msg import ByteMultiArray
import argparse
import struct
import time
from datetime import datetime
import threading
import csv
import sys

def get_timestamp_ns(topology: str):
    """Return timestamp function based on topology."""
    if topology in ('nuc2nuc', 'jetson2jetson'):
        return time.perf_counter_ns
    elif topology in ('nuc2jetson', 'jetson2nuc'):
        return time.time_ns
    else:
        raise ValueError(f"Topology tidak valid: {topology}. Pilihan: nuc2nuc, jetson2jetson, nuc2jetson, jetson2nuc")

def calculate_percentile(data: list, p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    index = (p / 100) * (n - 1)
    lower = int(index)
    upper = min(lower + 1, n - 1)
    fraction = index - lower
    return sorted_data[lower] + fraction * (sorted_data[upper] - sorted_data[lower])

class NetworkMonitor(Node):
    def __init__(self, args, stop_event):
        super().__init__('network_monitor')
        self.args = args
        self.stop_event = stop_event
        
        self.ts_func = get_timestamp_ns(self.args.topology)
        
        self.warmup_end_time = time.time() + self.args.warmup_seconds
        
        self.last_seq = -1
        self.first_seq = -1
        self.total_gaps = 0
        self.valid_samples = 0
        self.latencies_ms = []
        
        self.msg_count_1s = 0
        
        qos_map = {
            'best_effort': QoSReliabilityPolicy.BEST_EFFORT,
            'reliable': QoSReliabilityPolicy.RELIABLE,
        }
        qos_profile = QoSProfile(
            reliability=qos_map[self.args.qos],
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
        )
        
        self.subscription = self.create_subscription(
            ByteMultiArray,
            '/test_topic',
            self.listener_callback,
            qos_profile
        )
        
        self.report_timer = self.create_timer(1.0, self.report_callback)
        self.get_logger().info(f"Network Monitor started. Topology: {self.args.topology}, QoS: {self.args.qos}")

    def listener_callback(self, msg):
        if self.stop_event.is_set():
            return
            
        recv_ts = self.ts_func()
        
        if time.time() < self.warmup_end_time:
            return
            
        raw = bytes(msg.data)
        if len(raw) < 16:
            return
            
        seq, send_ts = struct.unpack('!Qq', raw[:16])
        
        latency_ns = recv_ts - send_ts
        latency_ms = latency_ns / 1_000_000.0
        
        self.latencies_ms.append(latency_ms)
        self.valid_samples += 1
        self.msg_count_1s += 1
        
        if self.last_seq == -1:
            self.first_seq = seq
            self.last_seq = seq
        else:
            if seq > self.last_seq + 1:
                self.total_gaps += (seq - self.last_seq - 1)
            self.last_seq = seq
            
        if self.args.samples > 0 and self.valid_samples >= self.args.samples:
            self.stop_event.set()

    def report_callback(self):
        if self.stop_event.is_set():
            return
            
        if self.first_seq == -1:
            return
            
        total_expected = self.last_seq - self.first_seq + 1
        miss_rate = (self.total_gaps / total_expected) * 100 if total_expected > 0 else 0.0
        
        if self.latencies_ms:
            avg_lat = sum(self.latencies_ms) / len(self.latencies_ms)
            min_lat = min(self.latencies_ms)
            max_lat = max(self.latencies_ms)
            p95_lat = calculate_percentile(self.latencies_ms, 95.0)
            p99_lat = calculate_percentile(self.latencies_ms, 99.0)
        else:
            avg_lat = min_lat = max_lat = p95_lat = p99_lat = 0.0
            
        hz = self.msg_count_1s
        self.msg_count_1s = 0
        
        self.get_logger().info(
            f"Hz: {hz} | Avg: {avg_lat:.2f}ms | Min: {min_lat:.2f}ms | Max: {max_lat:.2f}ms | "
            f"P95: {p95_lat:.2f}ms | P99: {p99_lat:.2f}ms | Miss: {miss_rate:.2f}% | Total: {self.valid_samples}"
        )

    def export_csv(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"brone_log_{self.args.topology}_{self.args.freq}hz_{self.args.payload}b_{self.args.qos}_{timestamp}.csv"
        
        total_expected = self.last_seq - self.first_seq + 1 if self.first_seq != -1 else 0
        miss_rate = (self.total_gaps / total_expected) * 100 if total_expected > 0 else 0.0
        
        if self.latencies_ms:
            avg_lat = sum(self.latencies_ms) / len(self.latencies_ms)
            min_lat = min(self.latencies_ms)
            max_lat = max(self.latencies_ms)
            p95_lat = calculate_percentile(self.latencies_ms, 95.0)
            p99_lat = calculate_percentile(self.latencies_ms, 99.0)
        else:
            avg_lat = min_lat = max_lat = p95_lat = p99_lat = 0.0
            
        ros2_distro_note = "NUC=Jazzy_Jetson=Humble"
        
        header = [
            "session_timestamp", "topology", "freq_hz", "payload_size_bytes", "qos_profile",
            "ros2_distro_note", "total_samples", "total_expected", "total_gaps",
            "miss_rate_percent", "avg_lat_ms", "min_lat_ms", "max_lat_ms", "p95_lat_ms", "p99_lat_ms"
        ]
        
        row = [
            timestamp, self.args.topology, self.args.freq, self.args.payload, self.args.qos,
            ros2_distro_note, self.valid_samples, total_expected, self.total_gaps,
            miss_rate, avg_lat, min_lat, max_lat, p95_lat, p99_lat
        ]
        
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerow(row)
            self.get_logger().info(f"Berhasil menyimpan log ke: {filename}")
        except Exception as e:
            self.get_logger().error(f"Gagal menyimpan CSV: {e}")


def parse_args():
    parser = argparse.ArgumentParser(description="Network Monitor ROS 2")
    parser.add_argument('--freq', type=int, default=50, help="Publish frequency (Hz) (untuk log/filename)")
    parser.add_argument('--payload', type=int, default=128, help="Payload size in bytes (untuk log/filename)")
    parser.add_argument('--warmup-seconds', type=int, default=3, help="Warmup seconds")
    parser.add_argument('--qos', type=str, choices=['best_effort', 'reliable'], default='best_effort', help="QoS Profile")
    parser.add_argument('--topology', type=str, required=True, choices=['nuc2nuc', 'jetson2jetson', 'nuc2jetson', 'jetson2nuc'], help="Topology type")
    parser.add_argument('--samples', type=int, default=1000, help="Number of samples to collect (0 = unlimited)")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.payload < 16:
        raise ValueError(f"Payload minimum 16 bytes, diberikan: {args.payload}")
        
    rclpy.init()
    stop_event = threading.Event()
    node = NetworkMonitor(args, stop_event)
    
    try:
        while rclpy.ok() and not stop_event.is_set():
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        node.export_csv()
        node.destroy_node()
        rclpy.shutdown()
        raise SystemExit(0)

if __name__ == '__main__':
    main()
