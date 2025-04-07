import tkinter as tk
from tkinter import ttk, Canvas, messagebox
from tkinter import *
from system_monitor import SystemMonitor
import threading

class TaskManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Диспетчер задач")
        self.root.geometry("800x500")
        self.root.configure(bg="#2d2d2d")

        # Инициализация SystemMonitor
        self.system_monitor = SystemMonitor()
        
        # Буфер для данных
        self._cpu_info = None
        self._memory_info = None
        self._process_info = None
        self._data_lock = threading.Lock()
        
        # Настройка стилей
        self._setup_styles()
        
        # Создание интерфейса
        self._create_interface()
        
        # Запуск мониторинга
        self.system_monitor.register_callback(self._update_data_buffer)
        self.system_monitor.start_monitoring(update_interval=1.0)
        
        # Запуск обновления GUI
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
        # Создание notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Вкладка "Процессы"
        self.processes_frame = tk.Frame(self.notebook, bg="#872187")
        self.notebook.add(self.processes_frame, text="Процессы")
        self._setup_processes_tab()

        # Вкладка "Производительность"
        self.performance_frame = tk.Frame(self.notebook, bg="#872187")
        self.notebook.add(self.performance_frame, text="Производительность")
        self._setup_performance_tab()

        # Вкладка "Службы"
        self.services_frame = tk.Frame(self.notebook, bg="#872187")
        self.notebook.add(self.services_frame, text="Службы")
        self._setup_services_tab()

    def _setup_processes_tab(self):
        # Таблица процессов
        columns = ("ID процесса", "Имя", "ЦП", "Память", "Диск", "Сеть", "GPU", "Энерг-ие")
        self.process_tree = ttk.Treeview(self.processes_frame, columns=columns, show="headings")

        for col in columns:
            self.process_tree.heading(col, text=col)
            self.services_tree.heading("ID процесса", text="ID процесса")
            self.process_tree.column(col, width=80, anchor="center")

        self.process_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.services_tree.column("ID процесса", width=100)

        # Кнопка завершения задачи
        self.end_task_btn = tk.Button(self.processes_frame, text="Завершить задачу", 
                                    bg="#5c2d5c", fg="white", 
                                    font=("Arial", 12, "bold"), 
                                    command=self._end_task)
        self.end_task_btn.pack(pady=10)

    def _setup_services_tab(self):
        # Таблица служб
        columns = ("Имя", "ID процесса", "Состояние")
        self.services_tree = ttk.Treeview(self.services_frame, columns=columns, show="headings")

        # Настройка колонок
        self.services_tree.heading("Имя", text="Имя")
        self.services_tree.heading("ID процесса", text="ID процесса")
        self.services_tree.heading("Состояние", text="Состояние")

        self.services_tree.column("Имя", width=300)
        self.services_tree.column("ID процесса", width=100)
        self.services_tree.column("Состояние", width=150)

        self.services_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _setup_performance_tab(self):
        # Создаем Canvas для графиков
        self.canvas = Canvas(self.performance_frame, bg="#872187", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Создаем StringVar для метрик
        self.metrics_var = tk.StringVar()
        self.metrics_label = tk.Label(
            self.performance_frame,
            textvariable=self.metrics_var,
            bg="#872187",
            fg="white",
            font=("Arial", 12)
        )
        self.metrics_label.pack(pady=10)
        
        # Инициализация метрик
        self.metrics = [
            {"label": "ЦП"},
            {"label": "Память"},
            {"label": "Диск"},
            {"label": "Ethernet"},
            {"label": "GPU"}
        ]

        self.canvas.bind("<Configure>", self._update_canvas)

    def _update_data_buffer(self, cpu_info, memory_info, process_info):
        """Обновляет буфер данных в отдельном потоке"""
        with self._data_lock:
            self._cpu_info = cpu_info
            self._memory_info = memory_info
            self._process_info = process_info

    def _schedule_gui_update(self):
        """Планирует обновление GUI"""
        self._update_gui()
        self.root.after(1000, self._schedule_gui_update)  # Обновление GUI каждую секунду

    def _update_gui(self):
        """Обновляет GUI используя данные из буфера"""
        with self._data_lock:
            if all(x is not None for x in (self._cpu_info, self._memory_info, self._process_info)):
                self._update_processes(self._process_info)
                self._update_performance_metrics()
                self._update_services()

    def _update_services(self):
        """Обновляет таблицу служб"""
        # Очистка старых данных
        self.services_tree.delete(*self.services_tree.get_children())
        
        # Получение информации о службах
        services = self.system_monitor.get_services_info()
        
        # Добавление новых данных
        for service in services:
            self.services_tree.insert("", tk.END, values=(
                service['name'],
                service['process_id'],
                service['status']
            ))

    def _update_processes(self, processes):
        """Обновляет таблицу процессов"""
        # Сохраняем выбранные элементы
        selected_items = self.process_tree.selection()
        selected_values = [self.process_tree.item(item)['values'][0] for item in selected_items]

        # Очистка старых данных
        self.process_tree.delete(*self.process_tree.get_children())
            
        # Добавление новых данных
        for proc in processes:
            values = (
                proc['name'],
                f"{proc['cpu_usage']:.1f}%",
                f"{proc['memory_mb']:.1f} MB",
                f"{proc['read_kb']:.1f} KB",
                "N/A",
                "N/A",
                "Normal"
            )
            item = self.process_tree.insert("", tk.END, values=values)
            
            # Восстанавливаем выделение
            if values[0] in selected_values:
                self.process_tree.selection_add(item)

    def _update_performance_metrics(self):
        """Обновляет метрики производительности"""
        disk_info = self.system_monitor.get_disk_info()
        net_info = self.system_monitor.get_network_info()

        # Расчет использования диска в ГБ
        total_space = sum(disk['total_space'] for disk in disk_info)
        available_space = sum(disk['available_space'] for disk in disk_info)
        used_space = total_space - available_space

        # Расчет общей сетевой скорости в Mbps
        total_network_speed = 0
        for net in net_info:
            if not any(x in net['name'].lower() for x in ['virtual', 'vmware', 'loopback']):
                total_network_speed += (net['send_speed'] + net['recv_speed']) * 8 / (1024 * 1024)  # Convert to Mbps

        # Форматирование текста скорости сети
        if total_network_speed < 0.01:
            network_text = "0 Mbps"
        elif total_network_speed < 1:
            network_text = f"{total_network_speed:.2f} Mbps"
        elif total_network_speed < 10:
            network_text = f"{total_network_speed:.1f} Mbps"
        else:
            network_text = f"{int(total_network_speed)} Mbps"

        # Получаем информацию о памяти и CPU
        memory_info = self.system_monitor._get_memory_info()
        memory_used = memory_info['used']
        memory_total = memory_info['total']
        cpu_percent = self.system_monitor.get_cpu_percent()

        # Форматируем значения для диска
        disk_text = f"{used_space:.0f}/{total_space:.0f}"

        # Обновляем метрики
        metrics = [
            f"CPU: {cpu_percent:.1f}%",
            f"RAM: {memory_used:.1f}/{memory_total:.1f} GB",
            f"Disk: {disk_text} GB",
            f"Network: {network_text}"
        ]
        
        self.metrics_var.set(" | ".join(metrics))

        # Обновляем значения для кругов
        self.metrics = [
            {"label": f"ЦП\n{cpu_percent:.1f}%"},
            {"label": f"Память\n{memory_used:.1f}/{memory_total:.1f} GB"},
            {"label": f"Диск\n{disk_text} GB"},
            {"label": f"Ethernet\n{network_text}"},
            {"label": f"GPU\n0%"}
        ]
        self._update_canvas()

    def _update_canvas(self, event=None):
        """Обновляет отрисовку кругов на канвасе"""
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        circle_size = min(width, height) // 6
        positions = [
            (width * 0.2, height * 0.3),
            (width * 0.5, height * 0.3),
            (width * 0.8, height * 0.3),
            (width * 0.35, height * 0.7),
            (width * 0.65, height * 0.7)
        ]

        for i, (x, y) in enumerate(positions):
            if i < len(self.metrics):
                # Рисуем круг
                self.canvas.create_oval(
                    x - circle_size, y - circle_size,
                    x + circle_size, y + circle_size,
                    fill="#5c2d5c", outline="white"
                )
                # Добавляем текст
                self.canvas.create_text(
                    x, y,
                    text=self.metrics[i]["label"],
                    fill="white",
                    font=("Arial", 12, "bold")
                )

    def _end_task(self):
        """Завершает выбранный процесс"""
        selected = self.process_tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите процесс для завершения")
            return
            
        process_name = self.process_tree.item(selected[0])['values'][0]
        if messagebox.askyesno("Подтверждение", f"Вы уверены, что хотите завершить процесс {process_name}?"):
            # Здесь должен быть код для завершения процесса
            pass

    def __del__(self):
        """Деструктор класса"""
        if hasattr(self, 'system_monitor'):
            self.system_monitor.stop_monitoring()

if __name__ == "__main__":
    root = tk.Tk()
    icon = PhotoImage(file="C:/taskmng/TaskManager/icon.png")
    root.iconphoto(False, icon)
    app = TaskManager(root)
    root.mainloop()
