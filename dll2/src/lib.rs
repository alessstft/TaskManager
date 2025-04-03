use sysinfo::{System, SystemExt, CpuExt, ProcessExt, DiskExt, NetworksExt,NetworkExt};
use std::ffi::CString;
use std::os::raw::c_char;
use std::sync::{
    Arc,
    Mutex,
    atomic::{AtomicBool, Ordering},
};
use std::thread::{self, JoinHandle};
use std::time::Duration;
use lazy_static::lazy_static;
use local_ipaddress;
use std::process::Command;
use serde::Deserialize;
// ===================== СТРУКТУРЫ ДЛЯ СТАТИЧЕСКОЙ ИНФОРМАЦИИ =====================

#[repr(C)]
pub struct CpuStaticInfo {
    pub brand: *mut c_char,  // наименование ЦПУ
    pub usage: f32,          // загрузка (в %)
    pub frequency: f64,      // частота (ГГц)
    pub core_count: usize,   // количество ядер
    pub work_time: i64,      // время работы
    pub process: i64,        // количество процессов
}

#[cfg(target_os = "windows")]
#[derive(Deserialize, Debug)]
struct Win32PhysicalMemory {
    #[serde(rename = "Speed")]
    speed: u32,
    #[serde(rename = "MemoryType")]
    memory_type: Option<u32>,
    #[serde(rename = "SMBIOSMemoryType")]
    smbios_memory_type: Option<u32>,
}

#[repr(C)]
pub struct MemoryStaticInfo {
    pub total: u64,         // общий объём (КБ)
    pub used: u64,          // используемая память (КБ)
    pub available: u64,     // доступная память (КБ)
    pub speed: u64,         // скорость памяти (МГц)
    pub format: *mut c_char,// формат памяти (например, "DDR4")
}

#[repr(C)]
pub struct MemoryInfo {
    pub speed: u32,
    pub memory_format: *mut c_char,
}

#[repr(C)]
pub struct MemoryInfoArray {
    pub data: *mut MemoryInfo,
    pub len: usize,
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

#[repr(C)]
pub struct NetworksStaticInfo {
    pub name: *mut c_char,
    pub ipv4: *mut c_char,
    pub send: u64,
    pub recive: u64,
}

#[repr(C)]
pub struct NetworksStaticInfoArray {
    pub data: *mut NetworksStaticInfo,
    pub len: usize,
}


#[cfg(target_os = "windows")]
#[repr(C)]
pub struct ServiceInfo {
    pub process_id: u32,    // Идентификатор процесса службы
    pub name: *mut c_char,  // Имя службы
    pub status: *mut c_char,// Статус службы
}

#[cfg(target_os = "windows")]
#[repr(C)]
pub struct ServiceInfoArray {
    pub data: *mut ServiceInfo,
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
    
    let work_time= if let Some(cpu) = sys.cpus().first() {
        sys.uptime() as i64
    } else {
        0
    };

    let process= if let Some(cpu) = sys.cpus().first() {
        sys.processes().len() as i64
    } else {
        0
    };

