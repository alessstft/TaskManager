use sysinfo::{System, SystemExt, CpuExt};
use std::ffi::{CString, CStr};
use std::os::raw::c_char;

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
    // Преобразуем строку в CString и передаём владение через into_raw()
    CString::new(cpu_name).unwrap().into_raw()
}

/// Функция для освобождения памяти, выделенной в get_cpu_name.
#[no_mangle]
pub extern "C" fn free_string(s: *mut c_char) {
    if s.is_null() { return; }
    // Освобождение памяти, возвращая CString во владение Rust
    unsafe { CString::from_raw(s); }
}
