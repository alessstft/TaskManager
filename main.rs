use sysinfo::{System, SystemExt, CpuExt, DiskExt, NetworkExt, ComponentExt,ProcessExt};
use local_ipaddress;
use std::process::Command;
use serde::Deserialize;
use serde_json;
use std::io;

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
    
    // Пробегаем по строкам вывода system_profiler
    for line in output_str.lines() {
        let line = line.trim();
        if line.is_empty() {
            // При разделении блоков памяти, если найдены данные — сохраняем их
            if current_speed.is_some() || current_type.is_some() {
                infos.push(MemoryInfo { speed: current_speed, memory_format: current_type.clone() });
                current_speed = None;
                current_type = None;
            }
            continue;
        }
        // Ищем строку с информацией о скорости
        if line.starts_with("Speed:") {
            // Пример строки: "Speed: 2400 MHz"
            let value = line.trim_start_matches("Speed:").trim();
            let value = value.replace("MHz", "").trim().to_string();
            if let Ok(num) = value.parse::<u32>() {
                current_speed = Some(num);
            }
        } else if line.starts_with("Type:") {
            // Пример строки: "Type: DDR4"
            let mem_type = line.trim_start_matches("Type:").trim();
            current_type = Some(mem_type.to_string());
        }
    }
    // Если последний блок не был завершён пустой строкой, добавляем его
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

    println!("\n🎮 Видеокарта:");
    if let Some(gpu) = sys.components().iter().find(|c| c.label().contains("GPU")) {
        println!("   🏷 Наименование: {}", gpu.label());
        println!("   🎮 Кол-во памяти: (не поддерживается напрямую)");
        println!("   📊 Выделено памяти: (не поддерживается напрямую)");
        println!("   🆓 Осталось: (не поддерживается напрямую)");
    } else {
        println!("   ❌ Информация о видеокарте не найдена.");
    }

    println!("\nПроцессы:");
        let mut processes: Vec<_> = sys.processes().iter().collect();
        processes.sort_by(|a, b| b.1.cpu_usage().partial_cmp(&a.1.cpu_usage()).unwrap());
        for (pid, process) in processes.iter().take(5) {
            println!("[{}] {}: {:.2}% CPU", pid, process.name(), process.cpu_usage());
        }

    println!("\n🔥 ВСЁ, СИСТЕМА ПРОАНАЛИЗИРОВАНА НА 100%! 🚀");

    println!("\nНажмите Enter, чтобы закрыть программу...");
    let mut input = String::new();
    io::stdin().read_line(&mut input).expect("Не удалось прочитать ввод");
}
