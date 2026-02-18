# main.py
import tkinter as tk
from gui import ChessGUI

def main():
    root = tk.Tk()
    ChessGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
