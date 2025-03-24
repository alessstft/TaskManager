import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("Task Manager")
root.geometry("600x400")
root.configure(bg="#2d2d2d")


root.attributes('-alpha', 0.95) 

# Стили
style = ttk.Style()
style.theme_use("clam")
style.configure("TNotebook", background="#2d2d2d", borderwidth=0)
style.configure("TNotebook.Tab", background="#5c2d5c", foreground="white", padding=[10, 5])
style.map("TNotebook.Tab", background=[("selected", "#872187")])

style.configure("Treeview", background="#872187", foreground="white", fieldbackground="#872187")
style.configure("Treeview.Heading", background="#5c2d5c", foreground="white")

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True)

# Вкладки
frame1 = tk.Frame(notebook, bg="#872187")
frame2 = tk.Frame(notebook, bg="#2d2d2d")
frame3 = tk.Frame(notebook, bg="#2d2d2d")
notebook.add(frame1, text="Процессы")
notebook.add(frame2, text="Производительность")
notebook.add(frame3, text="Службы")

# Таблица
columns = ("Имя", "ЦП", "Память", "Диск", "Сеть", "GPU", "Энерг-ие")
tree = ttk.Treeview(frame1, columns=columns, show="headings")

for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=80, anchor="w")

tree.pack(fill=tk.BOTH, expand=True)

# Добавление данных
processes = [
    ("Первое запущенное приложение", "", "", "", "", "", ""),
    ("Второе запущенное приложение", "", "", "", "", "", ""),
    ("Третье запущенное приложение", "", "", "", "", "", "")
]

for process in processes:
    tree.insert("", tk.END, values=process)

root.mainloop()
