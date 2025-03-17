use sysinfo::{System, SystemExt, CpuExt, ProcessExt, DiskExt};
use std::ffi::{CString, CStr};
use std::os::raw::c_char;
use serde::Serialize;
use serde_json;

#[derive(Serialize)]
struct ProcessInfo {
    pid: String,
    name: String,
    cpu_usage: f32,
    memory_mb: f64,
    read_kb: f64,
    written_kb: f64,
}

/// Функция возвращает указатель на C-строку с наименованием процессора.
#[no_mangle]
pub extern "C" fn get_cpu_name() -> *mut c_char {
    let mut sys = System::new_all();
    sys.refresh_all();
    let cpu_name = if let Some(cpu) = sys.cpus().first() {
        cpu.brand().to_string()
    } else {
        "Unknown".to_string()
    };
    CString::new(cpu_name).unwrap().into_raw()
}

/// Функция возвращает указатель на C-строку с информацией об использовании процессора в процентах.
#[no_mangle]
pub extern "C" fn get_cpu_usage_info() -> *mut c_char {
    let mut sys = System::new_all();
    sys.refresh_all();
    let usage = if let Some(cpu) = sys.cpus().first() {
        format!("{:.2}%", cpu.cpu_usage())
    } else {
        "0.00%".to_string()
    };
    CString::new(usage).unwrap().into_raw()
}

/// Функция возвращает скорость процессора в ГГц.
#[no_mangle]
pub extern "C" fn get_cpu_frequency() -> f64 {
    let mut sys = System::new_all();
    sys.refresh_all();
    if let Some(cpu) = sys.cpus().first() {
        cpu.frequency() as f64 / 1000.0 // преобразование МГц в ГГц
    } else {
        0.0
    }
}

/// Функция возвращает количество процессов.
#[no_mangle]
pub extern "C" fn get_process_count() -> usize {
    let mut sys = System::new_all();
    sys.refresh_all();
    sys.processes().len()
}

/// Функция возвращает количество потоков (ядер) у процессора.
#[no_mangle]
pub extern "C" fn get_cpu_count() -> usize {
    let mut sys = System::new_all();
    sys.refresh_all();
    sys.cpus().len()
}

/// Функция возвращает время работы системы в секундах.
#[no_mangle]
pub extern "C" fn get_uptime() -> u64 {
    let mut sys = System::new_all();
    sys.refresh_all();
    sys.uptime()
}

/// Функция возвращает указатель на C-строку в формате JSON с информацией обо всех процессах.
#[no_mangle]
pub extern "C" fn get_all_processes_json() -> *mut c_char {
    let mut sys = System::new_all();
    sys.refresh_all();

    // Собираем процессы в вектор; ключ имеет тип sysinfo::Pid
    let mut processes: Vec<(&sysinfo::Pid, &sysinfo::Process)> = sys.processes().iter().collect();
    // Сортируем по убыванию использования CPU (при необходимости)
    processes.sort_by(|a, b| b.1.cpu_usage().partial_cmp(&a.1.cpu_usage()).unwrap());

    let mut proc_list = Vec::new();
    for (pid, process) in processes.iter() {
        let disk_usage = process.disk_usage();
        proc_list.push(ProcessInfo {
            pid: pid.to_string(),
            name: process.name().to_string(),
            cpu_usage: process.cpu_usage(),
            memory_mb: process.memory() as f64 / (1024.0 * 1024.0),
            read_kb: disk_usage.total_read_bytes as f64 / 1024.0,
            written_kb: disk_usage.total_written_bytes as f64 / 1024.0,
        });
    }

    let json_str = serde_json::to_string(&proc_list).unwrap_or_else(|_| "[]".to_string());
    CString::new(json_str).unwrap().into_raw()
}

/// Функция для освобождения памяти, выделенной функциями, возвращающими строку.
#[no_mangle]
pub extern "C" fn free_string(s: *mut c_char) {
    if s.is_null() { return; }
    unsafe { CString::from_raw(s); }
}
