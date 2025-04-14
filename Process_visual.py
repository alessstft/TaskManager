import tkinter as tk
from tkinter import ttk, Canvas, messagebox
import psutil
import threading
from system_monitor import SystemMonitor
from tkinter import *
from tkinter import PhotoImage

class TaskManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Диспетчер задач")
        self.root.geometry("900x600")
        self.root.configure(bg="#2d2d2d")

        self.system_monitor = SystemMonitor()
        self._data_lock = threading.Lock()

        # Инициализация истории для всех метрик
        self.cpu_history = []
        self.memory_history = []
        self.disk_history = []
        self.network_history = []
        self.max_history_size = 60
        self.metrics = []
        self.current_graph = "cpu"  # Текущий отображаемый график

        self._setup_styles()
        self._create_interface()

        self.system_monitor.register_callback(self._update_metrics_data)
        self.system_monitor.start_monitoring(update_interval=1.0)
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

        # Вкладка процессы
        self.processes_frame = tk.Frame(self.notebook, bg="#872187")
        self.notebook.add(self.processes_frame, text="Процессы")
        self._setup_processes_tab()

        # Вкладка производительность
        self.performance_frame = tk.Frame(self.notebook, bg="#1e1e1e")
        self.notebook.add(self.performance_frame, text="Производительность")
        self._setup_performance_tab()

        # Вкладка службы
        self.services_frame = tk.Frame(self.notebook, bg="#872187")
        self.notebook.add(self.services_frame, text="Службы")
        self._setup_services_tab()

    def _setup_processes_tab(self):
        columns = ("ID процесса", "Имя", "ЦП", "Память", "Диск", "Сеть", "GPU", "Энерг-ие")
        self.process_tree = ttk.Treeview(self.processes_frame, columns=columns, show="headings")

        for col in columns:
            self.process_tree.heading(col, text=col)
            self.process_tree.column(col, width=80, anchor="center")
        self.process_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.end_task_btn = tk.Button(self.processes_frame, text="Завершить задачу",
                                      bg="#5c2d5c", fg="white",
                                      font=("Arial", 12, "bold"),
                                      command=self._end_task)
        self.end_task_btn.pack(pady=10)

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

    def _setup_performance_tab(self):
        self.canvas = Canvas(self.performance_frame, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._update_canvas)

    def _update_metrics_data(self):
        """Обновляет данные всех метрик"""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=None)
        self.cpu_history.append(cpu_percent)
        if len(self.cpu_history) > self.max_history_size:
            self.cpu_history.pop(0)

        # Memory
        memory = self.system_monitor._get_memory_info()
        memory_percent = (memory['used'] / memory['total']) * 100
        self.memory_history.append(memory_percent)
        if len(self.memory_history) > self.max_history_size:
            self.memory_history.pop(0)

        # Disk
        disk = self.system_monitor.get_disk_info()
        total_disk = sum(d['total_space'] for d in disk)
        used_disk = total_disk - sum(d['available_space'] for d in disk)
        disk_percent = (used_disk / total_disk) * 100 if total_disk > 0 else 0
        self.disk_history.append(disk_percent)
        if len(self.disk_history) > self.max_history_size:
            self.disk_history.pop(0)

        # Network
        net = self.system_monitor.get_network_info()
        net_speed = sum((n['send_speed'] + n['recv_speed']) * 8 / 1024 / 1024 for n in net)
        self.network_history.append(min(net_speed, 100))  # Ограничиваем до 100%
        if len(self.network_history) > self.max_history_size:
            self.network_history.pop(0)

        self.root.after(1000, self._update_metrics_data)

    def _update_canvas(self, event=None):
        self.canvas.delete("all")

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        # График производительности
        self._draw_cpu_graph(width, height)

        # Метрики
        self._update_performance_metrics()
        self._draw_metrics_circles(width, height)

    def _draw_cpu_graph(self, width, height):
        """Рисует график для выбранной метрики"""
        padding = 40
        graph_width = width - 2 * padding
        graph_height = height // 2 - padding

        grid_color = "#3c3c3c"
        text_color = "#cccccc"

        # Выбираем данные для отображения и настраиваем цвет
        if self.current_graph == "cpu":
            data = self.cpu_history
            title = "ЦП"
            graph_color = "#00c3ff"  # Синий для CPU
        elif self.current_graph == "memory":
            data = self.memory_history
            title = "Память"
            graph_color = "#ff6b6b"  # Красный для памяти
        elif self.current_graph == "disk":
            data = self.disk_history
            title = "Диск"
            graph_color = "#4caf50"  # Зеленый для диска
        elif self.current_graph == "network":
            data = self.network_history
            title = "Сеть"
            graph_color = "#ff9800"  # Оранжевый для сети
        elif self.current_graph == "gpu":
            data = [0] * self.max_history_size  # Заглушка для GPU
            title = "GPU"
            graph_color = "#9c27b0"  # Фиолетовый для GPU
        else:
            data = self.cpu_history
            title = "ЦП"
            graph_color = "#00c3ff"

        # Рисуем сетку и подписи
        for i in range(0, 101, 20):
            y = height // 2 - (i / 100 * graph_height)
            self.canvas.create_line(padding, y, width - padding, y, fill=grid_color)
            self.canvas.create_text(padding - 10, y, text=f"{i}%", fill=text_color, anchor="e", font=("Segoe UI", 10))

        num_lines = 6
        for i in range(num_lines + 1):
            x = padding + (i / num_lines) * graph_width
            self.canvas.create_line(x, height // 2 - graph_height, x, height // 2, fill=grid_color)
            seconds_ago = self.max_history_size - (i * self.max_history_size // num_lines)
            self.canvas.create_text(x, height // 2 + 15, text=f"-{seconds_ago}s", fill=text_color, anchor="n", font=("Segoe UI", 9))

        # Рисуем график
        if len(data) > 1:
            points = []
            visible = data[-self.max_history_size:]
            for i, value in enumerate(visible):
                x = padding + (i / (self.max_history_size - 1)) * graph_width
                y = height // 2 - (value / 100 * graph_height)
                points.extend([x, y])
            self.canvas.create_line(points, fill=graph_color, width=2, smooth=True)

        if data:
            self.canvas.create_text(padding, height // 2 - graph_height - 20, 
                                  text=f"{title}: {data[-1]:.1f}%", 
                                  fill="white", 
                                  anchor="w", 
                                  font=("Segoe UI", 14, "bold"))

    def _draw_metrics_circles(self, width, height):
        circle_size = min(width, height) // 10
        positions = [
            (width * 0.1, height * 0.75),
            (width * 0.3, height * 0.75),
            (width * 0.5, height * 0.75),
            (width * 0.7, height * 0.75),
            (width * 0.9, height * 0.75),
        ]

        for i, (x, y) in enumerate(positions):
            if i < len(self.metrics):
                # Создаем круг с тегом для кликабельности
                circle = self.canvas.create_oval(
                    x - circle_size, y - circle_size,
                    x + circle_size, y + circle_size,
                    fill="#5c2d5c", outline="white",
                    tags=f"circle_{i}"
                )
                
                # Добавляем текст
                self.canvas.create_text(
                    x, y,
                    text=self.metrics[i],
                    fill="white",
                    font=("Arial", 10, "bold"),
                    tags=f"text_{i}"
                )
                
                # Привязываем обработчик клика
                self.canvas.tag_bind(f"circle_{i}", "<Button-1>", lambda e, idx=i: self._on_circle_click(idx))
                self.canvas.tag_bind(f"text_{i}", "<Button-1>", lambda e, idx=i: self._on_circle_click(idx))

    def _on_circle_click(self, index):
        """Обработчик клика по кругу"""
        if index < len(self.metrics):
            # Устанавливаем текущий график в зависимости от выбранного круга
            if "ЦП" in self.metrics[index]:
                self.current_graph = "cpu"
            elif "Память" in self.metrics[index]:
                self.current_graph = "memory"
            elif "Диск" in self.metrics[index]:
                self.current_graph = "disk"
            elif "Ethernet" in self.metrics[index]:
                self.current_graph = "network"
            elif "GPU" in self.metrics[index]:
                self.current_graph = "gpu"
            
            # Обновляем отображение
            self._update_canvas()

    def _update_performance_metrics(self):
        memory = self.system_monitor._get_memory_info()
        disk = self.system_monitor.get_disk_info()
        net = self.system_monitor.get_network_info()
        cpu_percent = psutil.cpu_percent(interval=None)

        total_disk = sum(d['total_space'] for d in disk)
        used_disk = total_disk - sum(d['available_space'] for d in disk)
        net_speed = sum((n['send_speed'] + n['recv_speed']) * 8 / 1024 / 1024 for n in net)

        net_str = f"{net_speed:.1f} Mbps" if net_speed > 0 else "0 Mbps"

        self.metrics = [
            f"ЦП\n{cpu_percent:.1f}%",
            f"Память\n{memory['used']:.1f}/{memory['total']:.1f} GB",
            f"Ethernet\n{net_str}",
            f"GPU\nN/A",
            f"Диск\n{used_disk:.0f}/{total_disk:.0f} GB"
        ]

    def _schedule_gui_update(self):
        self._update_services()
        # self._update_processes([])  # Здесь должен быть список процессов, если получаем его
        self._update_canvas()
        self.root.after(1000, self._schedule_gui_update)

    def _update_services(self):
        self.services_tree.delete(*self.services_tree.get_children())
        services = self.system_monitor.get_services_info()
        for service in services:
            self.services_tree.insert("", tk.END, values=(service['name'], service['process_id'], service['status']))

    def _end_task(self):
        selected = self.process_tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите процесс для завершения")
            return
        process_name = self.process_tree.item(selected[0])['values'][0]
        if messagebox.askyesno("Подтверждение", f"Завершить процесс {process_name}?"):
            # Завершение процесса (добавить реализацию)
            pass

    def __del__(self):
        self.system_monitor.stop_monitoring()


if __name__ == "__main__":
    root = tk.Tk()
    app = TaskManager(root)
    icon = PhotoImage(file='icon.png')
    root.iconphoto(True, icon)
    root.mainloop()
