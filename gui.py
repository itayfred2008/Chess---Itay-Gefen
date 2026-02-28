# gui.py
import tkinter as tk
from engine import Game
from database import init_db, login, signup


def show_login_screen(root):
    """Show login screen (first page)."""
    init_db()

    login_frame = tk.Frame(root, padx=40, pady=40)
    login_frame.pack(expand=True, fill="both")

    tk.Label(login_frame, text="Chess MVP", font=("Arial", 28, "bold")).pack(pady=(0, 20))
    tk.Label(login_frame, text="Login", font=("Arial", 16)).pack(pady=(0, 15))

    tk.Label(login_frame, text="Username:").pack(anchor="w")
    username_entry = tk.Entry(login_frame, width=25)
    username_entry.pack(pady=(0, 10))

    tk.Label(login_frame, text="Password:").pack(anchor="w")
    password_entry = tk.Entry(login_frame, width=25, show="*")
    password_entry.pack(pady=(0, 15))

    error_var = tk.StringVar()
    error_label = tk.Label(login_frame, textvariable=error_var, fg="red")
    error_label.pack(pady=(0, 10))

    def on_login():
        success, msg = login(username_entry.get(), password_entry.get())
        if success:
            login_frame.destroy()
            show_start_screen(root, msg)
        else:
            error_var.set(msg)

    tk.Button(login_frame, text="Login", font=("Arial", 12), command=on_login).pack(pady=5)

    def go_to_signup():
        login_frame.destroy()
        show_signup_screen(root)

    tk.Button(login_frame, text="Don't have an account? Sign up", font=("Arial", 10), fg="blue",
              cursor="hand2", command=go_to_signup).pack(pady=15)


def show_signup_screen(root):
    """Show signup screen."""
    signup_frame = tk.Frame(root, padx=40, pady=40)
    signup_frame.pack(expand=True, fill="both")

    tk.Label(signup_frame, text="Chess MVP", font=("Arial", 28, "bold")).pack(pady=(0, 20))
    tk.Label(signup_frame, text="Create Account", font=("Arial", 16)).pack(pady=(0, 15))

    tk.Label(signup_frame, text="Username:").pack(anchor="w")
    username_entry = tk.Entry(signup_frame, width=25)
    username_entry.pack(pady=(0, 10))

    tk.Label(signup_frame, text="Password:").pack(anchor="w")
    password_entry = tk.Entry(signup_frame, width=25, show="*")
    password_entry.pack(pady=(0, 10))

    tk.Label(signup_frame, text="Confirm Password:").pack(anchor="w")
    confirm_entry = tk.Entry(signup_frame, width=25, show="*")
    confirm_entry.pack(pady=(0, 15))

    error_var = tk.StringVar()
    error_label = tk.Label(signup_frame, textvariable=error_var, fg="red")
    error_label.pack(pady=(0, 10))

    def on_signup():
        username = username_entry.get()
        password = password_entry.get()
        confirm = confirm_entry.get()
        if password != confirm:
            error_var.set("Passwords do not match.")
            return
        success, msg = signup(username, password)
        if success:
            signup_frame.destroy()
            show_start_screen(root, username.strip())
        else:
            error_var.set(msg)

    tk.Button(signup_frame, text="Sign Up", font=("Arial", 12), command=on_signup).pack(pady=5)

    def go_to_login():
        signup_frame.destroy()
        show_login_screen(root)

    tk.Button(signup_frame, text="Already have an account? Login", font=("Arial", 10), fg="blue",
              cursor="hand2", command=go_to_login).pack(pady=15)


def show_start_screen(root, username: str):
    """Show start screen with Start Game button."""
    start_frame = tk.Frame(root, padx=40, pady=40)
    start_frame.pack(expand=True, fill="both")

    tk.Label(start_frame, text=f"Hey {username}", font=("Arial", 28, "bold")).pack(pady=(0, 30))

    def on_start_game():
        start_frame.destroy()
        ChessGUI(root)

    tk.Button(start_frame, text="Start Game", font=("Arial", 16), command=on_start_game).pack(pady=10)


