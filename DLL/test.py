import ctypes
import os
import sys

# Определяем имя библиотеки в зависимости от ОС
if sys.platform.startswith('win'):
    libname = 'sys_info.dll'
elif sys.platform.startswith('darwin'):
    libname = 'libsys_info.dylib'
else:
    libname = 'libsys_info.so'

# Укажите корректный путь к библиотеке, например, абсолютный путь или относительно файла test.py
lib_path = "G:/Мой диск/projects/Тестирование программных модулей/Менеджер задач/sys_info_fn/target/release/sys_info_fn.dll"
lib = ctypes.CDLL(lib_path)

# Указываем, что функция get_cpu_name возвращает указатель на char
lib.get_cpu_name.restype = ctypes.c_char_p

# Вызываем функцию для получения названия процессора
cpu_name_ptr = lib.get_cpu_name()
cpu_name = cpu_name_ptr.decode("utf-8")
print("Наименование процессора:", cpu_name)

# Освобождаем выделенную память, вызывая функцию free_string
lib.free_string.argtypes = [ctypes.c_char_p]
lib.free_string(cpu_name_ptr)
