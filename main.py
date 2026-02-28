# main.py
import tkinter as tk
from gui import show_start_screen


def main():
    root = tk.Tk()
    root.title("Chess MVP")
    show_start_screen(root)
    root.mainloop()


if __name__ == "__main__":
    main()
