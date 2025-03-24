import tkinter as tk
from tkinter import ttk
from tkinter import *

root = tk.Tk()
root.title("Диспетчер задач")
icon = PhotoImage(file = "icon.png")
root.iconphoto(False, icon)
root.geometry("600x400")
root.configure(bg="#808000")

root.attributes('-alpha', 0.94) 

# Стили
style = ttk.Style()
style.theme_use("clam")
style.configure("TNotebook", background="#696969", borderwidth=0)
style.configure("TNotebook.Tab", background="#696969", foreground="white", padding=[10, 5])
style.map("TNotebook.Tab", background=[("selected", "#000000")])

style.configure("Treeview", background="#000000", foreground="white", fieldbackground="#000000")
style.configure("Treeview.Heading", background="#000000", foreground="white")

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True)

# Вкладки
frame1 = tk.Frame(notebook, bg="#808080")
frame2 = tk.Frame(notebook, bg="#808080")
frame3 = tk.Frame(notebook, bg="#808080")
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
