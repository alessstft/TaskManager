import tkinter as tk
from tkinter import ttk, Canvas, messagebox
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
        self.current_metric = 'cpu'
        self._prev_values = {}
        self._last_update = 0
        self._update_interval = 0.5
        
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
                borderwidth=5, 
                relief='flat',
                command=lambda m=metric: self.switch_metric(m)
            )

            btn.bind("<Enter>", lambda e, b=btn, c=color: b.config(bg=c))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg='#2d2d2d'))
            btn.bind("<Button-1>", lambda e, b=btn, c=color: b.config(bg=c))
            btn.bind("<Button-1>", lambda e, b=btn, c=color: b.config(bg=self.dark_color(c)))
            btn.grid(row=i, column=0, sticky='ew', padx=2, pady=2, ipadx=50, ipady=5)
        
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
        info_frame.pack(fill='x', padx=10, pady=(0, 10))
        
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
            frame.grid(row=0, column=i, padx=15)
            
            tk.Label(frame, text=name, bg='#1e1e1e', fg='#aaaaaa').pack()
            self.info_labels[name] = tk.Label(frame, text=value, bg='#1e1e1e', fg='white')
            self.info_labels[name].pack()

        # Создаем фрейм для деталей под графиком
        self.details_frame = tk.Frame(right_panel, bg='#1e1e1e', highlightbackground="#3c3c3c", highlightthickness=1)
        self.details_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Заголовок деталей
        self.details_header = tk.Label(self.details_frame, font=("Arial", 12, "bold"), 
                                     bg="#1e1e1e", fg="white")
        self.details_header.pack(anchor="w", padx=10, pady=(15, 1))
        
        # Контейнер для деталей
        self.details_container = tk.Frame(self.details_frame, bg='#1e1e1e')
        self.details_container.pack(fill="both", expand=True, padx=5)
        
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
        
        # Обновляем информацию в зависимости от выбранной метрики
        if metric == 'memory':
            self._update_memory_details(self._last_system_info if hasattr(self, '_last_system_info') else {})
        elif metric == 'disk':
            self._update_disk_details(self._last_system_info if hasattr(self, '_last_system_info') else {})
        elif metric == 'network':
            self._update_ethernet_details(self._last_system_info if hasattr(self, '_last_system_info') else {})
        else:
            # Скрываем детали для CPU
            if hasattr(self, 'details_frame'):
                self.details_frame.place_forget()
        
    def update_data(self, system_info):
        current_time = time.time()
        if current_time - self._last_update < self._update_interval:
            return
            
        with self._data_lock:
            # Сохраняем последние данные системы
            self._last_system_info = system_info
            
            metrics_data = self.calculate_metrics(system_info)
            for metric, value in metrics_data.items():   
                self.values[metric].append(value)
            
            if self.current_metric in metrics_data:
                self.update_chart()
                
            self.update_labels(system_info, metrics_data)
            self._last_update = current_time
            
    def calculate_metrics(self, system_info):
        metrics = {}
        metrics['cpu'] = system_info.get('cpu_percent', 0.0)
        
        memory = system_info.get('memory', {})
        total_memory = memory.get('total', 1)
        used_memory = total_memory - memory.get('available', 0)
        metrics['memory'] = (used_memory / total_memory) * 100 if total_memory > 0 else 0.0
        
        metrics['disk'] = system_info.get('disk_usage', 0.0)
        metrics['network'] = system_info.get('network_usage', 0.0)
        
        return metrics
        
    def update_chart(self):
        if not hasattr(self, '_current_color'):
            self._current_color = '#3794ff'
            
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        self.canvas.delete('all')
        
        # Сетка
        for i in range(0, 101, 20):
            y = height - (i/100 * (height - 20))
            self.canvas.create_line(0, y, width, y, fill='#3c3c3c')
            self.canvas.create_text(5, y, text=f"{i}%", fill='white', anchor='w')
        
        # График
        values = list(self.values[self.current_metric])
        if len(values) > 1:
            points = []
            for i, value in enumerate(values):
                x = (i / (len(values)-1)) * (width - 20) + 10
                y = height - (value/100 * (height - 20))
                points.extend([x, y])
            
            self.canvas.create_line(points, fill=self._current_color, width=2, smooth=True)
    
    def update_labels(self, system_info, metrics_data):
        cpu_percent = metrics_data.get('cpu', 0)
        self.info_labels["Использование"].config(text=f"{cpu_percent:.1f}%")
        self.info_labels["Процессы"].config(text=str(system_info.get('process_count', 0)))
        self.info_labels["Потоки"].config(text=str(system_info.get('thread_count', 0)))
        
        # Форматируем время работы
        uptime = system_info.get('uptime', 0)
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        self.info_labels["Время работы"].config(text=f"{hours}:{minutes:02d}:{seconds:02d}")
        
        # Если текущая метрика - память, показываем детальную информацию
        if self.current_metric == 'memory':
            self._update_memory_details(system_info)
        else:
            # Если не память - скрываем детали
            if hasattr(self, 'details_frame'):
                self.details_frame.place_forget()
    
    def _update_memory_details(self, system_info):
        """Обновляет панель с детальной информацией о памяти"""
        if not hasattr(self, 'system_monitor') or self.system_monitor is None:
            return  
    
        memory_info = self.system_monitor._get_memory_info()
        total_gb = memory_info['total'] / (1024**3)
        used_gb = memory_info['used'] / (1024**3)
        available_gb = memory_info['available'] / (1024**3)
        
        # Обновляем метки с актуальными данными
        labels = [
            ("Используется (сжатая)", f"{used_gb:.1f} ГБ (188 МБ)"),
            ("Доступно", f"{available_gb:.1f} ГБ"),
            ("Скорость:", f"{memory_info['speed']} МГц"),
            ("Выделено", f"{used_gb:.1f}/{total_gb:.1f} ГБ"),
            ("Кэшировано", "1,1 ГБ"),
            ("Использовано гнезд:", "2 из 4"),
            ("Выгружаемый пул", "315 МБ"),
            ("Невыгружаемый пул", "184 МБ"),
            ("Форм-фактор:", "DIMM"),
            ("Зарезервировано аппаратно:", "95,1 МБ")
        ]
        
        self._update_details("Использование памяти", labels)

    def _update_disk_details(self, system_info):
        if not hasattr(self, 'system_monitor') or self.system_monitor is None:
            return  # Прекращаем выполнение, если system_monitor не задан

        disk_info = self.system_monitor.get_disk_info()
        if not disk_info:  # Проверяем, что данные есть
            return

        disk_info = disk_info[0]  # Берем первый диск
        total_gb = disk_info['total_space'] / (1024**3)
        available_gb = disk_info['available_space'] / (1024**3)
        used_gb = total_gb - available_gb
        
        labels = [
            ("Активное время", "0%"),
            ("Средняя скорость отклика", "0 мс"),
            ("Скорость записи", "0 КБ/с"),
            ("Скорость чтения", "0 КБ/с"),
            ("Активное время записи", "0%"),
            ("Активное время чтения", "0%"),
            ("Размер раздела", f"{total_gb:.1f} ГБ"),
            ("Свободно места", f"{available_gb:.1f} ГБ"),
            ("Используется места", f"{used_gb:.1f} ГБ"),
            ("Тип раздела", "NTFS")
        ]
        
        self._update_details(f"Диск ({disk_info['name']})", labels)

    def _update_ethernet_details(self, system_info):
        if not hasattr(self, 'system_monitor') or self.system_monitor is None:
            return  # Прекращаем выполнение, если system_monitor не задан

        network_info = self.system_monitor.get_network_info()
        if not network_info:  # Проверяем, что данные есть
            network_info = []

            labels = [
                ("Отправлено", f"{net['send_speed']/1024:.1f} КБ/с"),
                ("Получено", f"{net['recv_speed']/1024:.1f} КБ/с"),
                ("Скорость соединения", "1.0 Гбит/с"),
                ("Состояние", "Подключено"),
                ("IPv4-адрес", net['ipv4']),
                ("Тип адаптера", "Ethernet"),
                ("DNS-сервер", "8.8.8.8"),
                ("Шлюз по умолчанию", "192.168.1.1"),
                ("Маска подсети", "255.255.255.0"),
                ("DHCP", "Включен")
            ]
        else:
            labels = [("Состояние", "Не подключено")]
            
        self._update_details("Ethernet", labels)

    def _update_details(self, header_text, labels):
        """Обновляет содержимое панели деталей"""
        # Обновляем заголовок
        self.details_header.config(text=header_text)
        
        # Очищаем старые метки
        for widget in self.details_container.winfo_children():
            widget.destroy()
        
        # Создаем новые метки
        for i, (name, value) in enumerate(labels):
            row = i // 2
            col = i % 2
            frame = tk.Frame(self.details_container, bg='#1e1e1e')
            frame.grid(row=row, column=col, sticky='w', padx=10, pady=5)
            
            tk.Label(frame, text=name, bg='#1e1e1e', fg='#aaaaaa', anchor='w', width=25).pack(side='top', fill='x')
            tk.Label(frame, text=value, bg='#1e1e1e', fg='white', anchor='w', width=25, 
                    font=("Arial", 10, "bold")).pack(side='top', fill='x')
        
        self.details_frame.lift()

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
        
        self.system_monitor.register_callback(self._update_data_buffer)
        self.system_monitor.start_monitoring(update_interval=2.0)
        self._schedule_gui_update()

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
        
        self.process_tree.bind('<<TreeviewSelect>>', self._on_process_select)
        self.process_tree.bind('<Button-3>', self._on_right_click)

        btn_frame = tk.Frame(self.processes_frame, bg="#2d2d2d")
        btn_frame.pack(fill=tk.X, pady=10)

        self.end_task_btn = tk.Button(
            btn_frame,
            text="Завершить задачу",
            bg="#5c2d5c",
            fg="white",
            font=("Arial", 12, "bold"),
            command=self._end_task
        )
        self.end_task_btn.pack(side=tk.LEFT, padx=10, ipadx=20, ipady=5)

        self.get_path_btn = tk.Button(
            btn_frame,
            text="Получить путь",
            bg="#5c2d5c",
            fg="white",
            font=("Arial", 12, "bold"),
            command=self._get_path
        )
        self.get_path_btn.pack(side=tk.RIGHT, padx=10, ipadx=20, ipady=5)

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
        self.root.after(1500, self._schedule_gui_update)

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
        
        # Format the data for the performance tab
        system_info = {
            'cpu_percent': cpu_info['usage'],
            'memory': {
                'total': memory_info['total'] / (1024 * 1024 * 1024),  # Convert to GB
                'available': memory_info['available'] / (1024 * 1024 * 1024)  # Convert to GB
            },
            'disk_usage': disk_info[0]['percent'] if disk_info and 'percent' in disk_info[0] else 
                          (1 - disk_info[0]['available_space'] / disk_info[0]['total_space']) * 100 if disk_info else 0,
            'network_usage': 0,  # Will be updated with proper calculation
            'process_count': cpu_info['process_count'],
            'thread_count': 0,  # This information might not be directly available from the DLL
            'uptime': cpu_info['work_time']
        }
        

        self.performance_tab.update_data(system_info)

    def _update_processes(self, processes):
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
        if self.process_tree.selection():
            self._process_selected = True
        else:
            self._process_selected = False

    def _on_right_click(self, event):
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
        icon = tk.PhotoImage(file='C:/Users/studentcoll/Desktop/TaskManager-Boba/icon.png')
        root.iconphoto(True, icon)
    except:
        pass  
    
    root.mainloop()
