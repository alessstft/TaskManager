import ctypes
from ctypes import c_char_p, c_float, c_double, c_uint64, c_int, c_void_p, Structure, POINTER, c_size_t, c_uint32
import os
from typing import List, Dict
import threading
import time

# Определения структур для FFI (как и ранее)
class ProcessInfo(Structure):
    _fields_ = [
        ("pid", c_char_p),
        ("name", c_char_p),
        ("cpu_usage", c_float),
        ("memory_mb", c_double),
        ("read_kb", c_double),
        ("written_kb", c_double),
    ]

class ProcessInfoArray(Structure):
    _fields_ = [
        ("data", POINTER(ProcessInfo)),
        ("len", c_size_t),
    ]

class ServiceInfo(Structure):
    _fields_ = [
        ("process_id", c_uint32),
        ("name", c_char_p),
        ("status", c_char_p),
    ]

class ServiceInfoArray(Structure):
    _fields_ = [
        ("data", POINTER(ServiceInfo)),
        ("len", c_size_t),
    ]

class CpuStaticInfo(Structure):
    _fields_ = [
        ("brand", c_char_p),
        ("usage", c_float),
        ("frequency", c_double),
        ("core_count", c_size_t),
        ("work_time", c_int),
        ("process", c_int),
    ]

class MemoryStaticInfo(Structure):
    _fields_ = [
        ("total", c_uint64),
        ("used", c_uint64),
        ("available", c_uint64),
        ("speed", c_uint64),
        ("format", c_char_p),
    ]

class DiskStaticInfo(Structure):
    _fields_ = [
        ("name", c_char_p),
        ("total_space", c_uint64),
        ("available_space", c_uint64),
    ]

class DiskStaticInfoArray(Structure):
    _fields_ = [
        ("data", POINTER(DiskStaticInfo)),
        ("len", c_size_t),
    ]

class NetworksStaticInfo(Structure):
    _fields_ = [
        ("name", c_char_p),
        ("ipv4", c_char_p),
        ("send", c_uint64),
        ("recive", c_uint64),
    ]

class NetworksStaticInfoArray(Structure):
    _fields_ = [
        ("data", POINTER(NetworksStaticInfo)),
        ("len", c_size_t),
    ]

