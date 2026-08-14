import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from std_msgs.msg import ByteMultiArray
import argparse
import struct
import os
import time
import threading
import sys

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

class DummyPublisher(Node):
    def __init__(self, args, stop_event):
        super().__init__('dummy_publisher')
        self.args = args
        self.stop_event = stop_event
        self.seq = 0
        
        self.ts_func = get_timestamp_ns(self.args.topology)
        
        qos_map = {
            'best_effort': QoSReliabilityPolicy.BEST_EFFORT,
            'reliable': QoSReliabilityPolicy.RELIABLE,
        }
        qos_profile = QoSProfile(
            reliability=qos_map[self.args.qos],
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
        )
        
        self.publisher_ = self.create_publisher(ByteMultiArray, '/test_topic', qos_profile)
        
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
            
    def cuda_workload(self):
        import numpy as np
        while not self.stop_event.is_set():
            try:
                dummy_mat = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)
                gpu_mat = cv2.cuda_GpuMat()
                gpu_mat.upload(dummy_mat)
                gray_gpu = cv2.cuda.cvtColor(gpu_mat, cv2.COLOR_BGR2GRAY)
                _ = gray_gpu.download()
            except Exception as e:
                self.get_logger().error(f"CUDA Error: {e}")
            time.sleep(0.01)

    def timer_callback(self):
        if self.stop_event.is_set():
            return
            
        if self.args.samples > 0 and self.seq >= self.args.samples:
            self.timer.cancel()
            self.get_logger().info(f"Mencapai target samples: {self.args.samples}. Menghentikan...")
            self.stop_event.set()
            return
            
        ts_ns = self.ts_func()
        
        padding_size = max(0, self.args.payload - 16)
        header = struct.pack('!Qq', self.seq, ts_ns)
        payload_bytes = header + os.urandom(padding_size)
        
        msg = ByteMultiArray()
        msg.data = list(payload_bytes)
        
        self.publisher_.publish(msg)
        
        if self.seq % self.args.freq == 0:
            self.get_logger().info(f"Published seq: {self.seq}, payload: {self.args.payload} bytes")
            
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
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        raise SystemExit(0)

if __name__ == '__main__':
    main()
