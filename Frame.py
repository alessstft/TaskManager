import tkinter as tk
from tkinter import ttk, Canvas, messagebox, Menu
from collections import deque
import threading
import time
from system_monitor import SystemMonitor
import ctypes
import os

class PerformanceTab(tk.Frame):
    def __init__(self, parent, system_monitor=None):
        super().__init__(parent)
        self.system_monitor = system_monitor  
        self._data_lock = threading.Lock()
        self._update_lock = threading.Lock()
        self.is_dark_theme = parent.is_dark_theme if hasattr(parent, 'is_dark_theme') else False
        self.init_data()
        self.init_ui()
        
    def init_data(self):
        self.values = {
            'cpu': deque(maxlen=60),
            'memory': deque(maxlen=60),
            'disk': deque(maxlen=60),
            'network': deque(maxlen=60)
        }
        self.speeds = {
            'disk': 0.0,
            'network': 0.0
        }
        self.current_metric = 'cpu'
        self._prev_values = {}
        self._last_update = 0
        self._update_interval = 0.5
        self._prev_disk_info = None
        self._last_disk_update = time.time()
        self._prev_network_info = None
        self._last_network_update = time.time()

    def init_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Левая панель с кнопками метрик
        left_panel = tk.Frame(self, bg='#2d2d2d', width=200)
        left_panel.grid(row=0, column=0, sticky='ns')
        left_panel.grid_propagate(False)
        

        metrics = {
            'cpu': ('ЦП', '#3794ff'),
            'memory': ('Память', '#ff4a4a'),
            'disk': ('Диск', '#4aff4a'),
            'network': ('Ethernet', '#ffd700')
        }
        
        for i, (metric, (name, color)) in enumerate(metrics.items()):
            btn = tk.Button(
                left_panel, 
                text=name,
                bg='#2d2d2d',
                fg='white',
                activeforeground='black',
                borderwidth=7, 
                relief='flat',
                highlightthickness=0,
                command=lambda m=metric: self.switch_metric(m)
            )

            btn.bind("<Enter>", lambda e, b=btn, c=color: b.config(bg=c))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg='#2d2d2d'))
            btn.bind("<Button-1>", lambda e, b=btn, c=color: b.config(bg=c))
            btn.bind("<Button-1>", lambda e, b=btn, c=color: b.config(bg=self.dark_color(c)))
            btn.grid(row=i, column=0, sticky='ew', padx=4, pady=4, ipadx=60, ipady=6)
        
        # Правая панель с графиком и деталями
        right_panel = tk.Frame(self, bg='#1e1e1e')
        right_panel.grid(row=0, column=1, sticky='nsew')
        
        # График
        self.chart_title = tk.Label(right_panel, text="ЦП", bg='#1e1e1e', fg='white', 
                                   font=('Arial', 28, 'bold'))
        self.chart_title.pack(anchor='w', padx=10, pady=(10, 0))
        
        self.canvas = tk.Canvas(right_panel, bg='#1e1e1e', highlightthickness=0, height=250)
        self.canvas.pack(fill='x', expand=False, padx=10, pady=10)
        
        # Информационные метки
        info_frame = tk.Frame(right_panel, bg='#1e1e1e')
        #info_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        # Создаем контейнер для меток
        self.info_labels_container = tk.Frame(info_frame, bg='#1e1e1e')
        self.info_labels_container.pack(fill='x', expand=True)
        
        self.info_labels = {}
        labels = [
            ("Использование", "0%"),
            ("Скорость", "0.00"),
            ("Процессы", "0"),
            ("Потоки", "0"),
            ("Время работы", "0:00:00")
        ]
        
        for i, (name, value) in enumerate(labels):
            frame = tk.Frame(self.info_labels_container, bg='#1e1e1e')
            frame.grid(row=0, column=i, padx=15, sticky='w')
            
            tk.Label(frame, text=name, bg='#1e1e1e', fg='#aaaaaa').pack(anchor='w')
            self.info_labels[name] = tk.Label(frame, text=value, bg='#1e1e1e', fg='white')
            self.info_labels[name].pack(anchor='w')

        # Создаем фреймы для деталей каждой метрики
        self.detail_frames = {}
        for metric in ['cpu', 'memory', 'disk', 'network']:
            frame = tk.Frame(right_panel, bg='#1e1e1e', highlightbackground="#3c3c3c", highlightthickness=1)
            header = tk.Label(frame, font=("Arial", 12, "bold"), bg="#1e1e1e", fg="white")
            header.pack(anchor="w", padx=10, pady=(15, 1))
            
            container = tk.Frame(frame, bg='#1e1e1e')
            container.pack(fill="both", expand=True, padx=5)
            
            self.detail_frames[metric] = {
                'frame': frame,
                'header': header,
                'container': container
            }
        
        # Показываем фрейм CPU по умолчанию
        self.detail_frames['cpu']['frame'].pack(fill='both', expand=True, padx=10, pady=10)
        
        # Инициализируем начальные данные
        if hasattr(self, 'system_monitor') and self.system_monitor is not None:
            self._force_update_all()

    def _force_update_all(self):
        """Принудительно обновляет данные для всех метрик"""
        system_info = {
            'cpu_info': self.system_monitor._get_cpu_info(),
            'memory_info': self.system_monitor._get_memory_info(),
            'disk_info': self.system_monitor.get_disk_info()[0] if self.system_monitor.get_disk_info() else None,
            'network_info': None
        }
        
        # Получаем сетевую информацию безопасно
        network_info = self.system_monitor.get_network_info()
        if network_info and len(network_info) > 0:
            system_info['network_info'] = network_info[0]
        
        # Обновляем все фреймы с деталями
        self._update_cpu_details(system_info)
        self._update_memory_details(system_info)
        self._update_disk_details(system_info)
        self._update_ethernet_details(system_info)

    def switch_metric(self, metric):
        self.current_metric = metric
        colors = {
            'cpu': '#3794ff',
            'memory': '#ff4a4a',
            'disk': '#4aff4a',
            'network': '#ffd700'
        }
        titles = {
            'cpu': 'ЦП',
            'memory': 'Память',
            'disk': 'Диск',
            'network': 'Ethernet'
        }
        self.chart_title.config(text=titles[metric])
        self._current_color = colors[metric]
        self.update_chart()
        
        # Скрываем все фреймы с деталями
        for m in self.detail_frames:
            self.detail_frames[m]['frame'].pack_forget()
        
        # Показываем фрейм для текущей метрики
        self.detail_frames[metric]['frame'].pack(fill='both', expand=True, padx=10, pady=10)
        
        # Принудительно обновляем данные
        self._force_update_all()

    def update_data(self, system_info):
        """Обновляет данные производительности во всех фреймах"""
        if not system_info:
            return
            
        current_time = time.time()
        if current_time - self._last_update < self._update_interval:
            return
            
        with self._data_lock:
            # Сохраняем последние данные системы
            self._last_system_info = system_info
            
            # Вычисляем метрики
            metrics_data = self.calculate_metrics(system_info)
            
            # Обновляем значения для графиков
            for metric, value in metrics_data.items():
                if metric in self.values:
                    self.values[metric].append(float(value))
                    
            # Принудительно обновляем все данные
            self._force_update_all()
            
            # Обновляем метки
            if self.current_metric in metrics_data:
                current_value = metrics_data[self.current_metric]
                self.info_labels["Использование"].config(text=f"{current_value:.1f}%")
                
            # Обновляем количество процессов и потоков
            self.info_labels["Процессы"].config(text=str(system_info.get('process_count', 0)))
            self.info_labels["Потоки"].config(text=str(system_info.get('thread_count', 0)))
            
            # Обновляем время работы
            uptime = system_info.get('uptime', 0)
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)
            seconds = int(uptime % 60)
            self.info_labels["Время работы"].config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            
            # Обновляем график
            self.update_chart()
            
            self._last_update = current_time

    def calculate_metrics(self, system_info):
        """Вычисляет метрики для графиков"""
        try:
            # Получаем текущую информацию о сети
            network_info = self.system_monitor.get_network_info()
            network_metric = 0.0
            
            if network_info and len(network_info) > 0:
                # Суммируем скорости по всем интерфейсам
                total_send = sum(net.get('send_speed', 0) for net in network_info)
                total_recv = sum(net.get('recv_speed', 0) for net in network_info)
                
                # Обновляем информацию в сетевой панели
                net = network_info[0]
                if "Скорость" in self.info_labels:
                    self.info_labels["Скорость"].config(text=f"{(net['send_speed'] + net['recv_speed'])/1024:.1f} КБ/с")
                
                # Конвертируем в Мбит/с (из байт/с)
                total_speed_mbps = (total_send + total_recv) * 8 / 1_000_000
                
                # Масштабируем для графика (100 Мбит/с = 100%)
                network_metric = min(100, total_speed_mbps)
            
            # Получаем актуальные данные CPU и памяти
            cpu_percent = self.system_monitor.get_cpu_percent()
            memory_percent = self.system_monitor.get_memory_percent()
            
            # Получаем информацию о диске
            disk_info = self.system_monitor.get_disk_info()
            disk_percent = 0.0
            if disk_info and len(disk_info) > 0:
                total = disk_info[0]['total_space']
                available = disk_info[0]['available_space']
                if total > 0:
                    disk_percent = ((total - available) / total) * 100
            
            # Обновляем значения для графиков
            self.values['cpu'].append(cpu_percent)
            self.values['memory'].append(memory_percent)
            self.values['disk'].append(disk_percent)
            self.values['network'].append(network_metric)
            
            return {
                'cpu': cpu_percent,
                'memory': memory_percent,
                'disk': disk_percent,
                'network': network_metric
            }
            
        except Exception as e:
            self._metrics = [0] * 4
            return {
                'cpu': 0.0,
                'memory': 0.0,
                'disk': 0.0,
                'network': 0.0
            }
        
    def update_chart(self):
        if not hasattr(self, '_current_color'):
            self._current_color = '#3794ff'
            
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        if width <= 1 or height <= 1:  # Пропускаем обновление если размеры невалидные
            return
            
        self.canvas.delete('all')
        
        # Отступы для графика
        padding_left = 40   # Отступ слева для меток
        padding_right = 10  # Отступ справа
        padding_top = 30    # Увеличили отступ сверху для названия
        padding_bottom = 30 # Отступ снизу для меток времени
        
        # Добавляем название устройства
        device_name = ""
        if self.current_metric == 'disk':
            disk_info = self.system_monitor.get_disk_info()
            if disk_info and len(disk_info) > 0:
                device_name = f"Диск {disk_info[0]['name']}"
        elif self.current_metric == 'network':
            network_info = self.system_monitor.get_network_info()
            if network_info and len(network_info) > 0:
                device_name = network_info[0]['name']
                
        if device_name:
            self.canvas.create_text(
                padding_left,
                padding_top - 15,
                text=device_name,
                fill='white',
                anchor='w',
                font=('Arial', 10, 'bold')
            )
        
        # Рабочая область графика
        chart_width = width - padding_left - padding_right
        chart_height = height - padding_top - padding_bottom
        
        # Цвета для разных метрик
        colors = {
            'cpu': '#3794ff',
            'memory': '#ff4a4a',
            'disk': '#4aff4a',
            'network': '#ffd700'
        }
        self._current_color = colors[self.current_metric]
        
        # Сетка и метки
        for i in range(0, 101, 20):
            y = padding_top + ((100 - i) / 100 * chart_height)
            self.canvas.create_line(
                padding_left, y, 
                width - padding_right, y, 
                fill='#3c3c3c', 
                dash=(2, 4)
            )
            self.canvas.create_text(
                padding_left - 5, y,
                text=f"{i}%",
                fill='white',
                anchor='e'
            )
            
        # Временная шкала
        time_marks = ['50с', '40с', '30с', '20с', '10с', '0с']
        for i, mark in enumerate(time_marks):
            x = padding_left + (i * chart_width / (len(time_marks) - 1))
            self.canvas.create_line(
                x, padding_top,
                x, height - padding_bottom,
                fill='#3c3c3c',
                dash=(2, 4)
            )
            self.canvas.create_text(
                x, height - padding_bottom + 15,
                text=mark,
                fill='white',
                anchor='n'
            )
            
        # График
        values = list(self.values[self.current_metric])
        if values:  # Проверяем, что есть данные для отображения
            points = []
            step = chart_width / 60  # 60 точек данных
            
            for i, value in enumerate(values):
                x = padding_left + (len(values) - i - 1) * step
                value = min(100, max(0, float(value)))
                y = padding_top + ((100 - value) / 100 * chart_height)
                points.extend([x, y])
            
            if len(points) >= 4:  # Минимум 2 точки для создания линии
                # Создаем градиент под линией графика
                gradient_points = points.copy()
                gradient_points.extend([
                    points[-2], height - padding_bottom,
                    points[0], height - padding_bottom
                ])
                
                # Создаем градиент
                fill_color = self._current_color[:-2] + '40'  # Добавляем прозрачность
                self.canvas.create_polygon(gradient_points, fill=fill_color, outline='')
                
                # Рисуем основную линию графика
                self.canvas.create_line(
                    points,
                    fill=self._current_color,
                    width=2,
                    smooth=True
                )
                
                # Добавляем точку текущего значения
                if values:
                    current_x = points[-2]
                    current_y = points[-1]
                    self.canvas.create_oval(
                        current_x - 3, current_y - 3,
                        current_x + 3, current_y + 3,
                        fill=self._current_color,
                        outline='white'
                    )

    def _update_cpu_details(self, system_info):
        """Обновляет панель с детальной информацией о процессоре"""
        if not hasattr(self, 'system_monitor') or self.system_monitor is None:
            return

        cpu_info = self.system_monitor._get_cpu_info()
        
        labels = [
            ("Название", cpu_info['brand']),
            ("Базовая скорость", f"{cpu_info['frequency']:.2f} GHz"),
            ("Ядра", str(cpu_info['core_count'])),
            ("Загруженность", f"{cpu_info['usage']:.1f}%"),
            ("Процессы", str(cpu_info['process_count'])),
            ("Потоки", str(cpu_info['core_count'] * 2)),
            ("Время работы", self._format_uptime(cpu_info['work_time'])),
            ("Виртуализация", "Включено"),
            ("L1 кэш", "384 КБ"),
            ("L2 кэш", "1.5 МБ")
        ]
        
        self._update_details('cpu', "Характеристики ЦП", labels)

    def _update_memory_details(self, system_info):
        """Обновляет панель с детальной информацией о памяти"""
        if not hasattr(self, 'system_monitor') or self.system_monitor is None:
            return  
    
        memory_info = self.system_monitor._get_memory_info()
        total_gb = memory_info['total'] / (1024**3)
        used_gb = memory_info['used'] / (1024**3)
        available_gb = memory_info['available'] / (1024**3)
        cached = (memory_info['total'] - memory_info['available'] - memory_info['used']) / (1024**3)
        
        labels = [
            ("Используется (сжатая)", f"{used_gb:.1f} ГБ"),
            ("Доступно", f"{available_gb:.1f} ГБ"),
            ("Скорость:", f"{memory_info['speed']} МГц"),
            ("Выделено", f"{used_gb:.1f}/{total_gb:.1f} ГБ"),
            ("Кэшировано", f"{cached:.1f} ГБ"),
            ("Использовано гнезд:", f"{memory_info.get('slots_used', 'N/A')}"),
            ("Выгружаемый пул", f"{(memory_info.get('pageable_pool', 0) / (1024**2)):.0f} МБ"),
            ("Невыгружаемый пул", f"{(memory_info.get('non_pageable_pool', 0) / (1024**2)):.0f} МБ"),
            ("Форм-фактор:", memory_info.get('form_factor', 'DIMM')),
            ("Зарезервировано аппаратно:", f"{(memory_info.get('hardware_reserved', 0) / (1024**2)):.1f} МБ")
        ]
        
        self._update_details('memory', "Использование памяти", labels)

    def _update_disk_details(self, system_info):
        """Обновляет панель с детальной информацией о диске"""
        if not hasattr(self, 'system_monitor') or self.system_monitor is None:
            return  

        disk_info = self.system_monitor.get_disk_info()
        if not disk_info or len(disk_info) == 0:
            labels = [
                ("Имя диска", "Не обнаружено"),
                ("Тип диска", "Н/Д"),
                ("Размер", "0.0 ГБ"),
                ("Свободно", "0.0 ГБ"),
                ("Занято", "0.0 ГБ (0%)"),
                ("Файловая система", "Н/Д"),
                ("Состояние", "Н/Д"),
                ("Активность", "0%")
            ]
            self._update_details('disk', "Использование диска", labels)
            return

        disk = disk_info[0]
        total_gb = disk['total_space']
        available_gb = disk['available_space']
        used_gb = total_gb - available_gb
        used_percent = (used_gb / total_gb) * 100 if total_gb > 0 else 0

        labels = [
            ("Имя диска", disk['name']),
            ("Тип диска", "SSD" if "SSD" in disk['name'].upper() else "HDD"),
            ("Размер", f"{total_gb:.1f} ГБ"),
            ("Свободно", f"{available_gb:.1f} ГБ"),
            ("Занято", f"{used_gb:.1f} ГБ ({used_percent:.1f}%)"),
            ("Файловая система", "NTFS"),
            ("Состояние", "Исправен"),
            ("Активность", f"{used_percent:.1f}%")
        ]
            
        self._update_details('disk', "Использование диска", labels)

    def _update_ethernet_details(self, system_info):
        """Обновляет панель с детальной информацией о сети"""
        if not hasattr(self, 'system_monitor') or self.system_monitor is None:
            return  

        network_info = self.system_monitor.get_network_info()
        if not network_info or len(network_info) == 0:
            # Устанавливаем значения по умолчанию если нет данных
            labels = [
                ("Сетевой адаптер", "Не обнаружено"),
                ("Состояние", "Отключено"),
                ("IP адрес", "Нет подключения"),
                ("Скорость соединения", "Н/Д"),
                ("Получено", "0.0 Б/с"),
                ("Отправлено", "0.0 Б/с"),
                ("Общая скорость", "0.0 Б/с"),
                ("Тип подключения", "Н/Д"),
                ("MTU", "Н/Д"),
                ("Протокол", "Н/Д")
            ]
            self._update_details('network', "Использование сети", labels)
            return

        network = network_info[0]
        
        # Форматируем скорости
        def format_speed(speed_bytes):
            if speed_bytes < 1024:
                return f"{speed_bytes:.1f} Б/с"
            elif speed_bytes < 1024*1024:
                return f"{speed_bytes/1024:.1f} КБ/с"
            else:
                return f"{speed_bytes/1024/1024:.1f} МБ/с"

        labels = [
            ("Сетевой адаптер", network['name']),
            ("Состояние", "Подключено" if network['ipv4'] else "Отключено"),
            ("IP адрес", network['ipv4'] if network['ipv4'] else "Нет подключения"),
            ("Скорость соединения", "1.0 Гбит/с"),
            ("Получено", format_speed(network['recv_speed'])),
            ("Отправлено", format_speed(network['send_speed'])),
            ("Общая скорость", format_speed(network['send_speed'] + network['recv_speed'])),
            ("Тип подключения", "Ethernet"),
            ("MTU", "1500"),
            ("Протокол", "IPv4")
        ]
            
        self._update_details('network', "Использование сети", labels)

    def _update_details(self, metric, header_text, labels):
        """Обновляет содержимое панели деталей для конкретной метрики"""
        frame_info = self.detail_frames[metric]
        frame_info['header'].config(text=header_text)
        
        # Очищаем старые метки
        for widget in frame_info['container'].winfo_children():
            widget.destroy()
        
        # Создаем новые метки
        for i, (name, value) in enumerate(labels):
            row = i // 2
            col = i % 2
            frame = tk.Frame(frame_info['container'], bg='#1e1e1e')
            frame.grid(row=row, column=col, sticky='w', padx=10, pady=5)
            
            tk.Label(frame, text=name, bg='#1e1e1e', fg='#aaaaaa', anchor='w', width=25).pack(side='top', fill='x')
            tk.Label(frame, text=value, bg='#1e1e1e', fg='white', anchor='w', width=25, 
                    font=("Arial", 10, "bold")).pack(side='top', fill='x')

    def _format_uptime(self, seconds):
        """Форматирует время работы в читаемый формат"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def dark_color(self, color):
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        
        r = max(0, r - 40)
        g = max(0, g - 40)
        b = max(0, b - 40)
        
        return f'#{r:02x}{g:02x}{b:02x}'

class TaskManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Диспетчер задач")
        self.root.geometry("900x700")
        self.root.configure(bg="#2d2d2d")
        self.is_dark_theme = True

        self.system_monitor = SystemMonitor()
        self._cpu_info = None
        self._memory_info = None
        self._process_info = None
        self._data_lock = threading.Lock()
        self._process_selected = False
        
        self._setup_styles()
        self._create_interface()
        
        self.m = Menu(root, tearoff=0)
        self.m.add_command(label ="Получить путь", command=self._get_path) 
        self.m.add_command(label ="Завершить процесс", command=self._end_task)

        self.system_monitor.register_callback(self._update_data_buffer)
        self.system_monitor.start_monitoring()

        self.system_monitor._update_data()

        self._update_gui()
        self._schedule_gui_update()

    def do_popup(self, event):
        try:
            self.m.tk_popup(event.x_root, event.y_root)
        finally:
            self.m.grab_release()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background="#2d2d2d", borderwidth=0)
        style.configure("TNotebook.Tab", background="#5c2d5c", foreground="white", padding=[10, 5])
        style.map("TNotebook.Tab", background=[("selected", "#872187")])
        style.configure("Treeview", background="#872187", foreground="white", fieldbackground="#872187")
        style.configure("Treeview.Heading", background="#5c2d5c", foreground="white")

    def _create_interface(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

    # Вкладка процессов
        self.processes_frame = tk.Frame(self.notebook, bg="#2d2d2d")
        self.notebook.add(self.processes_frame, text="Процессы")
        self._setup_processes_tab()

    # Вкладка производительности (передаем system_monitor)
        self.performance_tab = PerformanceTab(self.notebook, self.system_monitor)
        self.notebook.add(self.performance_tab, text="Производительность")

    # Вкладка служб
        self.services_frame = tk.Frame(self.notebook, bg="#2d2d2d")
        self.notebook.add(self.services_frame, text="Службы")
        self._setup_services_tab()

    def _setup_processes_tab(self):
        columns = ("ID процесса", "Имя", "ЦП", "Память", "Диск", "Сеть", "GPU", "Энерг-ие")
        self.process_tree = ttk.Treeview(self.processes_frame, columns=columns, show="headings")

        for col in columns:
            self.process_tree.heading(col, text=col)
            self.process_tree.column(col, width=80, anchor="center")
        self.process_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Привязываем события
        self.process_tree.bind('<<TreeviewSelect>>', self._on_process_select)
        self.process_tree.bind('<Button-3>', self.do_popup)
        self.process_tree.bind('<space>', self._on_space)
        self._last_click_time = 0

        btn_frame = tk.Frame(self.processes_frame, bg="#2d2d2d")
        btn_frame.pack(fill=tk.X, pady=10)

    def _setup_services_tab(self):
        columns = ("Имя", "ID служб", "Состояние")
        self.services_tree = ttk.Treeview(self.services_frame, columns=columns, show="headings")

        self.services_tree.heading("Имя", text="Имя")
        self.services_tree.heading("ID служб", text="ID служб")
        self.services_tree.heading("Состояние", text="Состояние")

        self.services_tree.column("Имя", width=300)
        self.services_tree.column("ID служб", width=100)
        self.services_tree.column("Состояние", width=150)

        self.services_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _update_data_buffer(self, cpu_info, memory_info, process_info):
        with self._data_lock:
            self._cpu_info = cpu_info
            self._memory_info = memory_info
            self._process_info = process_info

    def _schedule_gui_update(self):
        self._update_gui()
        self.root.after(1000, self._schedule_gui_update)

    def _update_gui(self):
        with self._data_lock:
            if all(x is not None for x in (self._cpu_info, self._memory_info, self._process_info)):
                self._update_processes(self._process_info)
                self._update_performance()
                self._update_services()

    def _update_performance(self):
        # Collect all data using system_monitor DLL
        cpu_info = self.system_monitor._get_cpu_info()
        memory_info = self.system_monitor._get_memory_info()
        disk_info = self.system_monitor.get_disk_info()
        network_info = self.system_monitor.get_network_info()
        
        # Format the data for the performance tab
        system_info = {
            'cpu_percent': cpu_info['usage'],
            'cpu_frequency': cpu_info['frequency'],
            'memory': {
                'total': memory_info['total'],
                'available': memory_info['available']
            },
            'memory_speed': memory_info['speed'],
            'disk_usage': ((disk_info[0]['total_space'] - disk_info[0]['available_space']) / disk_info[0]['total_space'] * 100) if disk_info else 0,
            'network_usage': network_info[0]['send_speed'] + network_info[0]['recv_speed'] if network_info else 0,
            'process_count': cpu_info['process_count'],
            'thread_count': cpu_info.get('core_count', 0),
            'uptime': cpu_info['work_time'],
            'cpu_info': cpu_info,
            'memory_info': memory_info,
            'disk_info': disk_info[0] if disk_info else None,
            'network_info': network_info[0] if network_info else None
        }

        self.performance_tab.update_data(system_info)

    def _update_processes(self, processes):
        """Обновление списка процессов с учетом выделения"""
        if self._process_selected:
            return
            
        selected_items = self.process_tree.selection()
        selected_values = [self.process_tree.item(item)['values'][0] for item in selected_items]
        
        self.process_tree.delete(*self.process_tree.get_children())
        
        for proc in processes:
            values = (
                proc['pid'],
                proc['name'],
                f"{proc['cpu_usage']:.1f}%",
                f"{proc['memory_mb']:.1f} MB",
                f"{proc['read_kb'] / 1024:.1f} MB",
                "N/A",
                "N/A",
                "Normal"
            )
            item = self.process_tree.insert("", tk.END, values=values)
            if values[0] in selected_values:
                self.process_tree.selection_add(item)

    def _update_services(self):
        self.services_tree.delete(*self.services_tree.get_children())
        services = self.system_monitor.get_services_info()
        for service in services:
            self.services_tree.insert("", tk.END, values=(
                service['name'],
                service['process_id'],
                service['status']
            ))

    def _on_process_select(self, event):
        """Обработчик выделения процесса"""
        current_time = time.time()
        # Проверяем, было ли это действие вызвано пробелом
        if event.state == 0 and current_time - self._last_click_time > 0.1:  # Защита от двойного срабатывания
            self._last_click_time = current_time
            if self.process_tree.selection():
                self._process_selected = True
            else:
                self._process_selected = False

    def _on_space(self, event):
        """Обработчик нажатия пробела для снятия выделения"""
        self.process_tree.selection_remove(self.process_tree.selection())
        self._process_selected = False

    def _end_task(self):
        selected = self.process_tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите процесс для завершения")
            return
        item_values = self.process_tree.item(selected[0])['values']
        pid_str = item_values[0]
        try:
            pid = int(pid_str)
        except ValueError:
            messagebox.showerror("Ошибка", f"Неверный формат PID: {pid_str}")
            return
        process_name = item_values[1]
        if messagebox.askyesno("Подтверждение", f"Вы уверены, что хотите завершить процесс {process_name} (PID: {pid})?"):
            if self.system_monitor.kill_process(pid):
                messagebox.showinfo("Успех", f"Процесс {process_name} (PID: {pid}) успешно завершён.")
                self._process_selected = False
            else:
                messagebox.showerror("Ошибка", f"Не удалось завершить процесс {process_name} (PID: {pid}).")
    
    def _get_path(self):
        selected = self.process_tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите процесс для получения пути")
            return
        item_values = self.process_tree.item(selected[0])['values']
        pid_str = item_values[0]
        process_name = item_values[1]
        try:
            pid = int(pid_str)
        except ValueError:
            messagebox.showerror("Ошибка", f"Неверный формат PID: {pid_str}")
            return
        path = self.system_monitor.get_proc_path(pid)
        messagebox.showinfo("Успех", f"Путь {process_name}: {path}")

    def __del__(self):
        if hasattr(self, 'system_monitor'):
            self.system_monitor.stop_monitoring()
    

if __name__ == "__main__":
    root = tk.Tk()
    app = TaskManager(root)
    try:
        icon = tk.PhotoImage(file=R'C:\taskmng\TaskManager\icon.png')
        root.iconphoto(True, icon)
    except:
        pass  
    root.mainloop()