class SystemMonitor:
    def __init__(self, dll_path: str = "C:/Users/studentcoll/Desktop/Панов Иля/Менеджер задач/sis_info_dll/target/release/sys_info_fn.dll"):
        try:
            self.dll = ctypes.CDLL(dll_path)
        except Exception as e:
            print(f"Error loading DLL: {e}")
            raise
        self._setup_dll_functions()
        self._running = False
        self._update_thread = None
        self._stop_event = threading.Event()
        self._callbacks = []
        self._last_network_stats = {}
        self._last_update_time = time.time()
        
    def _setup_dll_functions(self):
        self.dll.get_cpu_static_info.restype = POINTER(CpuStaticInfo)
        self.dll.get_memory_static_info.restype = MemoryStaticInfo
        self.dll.get_process_info_array.restype = ProcessInfoArray
        self.dll.get_disk_static_info_array.restype = DiskStaticInfoArray
        self.dll.get_networks_static_info_array.restype = NetworksStaticInfoArray
        self.dll.get_services_info_array.restype = ServiceInfoArray

        self.dll.start_process_collector.restype = c_int
        self.dll.stop_process_collector.restype = c_int
        self.dll.kill_process.argtypes = [c_uint32]
        self.dll.kill_process.restype = c_int

        
    def start_monitoring(self, update_interval: float = 2.0):
        """Запускает мониторинг системы с минимальной нагрузкой."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self.dll.start_process_collector()
        
        def update_loop():
            while not self._stop_event.is_set():
                start_time = time.time()
                self._update_data()
                elapsed = time.time() - start_time
                wait_time = max(0, update_interval - elapsed)
                self._stop_event.wait(wait_time)
                
        self._update_thread = threading.Thread(target=update_loop, daemon=True)
        self._update_thread.start()
        
    def stop_monitoring(self):
        """Останавливает мониторинг системы."""
        self._running = False
        self._stop_event.set()
        if self._update_thread:
            self._update_thread.join()
        self.dll.stop_process_collector()
        
    def _update_data(self):
        try:
            cpu_info = self._get_cpu_info()
            memory_info = self._get_memory_info()
            process_info = self._get_process_info()
            for callback in self._callbacks:
                callback(cpu_info, memory_info, process_info)
        except Exception as e:
            print(f"Error updating system data: {e}")
            
    def register_callback(self, callback):
        self._callbacks.append(callback)
        
    def unregister_callback(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            
    def _get_cpu_info(self) -> Dict:
        cpu_info_ptr = self.dll.get_cpu_static_info()
        cpu_info = cpu_info_ptr.contents
        info = {
            'brand': cpu_info.brand.decode('utf-8'),
            'usage': cpu_info.usage,
            'frequency': cpu_info.frequency,
            'core_count': cpu_info.core_count,
            'work_time': cpu_info.work_time,
            'process_count': cpu_info.process
        }
        self.dll.free_cpu_static_info(cpu_info_ptr)
        return info
        
    def _get_memory_info(self) -> Dict:
        memory_info = self.dll.get_memory_static_info()
        info = {
            'total': memory_info.total,
            'used': memory_info.used,
            'available': memory_info.available,
            'speed': memory_info.speed,
            'format': memory_info.format.decode('utf-8') if memory_info.format else "Unknown"
        }
        return info
        
    def _get_process_info(self) -> List[Dict]:
        process_array = self.dll.get_process_info_array()
        processes = []
        for i in range(process_array.len):
            process = process_array.data[i]
            processes.append({
                'pid': process.pid.decode('utf-8'),
                'name': process.name.decode('utf-8'),
                'cpu_usage': process.cpu_usage,
                'memory_mb': process.memory_mb,
                'read_kb': process.read_kb,
                'written_kb': process.written_kb
            })
        self.dll.free_process_info_array(process_array)
        return processes
        
    def _get_disk_info(self) -> List[Dict]:
        disk_array = self.dll.get_disk_static_info_array()
        disks = []
        for i in range(disk_array.len):
            disk = disk_array.data[i]
            disks.append({
                'name': disk.name.decode('utf-8'),
                'total_space': disk.total_space,
                'available_space': disk.available_space
            })
        self.dll.free_disk_static_info_array(disk_array)
        return disks
        
    def _get_network_info(self) -> List[Dict]:
        network_array = self.dll.get_networks_static_info_array()
        networks = []
        current_time = time.time()
        time_diff = current_time - self._last_update_time
        if time_diff > 2.0:
            self._last_network_stats = {}
            time_diff = 1.0
        
        for i in range(network_array.len):
            network = network_array.data[i]
            name = network.name.decode('utf-8')
            current_stats = {
                'send': network.send,
                'recive': network.recive,
                'time': current_time
            }
            if name in self._last_network_stats:
                last_stats = self._last_network_stats[name]
                send_speed = (current_stats['send'] - last_stats['send']) / time_diff
                recv_speed = (current_stats['recive'] - last_stats['recive']) / time_diff
                if send_speed < 0 or send_speed > 1e9:
                    send_speed = 0
                if recv_speed < 0 or recv_speed > 1e9:
                    recv_speed = 0
            else:
                send_speed = 0
                recv_speed = 0
                
            networks.append({
                'name': name,
                'ipv4': network.ipv4.decode('utf-8') if network.ipv4 else "",
                'send_speed': send_speed,
                'recv_speed': recv_speed
            })
            self._last_network_stats[name] = current_stats
            
        self._last_update_time = current_time
        self.dll.free_networks_static_info_array(network_array)
        return networks

    def get_disk_info(self) -> List[Dict]:
        return self._get_disk_info()

    def get_network_info(self) -> List[Dict]:
        return self._get_network_info()

    def get_cpu_percent(self) -> float:
        return self._get_cpu_info()['usage']

    def get_memory_percent(self) -> float:
        memory_info = self._get_memory_info()
        return (memory_info['used'] / memory_info['total']) * 100

    def get_services_info(self) -> List[Dict]:
        services_array = self.dll.get_services_info_array()
        services = []
        for i in range(services_array.len):
            service = services_array.data[i]
            services.append({
                'process_id': service.process_id,
                'name': service.name.decode('utf-8') if service.name else "Unknown",
                'status': service.status.decode('utf-8') if service.status else "Unknown"
            })
        self.dll.free_services_info_array(services_array)
        return services

    def kill_process(self, pid: int) -> bool:
        result = self.dll.kill_process(pid)
        return result == 0


    def __del__(self):
        if hasattr(self, '_update_thread'):
            self.stop_monitoring()
