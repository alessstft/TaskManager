import tkinter as tk
from Frame import TaskManager
import sys
import os

def main():
    try:
        print("Starting application...")
        print(f"Current directory: {os.getcwd()}")
        print(f"DLL path exists: {os.path.exists('sys_info_fn.dll')}")
        
        root = tk.Tk()
        print("Created Tk root window")
        
        app = TaskManager(root)
        print("Created TaskManager instance")
        
        root.mainloop()
        print("Started mainloop")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main() 