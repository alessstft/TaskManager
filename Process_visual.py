import tkinter as tk
from tkinter import ttk, Canvas, messagebox
import random

# Создаем главное окно
root = tk.Tk()
root.title("Диспетчер задач")
root.geometry("700x450")
root.configure(bg="#2d2d2d")

# Функция для завершения выбранного процесса
def end_task():
    selected_item = tree.selection()  # Получаем выделенный элемент
    if selected_item:
        tree.delete(selected_item)  # Удаляем процесс из таблицы
    else:
        messagebox.showwarning("Ошибка", "Выберите задачу для завершения")

# Устанавливаем прозрачность окна (неполностью)
root.attributes('-alpha', 0.95)

# Стилизация
style = ttk.Style()
style.theme_use("clam")

style.configure("TNotebook", background="#2d2d2d", borderwidth=0)
style.configure("TNotebook.Tab", background="#5c2d5c", foreground="white", padding=[10, 5])
style.map("TNotebook.Tab", background=[("selected", "#872187")])

style.configure("Treeview", background="#872187", foreground="white", fieldbackground="#872187")
style.configure("Treeview.Heading", background="#5c2d5c", foreground="white")

# Создаем вкладки
notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True)

# Вкладка "Процессы"
frame1 = tk.Frame(notebook, bg="#872187")
notebook.add(frame1, text="Процессы")

# Таблица процессов
columns = ("Имя", "ЦП", "Память", "Диск", "Сеть", "GPU", "Энергопотребление")
tree = ttk.Treeview(frame1, columns=columns, show="headings")

for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=90, anchor="center")

tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# Кнопка завершения задачи
end_task_btn = tk.Button(frame1, text="Завершить задачу", bg="#5c2d5c", fg="white", font=("Arial", 12, "bold"), command=end_task)
end_task_btn.pack(pady=10)

# Данные о процессах (тестовые)
processes = [
    ("Discord.exe", "2%", "150MB", "0MB/s", "0Kb/s", "0%", "Низкое"),
    ("Chrome.exe", "5%", "300MB", "1MB/s", "20Kb/s", "5%", "Среднее"),
    ("VisualStudio.exe", "15%", "1GB", "5MB/s", "100Kb/s", "30%", "Высокое"),
]

for process in processes:
    tree.insert("", tk.END, values=process)

# Вкладка "Производительность"
frame2 = tk.Frame(notebook, bg="#2d2d2d")
notebook.add(frame2, text="Производительность")


# Функция обновления производительности (рандомные значения для имитации)
def update_performance():
    cpu_usage.set(f"{random.randint(10, 90)}%")
    ram_usage.set(f"{random.randint(2, 16)}GB / 16GB")
    disk_usage.set(f"{random.randint(10, 200)}MB/s")
    network_usage.set(f"{random.randint(10, 1000)}Kb/s")
    gpu_usage.set(f"{random.randint(5, 80)}%")
    root.after(2000, update_performance)  # Обновлять каждые 2 секунды

# Метки производительности
cpu_usage = tk.StringVar()
ram_usage = tk.StringVar()
disk_usage = tk.StringVar()
network_usage = tk.StringVar()
gpu_usage = tk.StringVar()

labels = [
    ("ЦП:", cpu_usage),
    ("ОЗУ:", ram_usage),
    ("Диск:", disk_usage),
    ("Сеть:", network_usage),
    ("GPU:", gpu_usage),
]

for i, (text, var) in enumerate(labels):
    tk.Label(frame2, text=text, fg="white", bg="#2d2d2d", font=("Arial", 12)).grid(row=i, column=0, sticky="w", padx=20, pady=5)
    tk.Label(frame2, textvariable=var, fg="white", bg="#2d2d2d", font=("Arial", 12, "bold")).grid(row=i, column=1, sticky="w", padx=10, pady=5)

update_performance()  # Запускаем обновление производительности

root.mainloop()
