import socket
import threading
import json
import queue
import tkinter as tk
from tkinter import messagebox

from engine import Game

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000

UNICODE_PIECES = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
    ".": ""
}


def send_json(sock, data, lock):
    raw = (json.dumps(data) + "\n").encode("utf-8")
    with lock:
        sock.sendall(raw)


class NetworkClient:
    def __init__(self, host, port, on_message, on_disconnect):
        self.host = host
        self.port = port
        self.on_message = on_message
        self.on_disconnect = on_disconnect

        self.sock = None
        self.file = None
        self.send_lock = threading.Lock()
        self.alive = False

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.file = self.sock.makefile("r", encoding="utf-8")
        self.alive = True
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def _recv_loop(self):
        try:
            while self.alive:
                line = self.file.readline()
                if not line:
                    break
                msg = json.loads(line.strip())
                self.on_message(msg)
        except Exception:
            pass
        finally:
            self.alive = False
            self.on_disconnect()

    def send(self, data):
        if not self.alive:
            return
        send_json(self.sock, data, self.send_lock)

    def close(self):
        self.alive = False

        try:
            if self.sock:
                self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass

        try:
            if self.file:
                self.file.close()
        except Exception:
            pass

        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


class ChessClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Chess Client")

        self.closing = False
        self.after_id = None

        self.net_queue = queue.Queue()
        self.client = NetworkClient(
            SERVER_HOST,
            SERVER_PORT,
            on_message=self.net_queue.put,
            on_disconnect=lambda: self.net_queue.put({"type": "disconnected"})
        )

        self.username = None
        self.current_room_id = None
        self.current_room_name = None
        self.my_color = None
        self.both_connected = False

        self.server_game = Game()
        self.selected = None
        self.legal_squares = set()
        self.hover_square = None
        self.promo_window = None

        self.rooms_cache = []

        self.square_size = 72
        self.margin = 28
        self.board_pixels = self.square_size * 8

        self.main_frame = None

        self.client.connect()
        self.show_login_screen()
        self.after_id = self.root.after(100, self.process_network)

        self.draw_offer_from = None
        self.rematch_votes = []

    def clear_main(self):
        if self.main_frame is not None:
            self.main_frame.destroy()
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(expand=True, fill="both")

    def process_network(self):
        if self.closing:
            return

        while True:
            try:
                msg = self.net_queue.get_nowait()
            except queue.Empty:
                break

            if self.closing:
                return

            self.handle_server_message(msg)

        if not self.closing:
            self.after_id = self.root.after(100, self.process_network)

    def handle_server_message(self, msg):
        msg_type = msg.get("type")

        if msg_type == "disconnected":
            if self.closing:
                return

            messagebox.showerror("Disconnected", "Lost connection to server.")
            self.root.destroy()

        elif msg_type == "info":
            pass

        elif msg_type == "auth_ok":
            self.username = msg["username"]
            self.show_lobby_screen()
            self.client.send({"type": "list_rooms"})


        elif msg_type == "auth_error":
            error_message = msg.get("message", "Authentication failed.")

            if hasattr(self, "auth_error_var"):
                self.auth_error_var.set(error_message)

            messagebox.showerror("Login Error", error_message)

        elif msg_type == "room_list":
            self.rooms_cache = msg.get("rooms", [])
            self.refresh_room_listbox()


        elif msg_type == "room_joined":
            self.current_room_id = msg["room_id"]
            self.current_room_name = msg["room_name"]
            self.my_color = msg["your_color"]
            self.both_connected = False
            self.draw_offer_from = None
            self.rematch_votes = []
            self.show_room_screen()

        elif msg_type == "opponent_left":
            messagebox.showinfo("Player Left", msg.get("message", "The other player left the room."))

        elif msg_type == "left_room":
            self.current_room_id = None
            self.current_room_name = None
            self.my_color = None
            self.both_connected = False
            self.draw_offer_from = None
            self.rematch_votes = []
            self.selected = None
            self.legal_squares = set()
            self.show_lobby_screen()
            self.client.send({"type": "list_rooms"})

        elif msg_type == "game_state":
            self.apply_game_state(msg)
            self.refresh_move_list()
            self.refresh_status()
            self.refresh_action_buttons()
            self.redraw()
            if hasattr(self, "board_canvas"):
                self.refresh_move_list()
                self.refresh_status()
                self.redraw()

            if self.server_game.promotion_pending is not None and self.server_game.turn == self.my_color:
                self.ask_promotion()

        elif msg_type == "error":
            if hasattr(self, "status_var"):
                self.status_var.set(msg.get("message", "Unknown error."))
            else:
                messagebox.showerror("Error", msg.get("message", "Unknown error."))

    def on_offer_draw_click(self):
        if self.server_game.game_over:
            return
        self.client.send({"type": "offer_draw"})

    def on_respond_draw(self, accept):
        self.client.send({
            "type": "respond_draw",
            "accept": accept
        })

    def on_vote_rematch_click(self):
        if not self.server_game.game_over:
            messagebox.showinfo("New Game", "You can only vote for a new game after the game ends.")
            return
        self.client.send({"type": "vote_rematch"})

    def apply_game_state(self, state):
        game = Game()

        board_rows = state["board"]
        game.board.grid = [list(row) for row in board_rows]
        game.board.moved = dict(state.get("moved", {}))
        game.turn = state["turn"]
        game.last_message = state.get("last_message", "")
        game.game_over = state.get("game_over", False)
        game.result = state.get("result")
        game.promotion_pending = state.get("promotion_pending")
        game.en_passant_target = state.get("en_passant_target")
        game.move_list = list(state.get("move_list", []))

        self.server_game = game
        self.my_color = state.get("your_color", self.my_color)
        self.both_connected = state.get("both_connected", False)

        self.white_username_var.set(f"White: {state.get('white_username') or '-'}")
        self.black_username_var.set(f"Black: {state.get('black_username') or '-'}")

        both = state.get("both_connected", False)
        room_text = f"Room: {state.get('room_name', '-')}"
        if not both:
            room_text += "  |  Waiting for second player..."
        self.room_info_var.set(room_text)

        self.selected = None
        self.legal_squares = set()

        self.draw_offer_from = state.get("draw_offer_from")
        self.rematch_votes = list(state.get("rematch_votes", []))

    def refresh_action_buttons(self):
        if not hasattr(self, "action_frame"):
            return

        for widget in self.action_frame.winfo_children():
            widget.pack_forget()

        # Waiting for second player
        if not self.both_connected:
            self.leave_room_btn.pack(side="left", padx=6)
            return

        # During active game
        if not self.server_game.game_over:
            if self.draw_offer_from is None:
                self.offer_draw_btn.pack(side="left", padx=6)
            else:
                # Other player offered draw -> show accept/decline
                if self.draw_offer_from != self.my_color:
                    self.accept_draw_btn.pack(side="left", padx=6)
                    self.decline_draw_btn.pack(side="left", padx=6)

            self.surrender_btn.pack(side="left", padx=6)
            return

        # After game over
        self.vote_rematch_btn.pack(side="left", padx=6)
        self.leave_room_btn.pack(side="left", padx=6)


    def show_login_screen(self):
        self.clear_main()

        frame = tk.Frame(self.main_frame, padx=40, pady=40)
        frame.pack(expand=True)

        tk.Label(frame, text="Chess Client", font=("Arial", 28, "bold")).pack(pady=(0, 20))
        tk.Label(frame, text="Login", font=("Arial", 16)).pack(pady=(0, 15))

        tk.Label(frame, text="Username:").pack(anchor="w")
        self.login_username_entry = tk.Entry(frame, width=25)
        self.login_username_entry.pack(pady=(0, 10))

        tk.Label(frame, text="Password:").pack(anchor="w")
        self.login_password_entry = tk.Entry(frame, width=25, show="*")
        self.login_password_entry.pack(pady=(0, 15))

        self.auth_error_var = tk.StringVar()
        tk.Label(frame, textvariable=self.auth_error_var, fg="red").pack(pady=(0, 10))

        tk.Button(frame, text="Login", width=18, command=self.on_login).pack(pady=5)
        tk.Button(frame, text="Go to Sign Up", width=18, command=self.show_signup_screen).pack(pady=5)

    def show_signup_screen(self):
        self.clear_main()

        frame = tk.Frame(self.main_frame, padx=40, pady=40)
        frame.pack(expand=True)

        tk.Label(frame, text="Chess Client", font=("Arial", 28, "bold")).pack(pady=(0, 20))
        tk.Label(frame, text="Create Account", font=("Arial", 16)).pack(pady=(0, 15))

        tk.Label(frame, text="Username:").pack(anchor="w")
        self.signup_username_entry = tk.Entry(frame, width=25)
        self.signup_username_entry.pack(pady=(0, 10))

        tk.Label(frame, text="Password:").pack(anchor="w")
        self.signup_password_entry = tk.Entry(frame, width=25, show="*")
        self.signup_password_entry.pack(pady=(0, 10))

        tk.Label(frame, text="Confirm Password:").pack(anchor="w")
        self.signup_confirm_entry = tk.Entry(frame, width=25, show="*")
        self.signup_confirm_entry.pack(pady=(0, 15))

        tk.Label(
            frame,
            text=(
                "Password requirements:\n"
                "- at least 8 characters\n"
                "- one lowercase letter\n"
                "- one uppercase letter\n"
                "- one digit\n"
                "- one special character"
            ),
            justify="left",
            fg="gray"
        ).pack(anchor="w", pady=(0, 15))

        self.auth_error_var = tk.StringVar()
        tk.Label(frame, textvariable=self.auth_error_var, fg="red").pack(pady=(0, 10))

        tk.Button(frame, text="Sign Up", width=18, command=self.on_signup).pack(pady=5)
        tk.Button(frame, text="Back to Login", width=18, command=self.show_login_screen).pack(pady=5)

    def on_login(self):
        username = self.login_username_entry.get().strip()
        password = self.login_password_entry.get()
        self.client.send({
            "type": "login",
            "username": username,
            "password": password
        })

    def on_signup(self):
        username = self.signup_username_entry.get().strip()
        password = self.signup_password_entry.get()
        confirm = self.signup_confirm_entry.get()

        if password != confirm:
            self.auth_error_var.set("Passwords do not match.")
            return

        self.client.send({
            "type": "signup",
            "username": username,
            "password": password
        })

    # ---------- LOBBY UI ----------

    def show_lobby_screen(self):
        self.clear_main()

        frame = tk.Frame(self.main_frame, padx=20, pady=20)
        frame.pack(expand=True, fill="both")

        tk.Label(frame, text=f"Welcome, {self.username}", font=("Arial", 24, "bold")).pack(pady=(0, 15))
        tk.Label(frame, text="Rooms", font=("Arial", 16)).pack()

        top = tk.Frame(frame)
        top.pack(pady=10)

        self.create_room_entry = tk.Entry(top, width=30)
        self.create_room_entry.pack(side="left", padx=5)
        self.create_room_entry.insert(0, f"{self.username}'s Room")

        tk.Button(top, text="Create Room", command=self.on_create_room).pack(side="left", padx=5)
        tk.Button(top, text="Refresh", command=lambda: self.client.send({"type": "list_rooms"})).pack(side="left", padx=5)

        list_frame = tk.Frame(frame)
        list_frame.pack(pady=10, fill="both", expand=True)

        self.rooms_listbox = tk.Listbox(list_frame, width=60, height=15)
        self.rooms_listbox.pack(side="left", fill="both", expand=True)

        scroll = tk.Scrollbar(list_frame, command=self.rooms_listbox.yview)
        scroll.pack(side="left", fill="y")
        self.rooms_listbox.config(yscrollcommand=scroll.set)

        tk.Button(frame, text="Join Selected Room", command=self.on_join_selected_room).pack(pady=8)

    def refresh_room_listbox(self):
        if not hasattr(self, "rooms_listbox"):
            return

        self.rooms_listbox.delete(0, tk.END)
        for room in self.rooms_cache:
            text = (
                f"ID {room['room_id']} | {room['name']} | "
                f"Players: {room['players']}/2 | "
                f"White: {room.get('white_username') or '-'} | "
                f"Black: {room.get('black_username') or '-'}"
            )
            self.rooms_listbox.insert(tk.END, text)

    def on_create_room(self):
        name = self.create_room_entry.get().strip()
        self.client.send({
            "type": "create_room",
            "name": name
        })

    def on_join_selected_room(self):
        selection = self.rooms_listbox.curselection()
        if not selection:
            messagebox.showinfo("Join Room", "Select a room first.")
            return

        index = selection[0]
        room = self.rooms_cache[index]
        self.client.send({
            "type": "join_room",
            "room_id": room["room_id"]
        })

    def on_new_game_click(self):
        if not self.server_game.game_over:
            messagebox.showinfo("New Game", "You can only start a new game after the current game is finished.")
            return

        if not self.both_connected:
            messagebox.showinfo("New Game", "Both players must be in the room to start a new game.")
            return

        self.client.send({"type": "new_game"})

    def on_surrender_click(self):
        if not self.both_connected:
            messagebox.showinfo("Surrender", "You cannot surrender before both players join.")
            return

        if self.server_game.game_over:
            messagebox.showinfo("Surrender", "The game is already over.")
            return

        answer = messagebox.askyesno("Surrender", "Are you sure you want to surrender?")
        if answer:
            self.client.send({"type": "surrender"})

    # ---------- ROOM / BOARD UI ----------

    def show_room_screen(self):
        self.clear_main()

        container = tk.Frame(self.main_frame)
        container.pack(expand=True, fill="both")

        top = tk.Frame(container)
        top.pack(fill="x")

        self.room_info_var = tk.StringVar(value=f"Room: {self.current_room_name}")
        tk.Label(top, textvariable=self.room_info_var).pack(side="left", padx=10)

        self.turn_var = tk.StringVar()
        tk.Label(top, textvariable=self.turn_var).pack(side="left", padx=10)

        self.white_username_var = tk.StringVar(value="White: -")
        self.black_username_var = tk.StringVar(value="Black: -")
        tk.Label(top, textvariable=self.white_username_var).pack(side="right", padx=8)
        tk.Label(top, textvariable=self.black_username_var).pack(side="right", padx=8)

        middle = tk.Frame(container)
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

        canvas_size = self.board_pixels + self.margin * 2
        self.board_canvas = tk.Canvas(left, width=canvas_size, height=canvas_size)
        self.board_canvas.pack()

        self.board_canvas.tag_bind("board", "<Button-1>", self.on_click)
        self.board_canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.board_canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.board_canvas.bind("<Motion>", self.on_mouse_move)
        self.board_canvas.bind("<Leave>", self.on_mouse_leave)

        self.status_var = tk.StringVar(value="Waiting for state...")
        tk.Label(container, textvariable=self.status_var, anchor="w").pack(fill="x")

        self.action_frame = tk.Frame(container)
        self.action_frame.pack(pady=8)

        self.offer_draw_btn = tk.Button(self.action_frame, text="Offer Draw", command=self.on_offer_draw_click)
        self.accept_draw_btn = tk.Button(self.action_frame, text="Accept Draw",
                                         command=lambda: self.on_respond_draw(True))
        self.decline_draw_btn = tk.Button(self.action_frame, text="Decline Draw",
                                          command=lambda: self.on_respond_draw(False))
        self.vote_rematch_btn = tk.Button(self.action_frame, text="Vote New Game", command=self.on_vote_rematch_click)
        self.leave_room_btn = tk.Button(self.action_frame, text="Leave Room",
                                        command=lambda: self.client.send({"type": "leave_room"}))
        self.surrender_btn = tk.Button(self.action_frame, text="Surrender", command=self.on_surrender_click)

        self.refresh_action_buttons()
        self.refresh_move_list()
        self.refresh_status()
        self.redraw()

    def refresh_status(self):
        turn_text = self.server_game.turn.capitalize()
        color_text = self.my_color.capitalize() if self.my_color else "Unknown"
        self.turn_var.set(f"Turn: {turn_text} | You are: {color_text}")
        self.status_var.set(self.server_game.last_message if self.server_game.last_message else "Ready.")

    def refresh_move_list(self):
        if not hasattr(self, "moves_listbox"):
            return

        self.moves_listbox.delete(0, tk.END)
        for i, move in enumerate(self.server_game.move_list, start=1):
            self.moves_listbox.insert(tk.END, f"{i}. {move}")

        if self.server_game.move_list:
            self.moves_listbox.see(tk.END)

    def is_board_flipped(self):
        return self.my_color == "black"

    def row_col_to_square(self, row, col):
        return chr(ord("a") + col) + str(8 - row)

    def square_to_row_col(self, square):
        col = ord(square[0]) - ord("a")
        row = 8 - int(square[1])
        return row, col

    def board_to_display_row_col(self, row, col):
        if self.is_board_flipped():
            return 7 - row, 7 - col
        return row, col

    def display_to_board_row_col(self, row, col):
        if self.is_board_flipped():
            return 7 - row, 7 - col
        return row, col

    def pixel_to_square(self, x, y):
        x -= self.margin
        y -= self.margin

        display_col = x // self.square_size
        display_row = y // self.square_size

        if not (0 <= display_row < 8 and 0 <= display_col < 8):
            return None

        board_row, board_col = self.display_to_board_row_col(display_row, display_col)
        return self.row_col_to_square(board_row, board_col)

    def is_my_turn(self):
        return self.my_color == self.server_game.turn

    def is_square_playable(self, square, piece_char):
        if self.server_game.game_over:
            return False

        if self.server_game.promotion_pending is not None:
            return False

        if not self.both_connected:
            return False

        if not self.is_my_turn():
            return False

        if self.selected is None:
            if piece_char == ".":
                return False
            return piece_char.isupper() if self.my_color == "white" else piece_char.islower()

        if square in self.legal_squares:
            return True

        from_row, from_col = self.selected
        selected_square = self.row_col_to_square(from_row, from_col)
        return square == selected_square

    def is_capture_destination(self, square):
        if self.selected is None:
            return False
        if square not in self.legal_squares:
            return False

        row, col = self.square_to_row_col(square)
        target_piece = self.server_game.board.grid[row][col]

        if target_piece != ".":
            return True

        if self.server_game.en_passant_target == square:
            from_row, from_col = self.selected
            moving_piece = self.server_game.board.grid[from_row][from_col]
            if moving_piece.lower() == "p":
                direction = -1 if self.server_game.turn == "white" else 1
                if (row - from_row) == direction and abs(col - from_col) == 1:
                    return True

        return False

    def on_mouse_move(self, event):
        if not hasattr(self, "board_canvas"):
            return

        square = self.pixel_to_square(event.x, event.y)

        if square is None:
            if self.hover_square is not None:
                self.hover_square = None
                self.board_canvas.config(cursor="arrow")
                self.redraw()
            return

        row, col = self.square_to_row_col(square)
        piece = self.server_game.board.grid[row][col]
        playable = self.is_square_playable(square, piece)

        self.board_canvas.config(cursor="hand2" if playable else "arrow")

        if self.hover_square != square:
            self.hover_square = square
            self.redraw()

    def on_mouse_leave(self, _event):
        self.hover_square = None
        self.board_canvas.config(cursor="arrow")
        self.redraw()

    def on_mouse_down(self, event):
        square = self.pixel_to_square(event.x, event.y)
        if not square:
            return

        row, col = self.square_to_row_col(square)
        piece = self.server_game.board.grid[row][col]
        if self.is_square_playable(square, piece):
            self.board_canvas.config(cursor="fleur")

    def on_mouse_up(self, event):
        square = self.pixel_to_square(event.x, event.y)
        if not square:
            self.board_canvas.config(cursor="arrow")
            return

        row, col = self.square_to_row_col(square)
        piece = self.server_game.board.grid[row][col]
        if self.is_square_playable(square, piece):
            self.board_canvas.config(cursor="hand2")
        else:
            self.board_canvas.config(cursor="arrow")

    def ask_promotion(self):
        if self.promo_window is not None and self.promo_window.winfo_exists():
            self.promo_window.lift()
            self.promo_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.promo_window = win
        win.title("Promote pawn")
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        win.transient(self.root)

        square = self.server_game.promotion_pending
        if square and hasattr(self, "board_canvas"):
            row, col = self.square_to_row_col(square)
            display_row, display_col = self.board_to_display_row_col(row, col)

            canvas_x = self.board_canvas.winfo_rootx()
            canvas_y = self.board_canvas.winfo_rooty()

            x = canvas_x + self.margin + display_col * self.square_size
            y = canvas_y + self.margin + display_row * self.square_size

            win.geometry(f"+{x + self.square_size + 10}+{y}")

        tk.Label(win, text="Promote to:").pack(padx=10, pady=10)

        row_frame = tk.Frame(win)
        row_frame.pack(padx=10, pady=10)

        def choose(letter):
            self.client.send({
                "type": "promote",
                "piece": letter
            })
            win.grab_release()
            win.destroy()
            self.promo_window = None

        for letter, text in [("q", "Queen"), ("r", "Rook"), ("b", "Bishop"), ("n", "Knight")]:
            tk.Button(row_frame, text=text, width=8, command=lambda l=letter: choose(l)).pack(side="left", padx=5)

    def on_click(self, event):
        if self.server_game.game_over:
            self.status_var.set("Game over. Press New Game.")
            return

        if not self.both_connected:
            self.status_var.set("Waiting for second player to join.")
            return

        if self.server_game.promotion_pending is not None:
            if self.is_my_turn():
                self.ask_promotion()
            return

        clicked_square = self.pixel_to_square(event.x, event.y)
        if not clicked_square:
            return

        row, col = self.square_to_row_col(clicked_square)
        clicked_piece = self.server_game.board.grid[row][col]

        if self.selected is None:
            if not self.is_my_turn():
                self.status_var.set("Wait for your turn.")
                self.redraw()
                return

            if self.my_color == "white" and clicked_piece.isupper():
                self.selected = (row, col)
            elif self.my_color == "black" and clicked_piece.islower():
                self.selected = (row, col)
            else:
                self.status_var.set(f"{self.server_game.turn.capitalize()} to move. Select your piece.")
                self.redraw()
                return

            from_square = self.row_col_to_square(*self.selected)
            self.legal_squares = set(self.server_game.legal_destinations_from(from_square))
            self.refresh_status()
            self.redraw()
            return

        from_row, from_col = self.selected
        from_square = self.row_col_to_square(from_row, from_col)
        to_square = clicked_square

        self.selected = None
        self.legal_squares = set()
        self.redraw()

        self.client.send({
            "type": "make_move",
            "from": from_square,
            "to": to_square
        })

    def redraw(self):
        if not hasattr(self, "board_canvas"):
            return

        canvas = self.board_canvas
        canvas.delete("all")

        for col in range(8):
            file_char = chr(ord("a") + col)
            x = self.margin + col * self.square_size + self.square_size // 2
            canvas.create_text(x, self.margin // 2, text=file_char, font=("Arial", 12))
            canvas.create_text(x, self.margin + self.board_pixels + self.margin // 2, text=file_char, font=("Arial", 12))

        for row in range(8):
            rank_char = str(8 - row)
            y = self.margin + row * self.square_size + self.square_size // 2
            canvas.create_text(self.margin // 2, y, text=rank_char, font=("Arial", 12))
            canvas.create_text(self.margin + self.board_pixels + self.margin // 2, y, text=rank_char, font=("Arial", 12))

        checked_king_square = None
        if self.server_game.in_check_now(self.server_game.turn) and not self.server_game.game_over:
            king_char = "K" if self.server_game.turn == "white" else "k"
            for r in range(8):
                for c in range(8):
                    if self.server_game.board.grid[r][c] == king_char:
                        checked_king_square = self.row_col_to_square(r, c)
                        break
                if checked_king_square:
                    break

        for display_row in range(8):
            for display_col in range(8):
                row, col = self.display_to_board_row_col(display_row, display_col)
                x1 = self.margin + display_col * self.square_size
                y1 = self.margin + display_row * self.square_size
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

                if self.hover_square == square:
                    piece_here = self.server_game.board.grid[row][col]
                    if self.is_square_playable(square, piece_here):
                        if self.is_capture_destination(square):
                            fill = "#ffb3b3"
                        else:
                            fill = "#cfe8ff"

                canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="", tags=("board",))

                piece = self.server_game.board.grid[row][col]
                symbol = UNICODE_PIECES.get(piece, "")
                if symbol:
                    canvas.create_text(
                        (x1 + x2) // 2,
                        (y1 + y2) // 2,
                        text=symbol,
                        font=("Arial", int(self.square_size * 0.55)),
                        tags=("board",),
                    )

        if self.server_game.game_over:
            canvas.create_rectangle(
                self.margin, self.margin + self.board_pixels // 2 - 40,
                self.margin + self.board_pixels, self.margin + self.board_pixels // 2 + 40,
                fill="white", outline=""
            )
            canvas.create_text(
                self.margin + self.board_pixels // 2,
                self.margin + self.board_pixels // 2 - 12,
                text=self.server_game.last_message,
                font=("Arial", 16, "bold")
            )

            canvas.create_text(
                self.margin + self.board_pixels // 2,
                self.margin + self.board_pixels // 2 + 16,
                text="Use Vote New Game below if you want a rematch.",
                font=("Arial", 11)
            )


def main():
    root = tk.Tk()
    app = ChessClientApp(root)

    def on_close():
        app.closing = True

        try:
            if app.after_id is not None:
                root.after_cancel(app.after_id)
        except Exception:
            pass

        try:
            app.client.close()
        except Exception:
            pass

        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()