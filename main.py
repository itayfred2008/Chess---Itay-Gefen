# main.py
import tkinter as tk
from gui import show_login_screen


def main():
    root = tk.Tk()
    root.title("Chess MVP")
    show_login_screen(root)
    root.mainloop()


if __name__ == "__main__":
    main()
