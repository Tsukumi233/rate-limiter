"""
多节点启动脚本
用于启动多个 Rate Limiter 服务实例
"""
import subprocess
import sys
import time
import signal
import os
from typing import List
import threading


class MultiNodeManager:
    """多节点管理器"""
    
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.ports = [8000, 8001, 8002]  # 默认端口
        
    def read_output(self, process, port):
        """读取进程输出的线程函数"""
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"[节点 {port}] {line.strip()}")
                
        for line in iter(process.stderr.readline, ''):
            if line:
                print(f"[节点 {port} 错误] {line.strip()}")
    
    def start_node(self, port: int) -> subprocess.Popen:
        """启动单个节点"""
        print(f"[START] Starting Rate Limiter node on port: {port}")
        
        # 设置环境变量
        env = os.environ.copy()
        env["SERVER_PORT"] = str(port)
        
        # 启动进程
        process = subprocess.Popen(
            [sys.executable, "-m", "src.server", "--port", str(port)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # 启动线程读取输出
        stdout_thread = threading.Thread(target=self.read_output, args=(process, port))
        stdout_thread.daemon = True
        stdout_thread.start()
        
        return process
    
    def start_all_nodes(self):
        """启动所有节点"""
        print("=" * 60)
        print("[CLUSTER] Starting Rate Limiter Cluster")
        print("=" * 60)
        
        for port in self.ports:
            process = self.start_node(port)
            self.processes.append(process)
            time.sleep(2)  # 等待节点启动
        
        print(f"\n[OK] Started {len(self.processes)} nodes")
        print(f"[INFO] Ports: {', '.join(map(str, self.ports))}")
        print("\nPress Ctrl+C to stop all nodes...")
    
    def monitor_nodes(self):
        """监控节点输出"""
        try:
            while True:
                for i, process in enumerate(self.processes):
                    # 检查进程是否还在运行
                    if process.poll() is not None:
                        print(f"\n[WARN] Node {i+1} (port {self.ports[i]}) stopped with exit code: {process.returncode}")
                        # 重启节点
                        print(f"[RESTART] Restarting node {i+1}...")
                        new_process = self.start_node(self.ports[i])
                        self.processes[i] = new_process
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n\n[STOP] Received stop signal...")
            self.stop_all_nodes()
    
    def stop_all_nodes(self):
        """停止所有节点"""
        print("Stopping all nodes...")
        
        for i, process in enumerate(self.processes):
            if process.poll() is None:
                print(f"Stopping node {i+1} (port {self.ports[i]})...")
                process.terminate()
                
                # 等待进程结束
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"Force stopping node {i+1}...")
                    process.kill()
        
        print("[OK] All nodes stopped")
    
    def run(self):
        """运行多节点管理器"""
        try:
            self.start_all_nodes()
            self.monitor_nodes()
        except Exception as e:
            print(f"\n[ERROR] Error: {e}")
            import traceback
            traceback.print_exc()
            self.stop_all_nodes()


def check_redis():
    """检查 Redis 是否可用"""
    print("[CHECK] Checking Redis connection...")
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("[OK] Redis connection is OK")
        return True
    except Exception as e:
        print(f"[ERROR] Redis connection failed: {e}")
        print("\nPlease ensure Redis server is running:")
        print("  - Windows: run redis-server.exe")
        print("  - Linux/Mac: run redis-server")
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="启动多个 Rate Limiter 节点")
    parser.add_argument("--ports", nargs="+", type=int, default=[8000, 8001, 8002],
                       help="节点端口列表")
    parser.add_argument("--skip-redis-check", action="store_true",
                       help="跳过 Redis 检查")
    
    args = parser.parse_args()
    
    # 检查 Redis
    if not args.skip_redis_check and not check_redis():
        sys.exit(1)
    
    # 创建并运行管理器
    manager = MultiNodeManager()
    manager.ports = args.ports
    manager.run()


if __name__ == "__main__":
    main() 