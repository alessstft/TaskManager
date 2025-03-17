use sysinfo::{System, SystemExt, CpuExt, DiskExt, NetworkExt, ComponentExt, ProcessExt};
use local_ipaddress;
use std::process::Command;
use serde::Deserialize;
use serde_json;
use std::io;

// ==================== RAM ====================
struct MemoryInfo {
    speed: Option<u32>,
    memory_format: Option<String>,
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

//
// Реализация для Windows
//
#[cfg(target_os = "windows")]
#[derive(Deserialize, Debug)]
struct Win32PhysicalMemory {
    #[serde(rename = "Speed")]
    speed: Option<u32>,
    #[serde(rename = "MemoryType")]
    memory_type: Option<u32>,
    #[serde(rename = "SMBIOSMemoryType")]
    smbios_memory_type: Option<u32>,
}

#[cfg(target_os = "windows")]
fn get_ram_info() -> Result<Vec<MemoryInfo>, Box<dyn std::error::Error>> {
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
        let format = Some(get_modern_memory_format(m.smbios_memory_type, m.memory_type).to_string());
        MemoryInfo { speed: m.speed, memory_format: format }
    }).collect();
    
    Ok(mem_info)
}

//
// Реализация для macOS
//
#[cfg(target_os = "macos")]
fn get_ram_info() -> Result<Vec<MemoryInfo>, Box<dyn std::error::Error>> {
    let output = Command::new("system_profiler")
        .args(&["SPMemoryDataType"])
        .output()?;
    
    if !output.status.success() {
        return Err("system_profiler command failed".into());
    }
    
    let output_str = String::from_utf8_lossy(&output.stdout);
    let mut infos = Vec::new();
    let mut current_speed: Option<u32> = None;
    let mut current_type: Option<String> = None;
    
    for line in output_str.lines() {
        let line = line.trim();
        if line.is_empty() {
            if current_speed.is_some() || current_type.is_some() {
                infos.push(MemoryInfo { speed: current_speed, memory_format: current_type.clone() });
                current_speed = None;
                current_type = None;
            }
            continue;
        }
        if line.starts_with("Speed:") {
            let value = line.trim_start_matches("Speed:").trim().replace("MHz", "").trim().to_string();
            if let Ok(num) = value.parse::<u32>() {
                current_speed = Some(num);
            }
        } else if line.starts_with("Type:") {
            let mem_type = line.trim_start_matches("Type:").trim();
            current_type = Some(mem_type.to_string());
        }
    }
    if current_speed.is_some() || current_type.is_some() {
        infos.push(MemoryInfo { speed: current_speed, memory_format: current_type });
    }
    
    Ok(infos)
}

//
// Для остальных ОС
//
#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn get_ram_info() -> Result<Vec<MemoryInfo>, Box<dyn std::error::Error>> {
    Err("Unsupported OS".into())
}

// ==================== GPU ====================

struct GPUInfo {
    model: String,
    total_memory: Option<f64>, // в ГБ
    used_memory: Option<f64>,  // в ГБ
    free_memory: Option<f64>,  // в ГБ
    temperature: Option<u32>,  // в °C
}

/// Пытаемся получить информацию о GPU через nvidia-smi (для NVIDIA‑графики).
fn get_gpu_info() -> Result<Vec<GPUInfo>, Box<dyn std::error::Error>> {
    let output = Command::new("nvidia-smi")
        .args(&[
            "--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu",
            "--format=csv,noheader,nounits",
        ])
        .output();

    if let Ok(output) = output {
        if output.status.success() {
            let output_str = String::from_utf8_lossy(&output.stdout);
            let mut gpus = Vec::new();
            for line in output_str.lines() {
                let parts: Vec<&str> = line.split(',').map(|s| s.trim()).collect();
                if parts.len() == 5 {
                    let model = parts[0].to_string();
                    let total: f64 = parts[1].parse().unwrap_or(0.0);
                    let used: f64 = parts[2].parse().unwrap_or(0.0);
                    let free: f64 = parts[3].parse().unwrap_or(0.0);
                    let temperature: u32 = parts[4].parse().unwrap_or(0);
                    // Переводим из MB в ГБ
                    gpus.push(GPUInfo {
                        model,
                        total_memory: Some(total / 1024.0),
                        used_memory: Some(used / 1024.0),
                        free_memory: Some(free / 1024.0),
                        temperature: Some(temperature),
                    });
                }
            }
            if !gpus.is_empty() {
                return Ok(gpus);
            }
        }
    }
    
    Err("nvidia-smi не найден или вернул ошибку".into())
}