UNICODE_PIECES = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
    ".": ""
}

class ChessGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess MVP")
        self.promo_window = None
        self.hover_square = None  # e.g. "e4"

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

        # Middle area: board (left) + move list (right)
        middle = tk.Frame(root)
        middle.pack()

        left = tk.Frame(middle)
        left.pack(side="left")

        right = tk.Frame(middle)
        right.pack(side="left", padx=10, fill="y")

        tk.Label(right, text="Moves").pack(anchor="w")

        self.moves_listbox = tk.Listbox(right, width=22, height=24)
        self.moves_listbox.pack(side="left", fill="y")

        scroll = tk.Scrollbar(right, command=self.moves_listbox.yview)
        scroll.pack(side="left", fill="y")
        self.moves_listbox.config(yscrollcommand=scroll.set)

        self.canvas = tk.Canvas(left, width=canvas_size, height=canvas_size)
        self.canvas.pack()

        self.status_var = tk.StringVar()
        self.status = tk.Label(root, textvariable=self.status_var, anchor="w")
        self.status.pack(fill="x")

        self.selected = None
        self.legal_squares = set()

        self.canvas.tag_bind("board", "<Button-1>", self.on_click)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Leave>", self.on_mouse_leave)

        self.redraw()
        self.refresh_status()

    def on_new_game(self):
        self.game.reset()
        self.selected = None
        self.legal_squares = set()
        self.refresh_move_list()
        self.refresh_status()
        self.redraw()

    def refresh_status(self):
        self.turn_var.set(f"Turn: {self.game.turn.capitalize()}")
        self.status_var.set(self.game.last_message if self.game.last_message else "Ready.")

    def refresh_move_list(self):
        self.moves_listbox.delete(0, tk.END)
        for i, move in enumerate(self.game.move_list, start=1):
            self.moves_listbox.insert(tk.END, f"{i}. {move}")
        if self.game.move_list:
            self.moves_listbox.see(tk.END)

    def is_square_playable(self, square, piece_char):
        # if game is over, nothing is playable
        if self.game.game_over:
            return False

        # if promotion pending, only the promotion window is interactive
        if self.game.promotion_pending is not None:
            return False

        # if no piece selected: you can click your own piece squares
        if self.selected is None:
            if piece_char == ".":
                return False
            if self.game.turn == "white":
                return piece_char.isupper()
            return piece_char.islower()

        # if a piece is selected: you can click legal destination squares
        if square in self.legal_squares:
            return True

        # allow clicking the selected square again (optional)
        from_row, from_col = self.selected
        selected_square = self.row_col_to_square(from_row, from_col)
        return square == selected_square

    def is_capture_destination(self, square):
        # only relevant when a piece is selected and square is a legal destination
        if self.selected is None:
            return False
        if square not in self.legal_squares:
            return False

        row, col = self.square_to_row_col(square)
        target_piece = self.game.board.grid[row][col]

        # normal capture: destination has a piece
        if target_piece != ".":
            return True

        # en passant capture: destination is empty but equals EP target, and selected piece is a pawn moving diagonally
        if self.game.en_passant_target == square:
            from_row, from_col = self.selected
            moving_piece = self.game.board.grid[from_row][from_col]
            if moving_piece.lower() == "p":
                direction = -1 if self.game.turn == "white" else 1
                if (row - from_row) == direction and abs(col - from_col) == 1:
                    return True

        return False

    def on_mouse_move(self, event):
        x = event.x - self.margin
        y = event.y - self.margin
        col = x // self.square_size
        row = y // self.square_size

        # outside board
        if not (0 <= row < 8 and 0 <= col < 8):
            if self.hover_square is not None:
                self.hover_square = None
                self.canvas.config(cursor="arrow")
                self.redraw()
            return

        square = self.row_col_to_square(row, col)
        piece = self.game.board.grid[row][col]
        playable = self.is_square_playable(square, piece)

        # cursor: hand on playable squares
        self.canvas.config(cursor="hand2" if playable else "arrow")

        # hover highlight only if it changed
        if self.hover_square != square:
            self.hover_square = square
            self.redraw()

    def on_mouse_leave(self, _event):
        self.hover_square = None
        self.canvas.config(cursor="arrow")
        self.redraw()

    def row_col_to_square(self, row, col):
        return chr(ord("a") + col) + str(8 - row)

    def square_to_row_col(self, square):
        col = ord(square[0]) - ord("a")
        row = 8 - int(square[1])
        return row, col

    def pixel_to_square(self, x, y):
        x -= self.margin
        y -= self.margin
        col = x // self.square_size
        row = y // self.square_size
        if not (0 <= row < 8 and 0 <= col < 8):
            return None
        return self.row_col_to_square(row, col)

    def on_mouse_down(self, event):
        square = self.pixel_to_square(event.x, event.y)
        if not square:
            return

        row, col = self.square_to_row_col(square)
        piece = self.game.board.grid[row][col]
        if self.is_square_playable(square, piece):
            self.canvas.config(cursor="fleur")  # pressed hand

    def on_mouse_up(self, event):
        square = self.pixel_to_square(event.x, event.y)
        if not square:
            self.canvas.config(cursor="arrow")
            return

        row, col = self.square_to_row_col(square)
        piece = self.game.board.grid[row][col]
        if self.is_square_playable(square, piece):
            self.canvas.config(cursor="hand2")
        else:
            self.canvas.config(cursor="arrow")

    def ask_promotion(self):
        # If it's already open, just focus it
        if self.promo_window is not None and self.promo_window.winfo_exists():
            self.promo_window.lift()
            self.promo_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.promo_window = win
        win.title("Promote pawn")
        win.grab_set()  # modal

        win.protocol("WM_DELETE_WINDOW", lambda: None)  # disable X
        win.transient(self.root)  # stays on top of main window

        # Position near the promoted pawn square
        square = self.game.promotion_pending  # like "e8"
        if square:
            col = ord(square[0]) - ord("a")
            row = 8 - int(square[1])

            # canvas absolute position on screen
            canvas_x = self.canvas.winfo_rootx()
            canvas_y = self.canvas.winfo_rooty()

            # square top-left in screen coordinates
            x = canvas_x + self.margin + col * self.square_size
            y = canvas_y + self.margin + row * self.square_size

            # open slightly to the right of the square (and aligned vertically)
            win.geometry(f"+{x + self.square_size + 10}+{y}")

        tk.Label(win, text="Promote to:").pack(padx=10, pady=10)

        def choose(letter):
            self.game.promote(letter)
            win.grab_release()
            win.destroy()
            self.promo_window = None
            self.refresh_move_list()
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

        if self.game.promotion_pending is not None:
            self.ask_promotion()
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

        moved = self.game.try_move(from_square, to_square)
        if moved:
            self.refresh_move_list()

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

                # hover highlight on playable square
                if self.hover_square == square:
                    piece_here = self.game.board.grid[row][col]
                    if self.is_square_playable(square, piece_here):
                        # red hover if this square is a capturable destination
                        if self.is_capture_destination(square):
                            fill = "#ffb3b3"  # light red
                        else:
                            fill = "#cfe8ff"  # light blue

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="", tags=("board",))

                piece = self.game.board.grid[row][col]
                symbol = UNICODE_PIECES.get(piece, "")
                if symbol:
                    self.canvas.create_text(
                        (x1 + x2) // 2,
                        (y1 + y2) // 2,
                        text=symbol,
                        font=("Arial", int(self.square_size * 0.55)),
                        tags=("board",),
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
