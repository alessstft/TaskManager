use sysinfo::{System, SystemExt, CpuExt, ProcessExt, DiskExt, ComponentExt};
use std::ffi::{CString, CStr};
use std::os::raw::c_char;
use std::sync::{
    Arc,
    Mutex,
    atomic::{AtomicBool, Ordering},
};
use std::thread::{self, JoinHandle};
use std::time::Duration;
use lazy_static::lazy_static;

// ===================== СТРУКТУРЫ ДЛЯ СТАТИЧЕСКОЙ ИНФОРМАЦИИ =====================

#[repr(C)]
pub struct CpuStaticInfo {
    pub brand: *mut c_char,  // наименование ЦПУ
    pub usage: f32,          // загрузка (в %)
    pub frequency: f64,      // частота (ГГц)
    pub core_count: usize,   // количество ядер
}

#[repr(C)]
pub struct MemoryStaticInfo {
    pub total: u64,      // общий объём (КБ)
    pub used: u64,       // используемая память (КБ)
    pub available: u64,  // доступная память (КБ)
}

#[repr(C)]
pub struct DiskStaticInfo {
    pub name: *mut c_char,     // имя диска
    pub total_space: u64,      // общий объём (в байтах)
    pub available_space: u64,  // свободное место (в байтах)
}

#[repr(C)]
pub struct DiskStaticInfoArray {
    pub data: *mut DiskStaticInfo,
    pub len: usize,
}

// ===================== ФУНКЦИИ ДЛЯ СТАТИЧЕСКОЙ ИНФОРМАЦИИ =====================

#[no_mangle]
pub extern "C" fn get_cpu_static_info() -> *mut CpuStaticInfo {
    let mut sys = System::new_all();
    sys.refresh_all();
    let brand = if let Some(cpu) = sys.cpus().first() {
        cpu.brand().to_string()
    } else {
        "Unknown".to_string()
    };
    let usage = if let Some(cpu) = sys.cpus().first() {
        cpu.cpu_usage()
    } else {
        0.0
    };
    let frequency = if let Some(cpu) = sys.cpus().first() {
        cpu.frequency() as f64 / 1000.0
    } else {
        0.0
    };
    let core_count = sys.cpus().len();
    let info = CpuStaticInfo {
        brand: CString::new(brand).unwrap().into_raw(),
        usage,
        frequency,
        core_count,
    };
    Box::into_raw(Box::new(info))
}

#[no_mangle]
pub extern "C" fn free_cpu_static_info(info: *mut CpuStaticInfo) {
    if info.is_null() { return; }
    unsafe {
        let info_box = Box::from_raw(info);
        if !info_box.brand.is_null() {
            let _ = CString::from_raw(info_box.brand);
        }
    }
}

#[no_mangle]
pub extern "C" fn get_memory_static_info() -> MemoryStaticInfo {
    let mut sys = System::new_all();
    sys.refresh_all();
    MemoryStaticInfo {
        total: sys.total_memory() / (1024*1024*1024),      // перевод из КБ в МБ
        used: sys.used_memory() / (1024*1024*1024),          // перевод из КБ в МБ
        available: sys.available_memory() / (1024*1024*1024) // перевод из КБ в МБ
    }
}

#[no_mangle]
pub extern "C" fn get_disk_static_info_array() -> DiskStaticInfoArray {
    let mut sys = System::new_all();
    sys.refresh_all();
    let disks = sys.disks();
    let len = disks.len();
    let mut vec: Vec<DiskStaticInfo> = Vec::with_capacity(len);
    for disk in disks {
        let name = disk.name().to_string_lossy().to_string();
        vec.push(DiskStaticInfo {
            name: CString::new(name).unwrap().into_raw(),
            total_space: disk.total_space() / (1024 * 1024 * 1024),      // перевод из байт в ГБ
            available_space: disk.available_space() / (1024 * 1024 * 1024) // перевод из байт в ГБ
        });
    }
    let data_ptr = vec.as_mut_ptr();
    std::mem::forget(vec);
    DiskStaticInfoArray { data: data_ptr, len }
}

#[no_mangle]
pub extern "C" fn free_disk_static_info_array(array: DiskStaticInfoArray) {
    if array.data.is_null() { return; }
    unsafe {
        let vec = Vec::from_raw_parts(array.data, array.len, array.len);
        for disk in vec {
            if !disk.name.is_null() {
                let _ = CString::from_raw(disk.name);
            }
        }
    }
}

// ===================== ФУНКЦИИ ДЛЯ ПОДБОРА ИНФОРМАЦИИ О ПРОЦЕССАХ (ПОТОКОВЫЙ МОДУЛЬ) =====================

/// C‑совместимая структура для информации о процессе.
#[repr(C)]
pub struct ProcessInfo {
    pub pid: *mut c_char,      // идентификатор процесса (строка)
    pub name: *mut c_char,     // имя процесса
    pub cpu_usage: f32,        // загрузка CPU (в %)
    pub memory_mb: f64,        // используемая память (МБ)
    pub read_kb: f64,          // прочитано (КБ)
    pub written_kb: f64,       // записано (КБ)
}

/// Обёртка для массива структур с информацией о процессах.
#[repr(C)]
pub struct ProcessInfoArray {
    pub data: *mut ProcessInfo,
    pub len: usize,
}