#[cfg(target_os = "windows")]
fn get_integrated_gpu_model_windows() -> Result<String, Box<dyn std::error::Error>> {
    let output = Command::new("wmic")
        .args(&["path", "win32_VideoController", "get", "Name"])
        .output()?;
    if output.status.success() {
        let output_str = String::from_utf8_lossy(&output.stdout);
        let mut lines = output_str.lines();
        // Пропускаем заголовок
        lines.next();
        if let Some(name) = lines.next() {
            let name = name.trim();
            if !name.is_empty() {
                return Ok(name.to_string());
            }
        }
    }
    Err("Информация о встроенной графике не найдена".into())
}


#[cfg(target_os = "windows")]
fn get_cpu_integrated_gpu_model_windows() -> Result<String, Box<dyn std::error::Error>> {
    let output = Command::new("wmic")
        .args(&["path", "win32_VideoController", "get", "Name"])
        .output()?;
    let output_str = String::from_utf8_lossy(&output.stdout);
    // Пропускаем заголовок
    for line in output_str.lines().skip(1) {
        let name = line.trim();
        if !name.is_empty() &&
           (name.to_lowercase().contains("intel") ||
            name.to_lowercase().contains("amd") ||
            name.to_lowercase().contains("uhd"))
        {
            return Ok(name.to_string());
        }
    }
    Err("Интегрированная видеокарта в процессоре не найдена".into())
}

#[cfg(target_os = "linux")]
fn get_cpu_integrated_gpu_model_linux() -> Result<String, Box<dyn std::error::Error>> {
    let output = Command::new("lspci").output()?;
    let output_str = String::from_utf8_lossy(&output.stdout);
    for line in output_str.lines() {
        if line.contains("VGA compatible controller") &&
           (line.to_lowercase().contains("intel") || line.to_lowercase().contains("amd"))
        {
            return Ok(line.to_string());
        }
    }
    Err("Интегрированная видеокарта в процессоре не найдена".into())
}

#[cfg(target_os = "macos")]
fn get_cpu_integrated_gpu_model_macos() -> Result<String, Box<dyn std::error::Error>> {
    let output = Command::new("system_profiler")
        .args(&["SPDisplaysDataType"])
        .output()?;
    if output.status.success() {
        let output_str = String::from_utf8_lossy(&output.stdout);
        for line in output_str.lines() {
            if line.contains("Chipset Model:") {
                let model = line.trim().trim_start_matches("Chipset Model:").trim();
                if model.to_lowercase().contains("intel") ||
                   model.to_lowercase().contains("amd")
                {
                    return Ok(model.to_string());
                }
            }
        }
    }
    Err("Интегрированная видеокарта в процессоре не найдена".into())
}



