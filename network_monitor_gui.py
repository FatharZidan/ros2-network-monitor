"""
ROS 2 Network Monitor with Web Dashboard for BRONE robot project.
"""

import struct
import time
import json
import statistics
import threading
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
                data = {}
            
            self.wfile.write(json.dumps(data).encode('utf-8'))
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
        _monitor_node.get_logger().info('KeyboardInterrupt received, shutting down...')
    finally:
        httpd.shutdown()
        _monitor_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