/// Внутренняя структура для хранения данных о процессах (используются Rust‑строки).
#[derive(Clone)]
struct ProcessInfoInternal {
    pub pid: String,
    pub name: String,
    pub cpu_usage: f32,
    pub memory_mb: f64,
    pub read_kb: f64,
    pub written_kb: f64,
}

struct ProcessCollector {
    running: Arc<AtomicBool>,
    info: Arc<Mutex<Vec<ProcessInfoInternal>>>,
    handle: Option<JoinHandle<()>>,
}

lazy_static! {
    static ref PROCESS_COLLECTOR: Mutex<Option<ProcessCollector>> = Mutex::new(None);
}

fn create_process_info_internal(pid: &sysinfo::Pid, process: &sysinfo::Process) -> ProcessInfoInternal {
    let disk_usage = process.disk_usage();
    ProcessInfoInternal {
        pid: pid.to_string(),
        name: process.name().to_string(),
        cpu_usage: process.cpu_usage(),
        memory_mb: process.memory() as f64 / (1024.0 * 1024.0),
        read_kb: disk_usage.total_read_bytes as f64 / 1024.0,
        written_kb: disk_usage.total_written_bytes as f64 / 1024.0,
    }
}

fn process_collector_thread(running: Arc<AtomicBool>, info: Arc<Mutex<Vec<ProcessInfoInternal>>>) {
    let mut sys = System::new_all(); // создаём один объект System
    while running.load(Ordering::Relaxed) {
        sys.refresh_processes();
        sys.refresh_cpu();
        
        let mut processes_vec = Vec::new();
        for (pid, process) in sys.processes() {
            processes_vec.push(create_process_info_internal(pid, process));
        }
        processes_vec.sort_by(|a, b| b.cpu_usage.partial_cmp(&a.cpu_usage).unwrap());
        {
            let mut locked = info.lock().unwrap();
            *locked = processes_vec;
        }
        thread::sleep(Duration::from_secs(1));
    }
}

/// 1) Запуск фонового потока сбора информации о процессах.
/// Если поток уже запущен, возвращает false.
#[no_mangle]
pub extern "C" fn start_process_collector() -> bool {
    let mut collector_opt = PROCESS_COLLECTOR.lock().unwrap();
    if collector_opt.is_some() {
        return false;
    }
    let running = Arc::new(AtomicBool::new(true));
    let info = Arc::new(Mutex::new(Vec::new()));
    let running_clone = running.clone();
    let info_clone = info.clone();
    let handle = thread::spawn(move || {
        process_collector_thread(running_clone, info_clone);
    });
    *collector_opt = Some(ProcessCollector {
        running,
        info,
        handle: Some(handle),
    });
    true
}

/// 2) Получение актуальной информации о процессах.
/// Функция возвращает ProcessInfoArray, содержащую указатель на массив структур и число элементов.
/// Память для возвращённого массива необходимо освободить с помощью free_process_info_array.
#[no_mangle]
pub extern "C" fn get_process_info_array() -> ProcessInfoArray {
    let collector_opt = PROCESS_COLLECTOR.lock().unwrap();
    if let Some(collector) = &*collector_opt {
        let locked = collector.info.lock().unwrap();
        let mut new_vec: Vec<ProcessInfo> = Vec::with_capacity(locked.len());
        for proc in locked.iter() {
            let pid_dup = CString::new(proc.pid.clone()).unwrap();
            let name_dup = CString::new(proc.name.clone()).unwrap();
            new_vec.push(ProcessInfo {
                pid: pid_dup.into_raw(),
                name: name_dup.into_raw(),
                cpu_usage: proc.cpu_usage,
                memory_mb: proc.memory_mb,
                read_kb: proc.read_kb,
                written_kb: proc.written_kb,
            });
        }
        let len = new_vec.len();
        let data_ptr = new_vec.as_mut_ptr();
        std::mem::forget(new_vec);
        ProcessInfoArray { data: data_ptr, len }
    } else {
        ProcessInfoArray { data: std::ptr::null_mut(), len: 0 }
    }
}

/// 3) Остановка фонового потока сбора информации о процессах.
/// Функция останавливает поток, ожидает его завершения и освобождает ресурсы.
/// Возвращает true, если поток был успешно остановлен.
#[no_mangle]
pub extern "C" fn stop_process_collector() -> bool {
    let mut collector_opt = PROCESS_COLLECTOR.lock().unwrap();
    if let Some(mut collector) = collector_opt.take() {
        collector.running.store(false, Ordering::Relaxed);
        if let Some(handle) = collector.handle.take() {
            handle.join().unwrap();
        }
        {
            let mut locked = collector.info.lock().unwrap();
            locked.clear();
        }
        true
    } else {
        false
    }
}

/// Освобождение памяти, выделенной для массива ProcessInfoArray.
#[no_mangle]
pub extern "C" fn free_process_info_array(array: ProcessInfoArray) {
    if array.data.is_null() { return; }
    unsafe {
        let vec = Vec::from_raw_parts(array.data, array.len, array.len);
        for proc in vec {
            if !proc.pid.is_null() {
                let _ = CString::from_raw(proc.pid);
            }
            if !proc.name.is_null() {
                let _ = CString::from_raw(proc.name);
            }
        }
    }
}

/// Функция для освобождения памяти, выделенной функциями, возвращающими C‑строку.
#[no_mangle]
pub extern "C" fn free_string(s: *mut c_char) {
    if s.is_null() { return; }
    unsafe { CString::from_raw(s); }
}
