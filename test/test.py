import ctypes
import json

#Вставть свой путь к DLL. Для windows .dll, для mac os .dylib
lib_path = "/Users/sip/Yandex.Disk.localized/Learning/Тестирование программных модулей/Менеджер задач/sys_info_fn/target/release/libsys_info_fn.dylib"
lib = ctypes.CDLL(lib_path)

# Настраиваем типы возвращаемых значений для каждой функции
lib.get_cpu_name.restype = ctypes.c_char_p
lib.get_cpu_usage_info.restype = ctypes.c_char_p
lib.get_cpu_frequency.restype = ctypes.c_double
lib.get_process_count.restype = ctypes.c_size_t
lib.get_cpu_count.restype = ctypes.c_size_t
lib.get_uptime.restype = ctypes.c_ulonglong
lib.get_all_processes_json.restype = ctypes.c_char_p

# Вызываем функции и выводим результаты
cpu_name_ptr = lib.get_cpu_name()
cpu_name = cpu_name_ptr.decode("utf-8") if cpu_name_ptr is not None else "NULL"
print("Наименование процессора:", cpu_name)

cpu_usage_ptr = lib.get_cpu_usage_info()
cpu_usage = cpu_usage_ptr.decode("utf-8") if cpu_usage_ptr is not None else "NULL"
print("Использование процессора:", cpu_usage)

cpu_frequency = lib.get_cpu_frequency()
print("Скорость процессора: {:.2f} ГГц".format(cpu_frequency))

process_count = lib.get_process_count()
print("Количество процессов:", process_count)

cpu_count = lib.get_cpu_count()
print("Количество потоков:", cpu_count)

uptime = lib.get_uptime()
print("Время работы системы:", uptime, "сек")


proc_ptr = lib.get_all_processes_json()
proc_json = proc_ptr.decode("utf-8")
processes = json.loads(proc_json)

print("Список процессов:")
for proc in processes:
    print(proc)

lib.free_string.argtypes = [ctypes.c_char_p]
lib.free_string(proc_ptr)