    let core_count = num_cpus::get_physical();
    let info = CpuStaticInfo {
        brand: CString::new(brand).unwrap().into_raw(),
        usage,
        frequency,
        process,
        core_count,
        work_time,
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

#[cfg(target_os = "windows")]
fn internal_get_ram_info() -> Result<Vec<MemoryInfo>, Box<dyn std::error::Error>> {
    let output = Command::new("powershell")
        .args(&[
            "-Command",
            "Get-CimInstance Win32_PhysicalMemory | Select-Object Speed, MemoryType, SMBIOSMemoryType | ConvertTo-Json -Compress"
        ])
        .output()?;
    
    if !output.status.success() {
        return Err("PowerShell command failed".into());
    }
    
    let output_str = String::from_utf8_lossy(&output.stdout);
    let json_str = if output_str.trim_start().starts_with('[') {
        output_str.to_string()
    } else {
        format!("[{}]", output_str)
    };
    
    let memories: Vec<Win32PhysicalMemory> = serde_json::from_str(&json_str)?;
    
    let mem_info: Vec<MemoryInfo> = memories.into_iter().map(|m| {
        let fmt = get_modern_memory_format(m.smbios_memory_type, m.memory_type);
        let format_cstr = CString::new(fmt).unwrap();
        MemoryInfo { speed: m.speed, memory_format: format_cstr.into_raw() }
    }).collect();
    
    Ok(mem_info)
}

#[cfg(target_os = "windows")]
#[no_mangle]
pub extern "C" fn get_ram_info_array() -> MemoryInfoArray {
    match internal_get_ram_info() {
        Ok(mut vec) => {
            let len = vec.len();
            let data_ptr = vec.as_mut_ptr();
            std::mem::forget(vec);
            MemoryInfoArray { data: data_ptr, len }
        },
        Err(_) => MemoryInfoArray { data: std::ptr::null_mut(), len: 0 },
    }
}

#[no_mangle]
pub extern "C" fn free_memory_info_array(array: MemoryInfoArray) {
    if array.data.is_null() { return; }
    unsafe {
        let vec = Vec::from_raw_parts(array.data, array.len, array.len);
        for mem in vec {
            if !mem.memory_format.is_null() {
                let _ = CString::from_raw(mem.memory_format);
            }
        }
    }
}

fn get_modern_memory_format(smbios: Option<u32>, memory_type: Option<u32>) -> &'static str {
    if let Some(smbios_val) = smbios {
        if smbios_val != 0 {
            match smbios_val {
                20 => "DDR",
                21 => "DDR2",
                22 => "DDR2 FB-DIMM",
                24 => "DDR3",
                26 => "DDR4",
                34 => "DDR5",
                _  => "Unknown",
            }
        } else {
            if let Some(mem_val) = memory_type {
                match mem_val {
                    20 => "DDR",
                    21 => "DDR2",
                    22 => "DDR2 FB-DIMM",
                    24 => "DDR3",
                    _  => "Unknown",
                }
            } else {
                "Unknown"
            }
        }
    } else {
        if let Some(mem_val) = memory_type {
            match mem_val {
                20 => "DDR",
                21 => "DDR2",
                22 => "DDR2 FB-DIMM",
                24 => "DDR3",
                _  => "Unknown",
            }
        } else {
            "Unknown"
        }
    }
}

#[no_mangle]
pub extern "C" fn get_memory_static_info() -> MemoryStaticInfo {
    let mut sys = System::new_all();
    sys.refresh_all();
    // Пример значений: скорость 2400 МГц и формата DDR4 (используем smbios = Some(26))
    let mem_speed = 2400;
    let mem_format_str = get_modern_memory_format(Some(26), None);
    let mem_format = CString::new(mem_format_str).unwrap();
    MemoryStaticInfo {
        total: sys.total_memory() / (1024 * 1024 * 1024),      // перевод из КБ в ГБ
        used: sys.used_memory() / (1024 * 1024 * 1024),          // перевод из КБ в ГБ
        available: sys.available_memory() / (1024 * 1024 * 1024),// перевод из КБ в ГБ
        speed: mem_speed,
        format: mem_format.into_raw(),
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

#[no_mangle]
pub extern "C" fn get_networks_static_info_array() -> NetworksStaticInfoArray {
    let mut sys = System::new_all();
    sys.refresh_all();  // Обновляем все данные
    sys.refresh_networks();
    sys.refresh_networks_list();
    let networks = sys.networks();
    
    let mut vec: Vec<NetworksStaticInfo> = Vec::new();
    let local_ip = local_ipaddress::get().unwrap_or("0.0.0.0".to_string());
    
    for (iface_name, network) in networks {
        // Пропускаем виртуальные и неактивные интерфейсы
        if iface_name.contains("vEthernet") || 
           iface_name.contains("VirtualBox") || 
           iface_name.contains("VMware") ||
           iface_name.contains("Loopback") {
            continue;
        }
        
        // Получаем текущие значения
        let transmitted = network.transmitted();
        let received = network.received();
        
        // Если интерфейс активен (есть хоть какой-то трафик)
        if transmitted > 0 || received > 0 {
            let name = iface_name.to_string();
            vec.push(NetworksStaticInfo {
                name: CString::new(name).unwrap().into_raw(),
                ipv4: CString::new(local_ip.clone()).unwrap().into_raw(),
                send: transmitted,
                recive: received,
            });
        }
    }
    
    let len = vec.len();
    let data_ptr = vec.as_mut_ptr();
    std::mem::forget(vec);
    NetworksStaticInfoArray { data: data_ptr, len }
}

#[no_mangle]
pub extern "C" fn free_networks_static_info_array(array: NetworksStaticInfoArray) {
    if array.data.is_null() {
        return;
    }
    unsafe {
        let vec = Vec::from_raw_parts(array.data, array.len, array.len);
        for network in vec {
            if !network.name.is_null() {
                let _ = CString::from_raw(network.name);
            }
            if !network.ipv4.is_null() {
                let _ = CString::from_raw(network.ipv4);
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
//ДЛЯ WINDOWS
//ВАНЯ, допиши выше зависимости и добавь их в cargo.toml. Функцию
#[unsafe(no_mangle)] 
pub extern "C" fn kill_process(pid: u32) -> i32 {
    unsafe {
        let process_handle: HANDLE = OpenProcess(PROCESS_TERMINATE, 0, pid);
        if process_handle.is_null() {
            return -1;  // Ошибка: не удалось открыть процесс
        }

        // Завершаем процесс
        if TerminateProcess(process_handle, 1) == 0 {
            CloseHandle(process_handle); 
            return -2;  // Ошибка: не удалось завершить процесс
        }

        CloseHandle(process_handle);
        return 0;
    }
}

#[no_mangle]
pub extern "C" fn get_proc_path(pid: u32) -> *const c_char {
    let mut filename: [u16; 260] = [0; 260];

    let process_handle: HANDLE = unsafe {
        OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 0, pid)
    };

    if process_handle.is_null() {
        return ptr::null();
    }

    let result = unsafe {
        GetModuleFileNameExW(process_handle, ptr::null_mut(), filename.as_mut_ptr(), filename.len() as u32)
    };

    unsafe { CloseHandle(process_handle) };

    if result == 0 {
        return ptr::null();
    }

    // Convert to UTF-16 string and then to CString
    let filename_osstr = OsString::from_wide(&filename[..result as usize]);
    let path = filename_osstr.to_string_lossy().into_owned();
    
    match CString::new(path) {
        Ok(c_string) => c_string.into_raw(), // Transfer ownership to caller
        Err(_) => ptr::null(),
    }

//ДЛЯ MAC OS
/// Функция для завершения процесса по идентификатору.
// #[no_mangle]
// pub extern "C" fn kill_process(pid: u32) -> i32 {
//     let result = unsafe { libc::kill(pid as libc::pid_t, libc::SIGKILL) };
//     if result == 0 {
//         0 
//     } else {
//         -1 
//     }
// }

#[cfg(target_os = "windows")]
#[no_mangle]
pub extern "C" fn get_services_info_array() -> ServiceInfoArray {
    let output = Command::new("powershell")
        .args(&[
            "-Command",
            "Get-CimInstance Win32_Service | Select-Object ProcessId, Name, Status | ConvertTo-Json -Compress"
        ])
        .output()
        .expect("Не удалось выполнить команду PowerShell");

    if output.status.success() {
        let output_str = String::from_utf8_lossy(&output.stdout);
        let services: Vec<serde_json::Value> = serde_json::from_str(&output_str)
            .expect("Не удалось распарсить JSON");
        let len = services.len();
        let mut vec: Vec<ServiceInfo> = Vec::with_capacity(len);
        for service in services {
            let process_id = service["ProcessId"].as_u64().unwrap_or(0) as u32;
            let name_str = service["Name"].as_str().unwrap_or("Unknown").to_string();
            let status_str = service["Status"].as_str().unwrap_or("Unknown").to_string();
            let c_name = CString::new(name_str).unwrap().into_raw();
            let c_status = CString::new(status_str).unwrap().into_raw();
            vec.push(ServiceInfo {
                process_id,
                name: c_name,
                status: c_status,
            });
        }
        let data_ptr = vec.as_mut_ptr();
        std::mem::forget(vec);
        ServiceInfoArray { data: data_ptr, len }
    } else {
        ServiceInfoArray { data: std::ptr::null_mut(), len: 0 }
    }
}

#[cfg(target_os = "windows")]
#[no_mangle]
pub extern "C" fn free_services_info_array(array: ServiceInfoArray) {
    if array.data.is_null() {
        return;
    }
    unsafe {
        let vec = Vec::from_raw_parts(array.data, array.len, array.len);
        for service in vec {
            if !service.name.is_null() {
                let _ = CString::from_raw(service.name);
            }
            if !service.status.is_null() {
                let _ = CString::from_raw(service.status);
            }
        }
    }
}
/// Функция для освобождения памяти, выделенной функциями, возвращающими C‑строку.
#[no_mangle]
pub extern "C" fn free_string(s: *mut c_char) {
    if s.is_null() { return; }
    unsafe { let _ = CString::from_raw(s); }
}
