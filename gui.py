# gui.py
import tkinter as tk
from engine import Game

UNICODE_PIECES = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
    ".": ""
}

class ChessGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess MVP")

        self.game = Game()

        self.square_size = 72
        self.margin = 28
        self.board_pixels = self.square_size * 8
        canvas_size = self.board_pixels + self.margin * 2

        # Top controls
        controls = tk.Frame(root)
        controls.pack(fill="x")

        self.new_game_btn = tk.Button(controls, text="New Game", command=self.on_new_game)
        self.new_game_btn.pack(side="left", padx=6, pady=6)

        self.turn_var = tk.StringVar()
        tk.Label(controls, textvariable=self.turn_var).pack(side="left", padx=10)

        self.canvas = tk.Canvas(root, width=canvas_size, height=canvas_size)
        self.canvas.pack()

        self.status_var = tk.StringVar()
        self.status = tk.Label(root, textvariable=self.status_var, anchor="w")
        self.status.pack(fill="x")

        self.selected = None
        self.legal_squares = set()

        self.canvas.bind("<Button-1>", self.on_click)
        self.redraw()
        self.refresh_status()

    def on_new_game(self):
        self.game.reset()
        self.selected = None
        self.legal_squares = set()
        self.refresh_status()
        self.redraw()

    def refresh_status(self):
        self.turn_var.set(f"Turn: {self.game.turn.capitalize()}")
        self.status_var.set(self.game.last_message if self.game.last_message else "Ready.")

    def row_col_to_square(self, row, col):
        return chr(ord("a") + col) + str(8 - row)

    def ask_promotion(self):
        win = tk.Toplevel(self.root)
        win.title("Promote pawn")
        win.grab_set()  # modal

        tk.Label(win, text="Promote to:").pack(padx=10, pady=10)

        def choose(letter):
            self.game.promote(letter)
            win.destroy()
            self.refresh_status()
            self.redraw()

        row = tk.Frame(win)
        row.pack(padx=10, pady=10)

        for letter, text in [("q", "Queen"), ("r", "Rook"), ("b", "Bishop"), ("n", "Knight")]:
            tk.Button(row, text=text, width=8, command=lambda l=letter: choose(l)).pack(side="left", padx=5)

    def on_click(self, event):
        # If game over, still allow selecting nothing; just tell user.
        if self.game.game_over:
            self.status_var.set("Game over. Press New Game.")
            return

        x = event.x - self.margin
        y = event.y - self.margin
        col = x // self.square_size
        row = y // self.square_size
        if not (0 <= row < 8 and 0 <= col < 8):
            return

        clicked_square = self.row_col_to_square(row, col)
        clicked_piece = self.game.board.grid[row][col]

        if self.selected is None:
            # select only if clicking your own piece
            if self.game.turn == "white" and clicked_piece.isupper():
                self.selected = (row, col)
            elif self.game.turn == "black" and clicked_piece.islower():
                self.selected = (row, col)
            else:
                self.status_var.set(f"{self.game.turn.capitalize()} to move. Select your piece.")
                self.redraw()
                return

            from_square = self.row_col_to_square(*self.selected)
            self.legal_squares = set(self.game.legal_destinations_from(from_square))
            self.refresh_status()
            self.redraw()
            return

        # attempt move
        from_row, from_col = self.selected
        from_square = self.row_col_to_square(from_row, from_col)
        to_square = clicked_square

        self.game.try_move(from_square, to_square)

        # if promotion pending, ask immediately
        if self.game.promotion_pending is not None:
            self.ask_promotion()

        # clear selection after attempt
        self.selected = None
        self.legal_squares = set()

        self.refresh_status()
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")

        # coordinate labels
        for col in range(8):
            file_char = chr(ord("a") + col)
            x = self.margin + col * self.square_size + self.square_size // 2
            self.canvas.create_text(x, self.margin // 2, text=file_char, font=("Arial", 12))
            self.canvas.create_text(x, self.margin + self.board_pixels + self.margin // 2, text=file_char, font=("Arial", 12))

        for row in range(8):
            rank_char = str(8 - row)
            y = self.margin + row * self.square_size + self.square_size // 2
            self.canvas.create_text(self.margin // 2, y, text=rank_char, font=("Arial", 12))
            self.canvas.create_text(self.margin + self.board_pixels + self.margin // 2, y, text=rank_char, font=("Arial", 12))

        # highlight checked king for side-to-move (if any)
        checked_king_square = None
        if self.game.in_check_now(self.game.turn) and not self.game.game_over:
            king_char = "K" if self.game.turn == "white" else "k"
            for r in range(8):
                for c in range(8):
                    if self.game.board.grid[r][c] == king_char:
                        checked_king_square = self.row_col_to_square(r, c)
                        break
                if checked_king_square:
                    break

        # draw squares + pieces
        for row in range(8):
            for col in range(8):
                x1 = self.margin + col * self.square_size
                y1 = self.margin + row * self.square_size
                x2 = x1 + self.square_size
                y2 = y1 + self.square_size

                light = (row + col) % 2 == 0
                fill = "#f0d9b5" if light else "#b58863"

                square = self.row_col_to_square(row, col)

                if self.selected == (row, col):
                    fill = "#f7ec6e"

                if square in self.legal_squares:
                    fill = "#a7e3a1"

                if checked_king_square == square:
                    fill = "#f29b9b"

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")

                piece = self.game.board.grid[row][col]
                symbol = UNICODE_PIECES.get(piece, "")
                if symbol:
                    self.canvas.create_text(
                        (x1 + x2) // 2,
                        (y1 + y2) // 2,
                        text=symbol,
                        font=("Arial", int(self.square_size * 0.55)),
                    )

        # If game over, overlay a message
        if self.game.game_over:
            self.canvas.create_rectangle(
                self.margin, self.margin + self.board_pixels // 2 - 40,
                self.margin + self.board_pixels, self.margin + self.board_pixels // 2 + 40,
                fill="white", outline=""
            )
            self.canvas.create_text(
                self.margin + self.board_pixels // 2,
                self.margin + self.board_pixels // 2,
                text=self.game.last_message,
                font=("Arial", 16, "bold")
            )