// ==================== Main ====================
fn main() {
    let mut sys = System::new_all();
    sys.refresh_all();
    
    println!("🔥 Система проанализирована! Вот что удалось узнать: 🔥");

    println!("\n💻 Процессор:");
    if let Some(cpu) = sys.cpus().first() {
        println!("   🏷 Наименование: {}", cpu.brand());
        println!("   📊 Использование: {:.2}%", cpu.cpu_usage());
        println!("   🚀 Скорость: {:.2} ГГц", cpu.frequency() as f64 / 1000.0);
        println!("   ⚙️ Процессов: {}", sys.processes().len());
        println!("   🔄 Потоков: {}", sys.cpus().len());
        println!("   ⏳ Время работы: {} сек", sys.uptime());
    }
    println!("   🌡 Температура процессора:");
    for comp in sys.components() {
        if comp.label().to_lowercase().contains("cpu") {
            println!("     {}: {:.2}°C", comp.label(), comp.temperature());
        }
    }

    println!("\n🛠 Оперативная память:");
    println!("   👀 Всего: {:.2} ГБ", sys.total_memory() as f64 / (1024.0 * 1024.0 * 1024.0));
    println!("   📊 Используемая: {:.2} ГБ", sys.used_memory() as f64 / (1024.0 * 1024.0 * 1024.0));
    println!("   🟢 Доступно: {:.2} ГБ", sys.available_memory() as f64 / (1024.0 * 1024.0 * 1024.0));

    
    match get_ram_info() {
        Ok(mem_infos) => {
            if mem_infos.is_empty() {
                println!("   ⚡ Скорость: Неизвестно");
                println!("   🧩 Формат: Неизвестно");
            } else {
                let mut speeds: Vec<String> = Vec::new();
                let mut formats: Vec<String> = Vec::new();
                for info in mem_infos {
                    if let Some(s) = info.speed {
                        speeds.push(format!("{} MHz", s));
                    }
                    if let Some(fmt) = info.memory_format {
                        formats.push(fmt);
                    }
                }
                if !speeds.is_empty() {
                    println!("   ⚡ Скорость: {}", speeds.join(", "));
                } else {
                    println!("   ⚡ Скорость: Неизвестно");
                }
                if !formats.is_empty() {
                    println!("   🧩 Формат: {}", formats.join(", "));
                } else {
                    println!("   🧩 Формат: Неизвестно");
                }
            }
        },
        Err(e) => {
            println!("   ⚡ Скорость: Ошибка получения данных ({})", e);
            println!("   🧩 Формат: Ошибка получения данных");
        }
    }

    println!("\n💾 Диски:");
    for disk in sys.disks() {
        println!("   📀 Наименование: {:?}", disk.name());
        println!("   💾 Емкость: {} ГБ", disk.total_space() / (1024 * 1024 * 1024));
        println!("   🆓 Свободно: {} ГБ", disk.available_space() / (1024 * 1024 * 1024));
    }

    println!("\n🌐 Сетевые интерфейсы:");
    for (interface_name, data) in sys.networks() {
        println!("   🔌 Наименование: {}", interface_name);
        println!("   📡 Отправка: {} Кбит/с", data.total_transmitted() / 1024);
        println!("   📥 Получение: {} Кбит/с", data.total_received() / 1024);
    }

    match local_ipaddress::get() {
        Some(ip) => println!("   🌍 IPv4-адрес: {}", ip),
        None => println!("   ❌ IPv4-адрес не найден."),
    }
    println!("   🌍 IPv6-адрес: (не поддерживается sysinfo)");

    // ==================== Интеграция GPU ====================
    println!("\n🎮 Видеокарта:");
    // Сначала пытаемся получить информацию о дискретной GPU через nvidia-smi
    if let Ok(gpus) = get_gpu_info() {
        for gpu in gpus {
            println!("   🏷 Наименование: {}", gpu.model);
            if let Some(total) = gpu.total_memory {
                println!("   🎮 Общий объём памяти: {:.2} ГБ", total);
            } else {
                println!("   🎮 Кол-во памяти: (не поддерживается напрямую)");
            }
            if let Some(used) = gpu.used_memory {
                println!("   📊 Выделено памяти: {:.2} ГБ", used);
            } else {
                println!("   📊 Выделено памяти: (не поддерживается напрямую)");
            }
            if let Some(free) = gpu.free_memory {
                println!("   🆓 Осталось: {:.2} ГБ", free);
            } else {
                println!("   🆓 Осталось: (не поддерживается напрямую)");
            }
            if let Some(temp) = gpu.temperature {
                println!("   🌡 Температура: {}°C", temp);
            } else {
                println!("   🌡 Температура: (не поддерживается напрямую)");
            }
        }
    } else {
        // Если дискретная GPU не найдена, пробуем получить модель встроенной графики
        #[cfg(target_os = "windows")]
        {
            match get_integrated_gpu_model_windows() {
                Ok(model) => {
                    println!("   🏷 Наименование: {}", model);
                    println!("   🎮 Кол-во памяти: (не поддерживается напрямую)");
                    println!("   📊 Выделено памяти: (не поддерживается напрямую)");
                    println!("   🆓 Осталось: (не поддерживается напрямую)");
                },
                Err(_) => println!("   ❌ Информация о видеокарте не найдена."),
            }
        }
        #[cfg(target_os = "linux")]
        {
            match get_integrated_gpu_model_linux() {
                Ok(model) => {
                    println!("   🏷 Наименование: {}", model);
                    println!("   🎮 Кол-во памяти: (не поддерживается напрямую)");
                    println!("   📊 Выделено памяти: (не поддерживается напрямую)");
                    println!("   🆓 Осталось: (не поддерживается напрямую)");
                },
                Err(_) => println!("   ❌ Информация о видеокарте не найдена."),
            }
        }
        #[cfg(target_os = "macos")]
        {
            match get_cpu_integrated_gpu_model_macos() {
                Ok(model) => {
                    println!("   🏷 Наименование: {}", model);
                    println!("   🎮 Кол-во памяти: (не поддерживается напрямую)");
                    println!("   📊 Выделено памяти: (не поддерживается напрямую)");
                    println!("   🆓 Осталось: (не поддерживается напрямую)");
                },
                Err(_) => println!("   ❌ Информация о видеокарте не найдена."),
            }
        }
    }

    // Если дискретная GPU не найдена или требуется дополнительно отобразить информацию об интегрированной графике в процессоре
    #[cfg(target_os = "windows")]
    {
        match get_cpu_integrated_gpu_model_windows() {
            Ok(model) => {
                println!("   🏷 Интегрированная видеокарта (CPU): {}", model);
                println!("   🎮 Кол-во памяти: (не поддерживается напрямую)");
                println!("   📊 Выделено памяти: (не поддерживается напрямую)");
                println!("   🆓 Осталось: (не поддерживается напрямую)");
            },
            Err(e) => println!("   ❌ Информация о видеокарте (CPU) не найдена: {}", e),
        }
    }

    #[cfg(target_os = "linux")]
    {
        match get_cpu_integrated_gpu_model_linux() {
            Ok(model) => {
                println!("   🏷 Интегрированная видеокарта (CPU): {}", model);
                println!("   🎮 Кол-во памяти: (не поддерживается напрямую)");
                println!("   📊 Выделено памяти: (не поддерживается напрямую)");
                println!("   🆓 Осталось: (не поддерживается напрямую)");
            },
            Err(e) => println!("   ❌ Информация о видеокарте (CPU) не найдена: {}", e),
        }
    }

    #[cfg(target_os = "macos")]
    {
        match get_cpu_integrated_gpu_model_macos() {
            Ok(model) => {
                println!("   🏷 Интегрированная видеокарта (CPU): {}", model);
                println!("   🎮 Кол-во памяти: (не поддерживается напрямую)");
                println!("   📊 Выделено памяти: (не поддерживается напрямую)");
                println!("   🆓 Осталось: (не поддерживается напрямую)");
            },
            Err(e) => println!("   ❌ Информация о видеокарте (CPU) не найдена: {}", e),
        }
    }

    println!("\nПроцессы:");
    let mut processes: Vec<_> = sys.processes().iter().collect();
    processes.sort_by(|a, b| b.1.cpu_usage().partial_cmp(&a.1.cpu_usage()).unwrap());
    for (pid, process) in processes.iter().take(15) {
        let disk_usage = process.disk_usage();
        println!(
            "[{}] {}: {:.2}% CPU, {:.2} MB RAM, {:.2} KB чтение, {:.2} KB запись",
            pid,
            process.name(),
            process.cpu_usage(),
            process.memory() as f64 / (1024.0 * 1024.0),
            disk_usage.total_read_bytes as f64 / (1024.0 * 1024.0),
            disk_usage.total_written_bytes as f64 / (1024.0 * 1024.0)
        );
    }

    println!("\nСистемные службы:");
    #[cfg(target_os = "windows")]
    {    
        let output = Command::new("powershell")
            .args(&[
                "-Command",
                "Get-CimInstance Win32_Service | Select-Object ProcessId, Name, Status | ConvertTo-Json -Compress"
            ])
            .output()
            .expect("Не удалось выполнить команду PowerShell");
    
        if output.status.success() {
            let output_str = String::from_utf8_lossy(&output.stdout);
            let services: Vec<serde_json::Value> = serde_json::from_str(&output_str).expect("Не удалось распарсить JSON");
            for service in services {
                println!("   [{}] {}: {}", service["ProcessId"], service["Name"], service["Status"]);
            }
        } else {
            println!("   ❌ Не удалось получить информацию о службах.");
        }
    }

    #[cfg(target_os = "linux")]
    {
        let output = Command::new("systemctl")
            .args(&["list-units", "--type=service", "--no-pager", "--plain", "--no-legend"])
            .output()
            .expect("Не удалось выполнить команду systemctl");
    
        if output.status.success() {
            let output_str = String::from_utf8_lossy(&output.stdout);
            for line in output_str.lines() {
                let parts: Vec<&str> = line.split_whitespace().collect();
                if parts.len() > 3 {
                    // PID не доступен напрямую, поэтому выводим [N/A]
                    println!("   [N/A] {}: {}", parts[0], parts[3]);
                }
            }
        } else {
            println!("   ❌ Не удалось получить информацию о службах.");
        }
    }

    #[cfg(target_os = "macos")]
    {
        let output = Command::new("launchctl")
            .args(&["list"])
            .output()
            .expect("Не удалось выполнить команду launchctl");
        
        if output.status.success() {
            let output_str = String::from_utf8_lossy(&output.stdout);
            for line in output_str.lines().skip(1) { // Пропускаем заголовок
                let parts: Vec<&str> = line.split_whitespace().collect();
                if parts.len() > 2 {
                    println!("   [{}] {}:", parts[0], parts[2]);
                }
            }
        } else {
            println!("   ❌ Не удалось получить информацию о службах.");
        }
    }
    
    println!("\n🔥 ВСЁ, СИСТЕМА ПРОАНАЛИЗИРОВАНА НА 100%! 🚀");

    println!("\nНажмите Enter, чтобы закрыть программу...");
    let mut input = String::new();
    io::stdin().read_line(&mut input).expect("Не удалось прочитать ввод");
}

