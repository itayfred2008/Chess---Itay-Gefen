# engine.py

def is_white_piece(ch):
    return ch != "." and ch.isupper()

def is_black_piece(ch):
    return ch != "." and ch.islower()

def sign(x):
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


class Board:
    def __init__(self):
        self.grid = [["." for _ in range(8)] for _ in range(8)]
        self.moved = {
            "white_king": False,
            "white_rook_a": False,
            "white_rook_h": False,
            "black_king": False,
            "black_rook_a": False,
            "black_rook_h": False,
        }

    def reset(self):
        self.grid = [["." for _ in range(8)] for _ in range(8)]
        self.moved = {
            "white_king": False,
            "white_rook_a": False,
            "white_rook_h": False,
            "black_king": False,
            "black_rook_a": False,
            "black_rook_h": False,
        }
        self.setup_start_position()

    def setup_start_position(self):
        self.grid[0] = list("rnbqkbnr")
        self.grid[1] = ["p"] * 8
        for row in range(2, 6):
            self.grid[row] = ["."] * 8
        self.grid[6] = ["P"] * 8
        self.grid[7] = list("RNBQKBNR")

    def is_valid_square(self, square):
        return len(square) == 2 and ("a" <= square[0] <= "h") and ("1" <= square[1] <= "8")

    def square_to_index(self, square):
        col = ord(square[0]) - ord("a")
        row = 8 - int(square[1])
        return row, col

    def index_to_square(self, row, col):
        return chr(ord("a") + col) + str(8 - row)

    def get_piece(self, square):
        row, col = self.square_to_index(square)
        return self.grid[row][col]

    def _set_raw(self, square, piece_char):
        row, col = self.square_to_index(square)
        self.grid[row][col] = piece_char

    def _move_raw(self, from_square, to_square):
        piece = self.get_piece(from_square)
        self._set_raw(from_square, ".")
        self._set_raw(to_square, piece)

    def make_move(self, from_square, to_square, en_passant_target=None, turn=None):
        undo = {
            "from": from_square,
            "to": to_square,
            "captured": self.get_piece(to_square),
            "castling": False,
            "rook_from": None,
            "rook_to": None,
            "moved_before": self.moved.copy(),
            "en_passant": False,
            "ep_captured_square": None,
            "ep_captured_piece": None,
        }

        moving_piece = self.get_piece(from_square)
        from_row, from_col = self.square_to_index(from_square)
        to_row, to_col = self.square_to_index(to_square)

        # --- En Passant special move ---
        if (
                moving_piece.lower() == "p"
                and en_passant_target is not None
                and turn is not None
        ):
            # If pawn moves diagonally into EMPTY square that equals en_passant_target
            if self.get_piece(to_square) == ".":
                direction = -1 if turn == "white" else 1
                if (to_row - from_row) == direction and abs(to_col - from_col) == 1 and to_square == en_passant_target:
                    # captured pawn is behind the target square
                    captured_row = to_row - direction
                    captured_col = to_col
                    captured_square = self.index_to_square(captured_row, captured_col)

                    undo["en_passant"] = True
                    undo["ep_captured_square"] = captured_square
                    undo["ep_captured_piece"] = self.get_piece(captured_square)

                    # move pawn
                    self._move_raw(from_square, to_square)
                    self._update_moved_flags(from_square, moving_piece)

                    # remove captured pawn
                    self._set_raw(captured_square, ".")
                    return undo
        # ------------------------------

        # Castling: king moves 2 squares horizontally
        if moving_piece.lower() == "k" and from_row == to_row and abs(to_col - from_col) == 2:
            undo["castling"] = True

            if to_col > from_col:  # kingside
                rook_from_col, rook_to_col = 7, 5
            else:  # queenside
                rook_from_col, rook_to_col = 0, 3

            rook_from_square = self.index_to_square(from_row, rook_from_col)
            rook_to_square = self.index_to_square(from_row, rook_to_col)

            undo["rook_from"] = rook_from_square
            undo["rook_to"] = rook_to_square

            # move king then rook
            self._move_raw(from_square, to_square)
            rook_piece = self.get_piece(rook_from_square)
            self._move_raw(rook_from_square, rook_to_square)

            self._update_moved_flags(from_square, moving_piece)
            self._update_moved_flags(rook_from_square, rook_piece)
            return undo

        # Normal move
        self._move_raw(from_square, to_square)
        self._update_moved_flags(from_square, moving_piece)
        return undo

    def undo_move(self, undo):
        self.moved = undo["moved_before"]

        from_square = undo["from"]
        to_square = undo["to"]

        # --- Undo En Passant ---
        if undo.get("en_passant"):
            # move pawn back
            self._move_raw(to_square, from_square)
            # restore captured pawn
            self._set_raw(undo["ep_captured_square"], undo["ep_captured_piece"])
            return
        # ----------------------

        if undo["castling"]:
            rook_from = undo["rook_from"]
            rook_to = undo["rook_to"]
            self._move_raw(rook_to, rook_from)
            self._move_raw(to_square, from_square)
            return

        moved_piece = self.get_piece(to_square)
        self._set_raw(to_square, undo["captured"])
        self._set_raw(from_square, moved_piece)

    def _update_moved_flags(self, from_square, piece_char):
        if piece_char == "K":
            self.moved["white_king"] = True
        elif piece_char == "k":
            self.moved["black_king"] = True
        elif piece_char == "R":
            if from_square == "a1":
                self.moved["white_rook_a"] = True
            elif from_square == "h1":
                self.moved["white_rook_h"] = True
        elif piece_char == "r":
            if from_square == "a8":
                self.moved["black_rook_a"] = True
            elif from_square == "h8":
                self.moved["black_rook_h"] = True


def path_is_clear(board, from_row, from_col, to_row, to_col):
    step_row = sign(to_row - from_row)
    step_col = sign(to_col - from_col)
    r = from_row + step_row
    c = from_col + step_col
    while (r, c) != (to_row, to_col):
        if board.grid[r][c] != ".":
            return False
        r += step_row
        c += step_col
    return True


def find_king(board, color):
    king_char = "K" if color == "white" else "k"
    for row in range(8):
        for col in range(8):
            if board.grid[row][col] == king_char:
                return row, col
    return None


def square_is_attacked(board, target_row, target_col, attacker_color):
    for row in range(8):
        for col in range(8):
            piece = board.grid[row][col]
            if piece == ".":
                continue

            if attacker_color == "white" and not is_white_piece(piece):
                continue
            if attacker_color == "black" and not is_black_piece(piece):
                continue

            piece_type = piece.lower()
            delta_row = target_row - row
            delta_col = target_col - col
            abs_row = abs(delta_row)
            abs_col = abs(delta_col)

            if piece_type == "p":
                direction = -1 if attacker_color == "white" else 1
                if delta_row == direction and abs_col == 1:
                    return True

            elif piece_type == "n":
                if (abs_row, abs_col) in [(1, 2), (2, 1)]:
                    return True

            elif piece_type == "b":
                if abs_row == abs_col and abs_row != 0 and path_is_clear(board, row, col, target_row, target_col):
                    return True

            elif piece_type == "r":
                straight = (delta_row == 0 and delta_col != 0) or (delta_col == 0 and delta_row != 0)
                if straight and path_is_clear(board, row, col, target_row, target_col):
                    return True

            elif piece_type == "q":
                diagonal = (abs_row == abs_col and abs_row != 0)
                straight = (delta_row == 0 and delta_col != 0) or (delta_col == 0 and delta_row != 0)
                if (diagonal or straight) and path_is_clear(board, row, col, target_row, target_col):
                    return True

            elif piece_type == "k":
                if max(abs_row, abs_col) == 1 and (abs_row + abs_col) > 0:
                    return True

    return False


def king_in_check(board, color):
    pos = find_king(board, color)
    if pos is None:
        return False
    king_row, king_col = pos
    attacker = "black" if color == "white" else "white"
    return square_is_attacked(board, king_row, king_col, attacker)


def can_castle(board, from_square, to_square, turn):
    if turn == "white":
        if from_square != "e1":
            return False, "Castling: king must start on e1"
        if board.moved["white_king"]:
            return False, "Castling: king already moved"
    else:
        if from_square != "e8":
            return False, "Castling: king must start on e8"
        if board.moved["black_king"]:
            return False, "Castling: king already moved"

    from_row, from_col = board.square_to_index(from_square)
    to_row, to_col = board.square_to_index(to_square)

    if from_row != to_row or abs(to_col - from_col) != 2:
        return False, "Not a castling move"

    if king_in_check(board, turn):
        return False, "Castling: king is currently in check"

    opponent = "black" if turn == "white" else "white"

    if to_col > from_col:  # kingside
        rook_square = "h1" if turn == "white" else "h8"
        rook_piece = "R" if turn == "white" else "r"
        rook_moved_flag = "white_rook_h" if turn == "white" else "black_rook_h"
        between_cols = [5, 6]
        pass_cols = [5, 6]
    else:  # queenside
        rook_square = "a1" if turn == "white" else "a8"
        rook_piece = "R" if turn == "white" else "r"
        rook_moved_flag = "white_rook_a" if turn == "white" else "black_rook_a"
        between_cols = [1, 2, 3]
        pass_cols = [3, 2]

    if board.moved[rook_moved_flag]:
        return False, "Castling: rook already moved"
    if board.get_piece(rook_square) != rook_piece:
        return False, "Castling: rook is missing"

    for col in between_cols:
        if board.grid[from_row][col] != ".":
            return False, "Castling: squares between are not empty"

    for col in pass_cols:
        if square_is_attacked(board, from_row, col, opponent):
            return False, "Castling: king would pass through/into check"

    return True, "ok"


def legal_piece_move_only(board, from_square, to_square, turn, en_passant_target):
    moving_piece = board.get_piece(from_square)
    target_piece = board.get_piece(to_square)

    if moving_piece == ".":
        return False, "No piece on the from-square"

    if turn == "white" and not is_white_piece(moving_piece):
        return False, "It's white's turn"
    if turn == "black" and not is_black_piece(moving_piece):
        return False, "It's black's turn"

    if turn == "white" and is_white_piece(target_piece):
        return False, "Can't capture your own piece"
    if turn == "black" and is_black_piece(target_piece):
        return False, "Can't capture your own piece"

    from_row, from_col = board.square_to_index(from_square)
    to_row, to_col = board.square_to_index(to_square)

    delta_row = to_row - from_row
    delta_col = to_col - from_col
    abs_row = abs(delta_row)
    abs_col = abs(delta_col)

    piece_type = moving_piece.lower()

    # Pawn
    if piece_type == "p":
        direction = -1 if turn == "white" else 1
        start_row = 6 if turn == "white" else 1

        if delta_col == 0 and target_piece == ".":
            if delta_row == direction:
                return True, "ok"
            if from_row == start_row and delta_row == 2 * direction:
                intermediate_row = from_row + direction
                if board.grid[intermediate_row][from_col] == ".":
                    return True, "ok"
                return False, "Pawn is blocked"
            return False, "Illegal pawn move"

        if abs_row == 1 and abs_col == 1 and delta_row == direction:
            # normal capture
            if target_piece != ".":
                return True, "ok"

            # en passant capture (diagonal into empty square)
            if en_passant_target is not None and to_square == en_passant_target:
                return True, "ok"

            return False, "Pawn capture requires an opponent piece"

        return False, "Illegal pawn move"

    # Knight
    if piece_type == "n":
        if (abs_row, abs_col) in [(1, 2), (2, 1)]:
            return True, "ok"
        return False, "Illegal knight move"

    # Bishop
    if piece_type == "b":
        if abs_row == abs_col and abs_row != 0 and path_is_clear(board, from_row, from_col, to_row, to_col):
            return True, "ok"
        return False, "Illegal bishop move or path blocked"

    # Rook
    if piece_type == "r":
        straight = (delta_row == 0 and delta_col != 0) or (delta_col == 0 and delta_row != 0)
        if straight and path_is_clear(board, from_row, from_col, to_row, to_col):
            return True, "ok"
        return False, "Illegal rook move or path blocked"

    # Queen
    if piece_type == "q":
        diagonal = (abs_row == abs_col and abs_row != 0)
        straight = (delta_row == 0 and delta_col != 0) or (delta_col == 0 and delta_row != 0)
        if (diagonal or straight) and path_is_clear(board, from_row, from_col, to_row, to_col):
            return True, "ok"
        return False, "Illegal queen move or path blocked"

    # King (+ castling)
    if piece_type == "k":
        if delta_row == 0 and abs(delta_col) == 2:
            return can_castle(board, from_square, to_square, turn)

        if max(abs_row, abs_col) == 1 and (abs_row + abs_col) > 0:
            return True, "ok"
        return False, "Illegal king move"

    return False, "Unknown piece"

def is_pawn_promotion_square(board, square, piece_char):
    row, col = board.square_to_index(square)
    return (piece_char == "P" and row == 0) or (piece_char == "p" and row == 7)


class Game:
    def __init__(self):
        self.board = Board()
        self.board.setup_start_position()
        self.turn = "white"
        self.last_message = ""
        self.game_over = False
        self.result = None  # "checkmate" | "stalemate" | None
        self.promotion_pending = None  # e.g. "e8" or "a1"
        self.en_passant_target = None  # e.g. "e3" or "d6" (square that can be captured into)
        self.move_list = []  # list of strings
        self.pending_promo_text = None  # if a pawn reached last rank, store base move text until user chooses piece
        self.last_move_text = ""  # last executed move text (e.g. e2→e4, O-O)

    def reset(self):
        self.board.reset()
        self.turn = "white"
        self.last_message = "New game."
        self.game_over = False
        self.result = None
        self.promotion_pending = None
        self.en_passant_target = None
        self.move_list = []
        self.pending_promo_text = None
        self.last_move_text = ""

    def in_check_now(self, color):
        return king_in_check(self.board, color)

    def is_legal_move(self, from_square, to_square):
        ok, reason = legal_piece_move_only(self.board, from_square, to_square, self.turn, self.en_passant_target)

        if not ok:
            return False, reason

        undo = self.board.make_move(from_square, to_square, self.en_passant_target, self.turn)
        illegal = king_in_check(self.board, self.turn)
        self.board.undo_move(undo)

        if illegal:
            return False, "Illegal: you can't leave your king in check."
        return True, "ok"

    def legal_destinations_from(self, from_square):
        destinations = []
        for row in range(8):
            for col in range(8):
                to_square = self.board.index_to_square(row, col)
                ok, _ = self.is_legal_move(from_square, to_square)
                if ok:
                    destinations.append(to_square)
        return destinations

    def has_any_legal_move(self, color):
        # temporarily set turn to generate moves for that color, then restore
        saved_turn = self.turn
        self.turn = color
        try:
            for row in range(8):
                for col in range(8):
                    piece = self.board.grid[row][col]
                    if piece == ".":
                        continue
                    if color == "white" and not is_white_piece(piece):
                        continue
                    if color == "black" and not is_black_piece(piece):
                        continue

                    from_sq = self.board.index_to_square(row, col)
                    if self.legal_destinations_from(from_sq):
                        return True
            return False
        finally:
            self.turn = saved_turn

    def update_end_state_for_side_to_move(self):
        # side to move = self.turn
        in_check = self.in_check_now(self.turn)
        has_move = self.has_any_legal_move(self.turn)

        if not has_move:
            self.game_over = True
            if in_check:
                self.result = "checkmate"
                self.last_message = f"Checkmate! {'Black' if self.turn == 'white' else 'White'} wins."
            else:
                self.result = "stalemate"
                self.last_message = "Stalemate! Draw."
            return

        # not game over
        base = self.last_move_text or ""  # safety
        if in_check:
            self.last_message = base + " (Check!)" if base else "Check!"
        else:
            self.last_message = base if base else ""

    def promote(self, piece_letter):
        # piece_letter should be one of: "q","r","b","n" (case-insensitive)
        if self.promotion_pending is None:
            self.last_message = "No promotion pending."
            return False

        piece_letter = piece_letter.lower()
        if piece_letter not in ("q", "r", "b", "n"):
            self.last_message = "Invalid promotion piece."
            return False

        square = self.promotion_pending
        pawn = self.board.get_piece(square)
        if pawn not in ("P", "p"):
            self.last_message = "Promotion error (no pawn)."
            self.promotion_pending = None
            return False

        promoted = piece_letter.upper() if pawn == "P" else piece_letter
        self.board._set_raw(square, promoted)  # or a public setter if you prefer

        self.promotion_pending = None

        final_text = (self.pending_promo_text or "") + piece_letter.upper()
        self.move_list.append(final_text)
        self.last_move_text = final_text
        self.pending_promo_text = None

        # now switch turn and evaluate check/mate/stalemate
        self.turn = "black" if self.turn == "white" else "white"
        self.update_end_state_for_side_to_move()
        return True

    def _format_move_text(self, from_square, to_square, moving_piece, captured_piece, was_en_passant):
        # Castling
        from_row, from_col = self.board.square_to_index(from_square)
        to_row, to_col = self.board.square_to_index(to_square)
        if moving_piece.lower() == "k" and from_row == to_row and abs(to_col - from_col) == 2:
            return "O-O" if to_col > from_col else "O-O-O"

        # Capture?
        is_capture = (captured_piece != ".") or was_en_passant
        arrow = "×" if is_capture else "→"
        return f"{from_square}{arrow}{to_square}"

    def try_move(self, from_square, to_square):
        if self.game_over:
            self.last_message = "Game over. Press New Game."
            return False

        if self.promotion_pending is not None:
            self.last_message = "Promotion required."
            return False

        ok, reason = self.is_legal_move(from_square, to_square)
        if not ok:
            self.last_message = reason
            return False

        moving_piece = self.board.get_piece(from_square)
        captured_piece = self.board.get_piece(to_square)  # normal capture is on destination

        # make move
        undo = self.board.make_move(from_square, to_square, self.en_passant_target, self.turn)

        was_en_passant = bool(undo.get("en_passant"))
        move_text = self._format_move_text(from_square, to_square, moving_piece, captured_piece, was_en_passant)
        self.last_move_text = move_text

        moved_piece = self.board.get_piece(to_square)

        # --- NEW: promotion pending? ---
        if moved_piece.lower() == "p" and is_pawn_promotion_square(self.board, to_square, moved_piece):
            self.promotion_pending = to_square
            self.pending_promo_text = move_text + "="  # we'll append Q/R/B/N later
            self.last_message = f"{move_text} (promotion)"
            return True
        # --------------------------------

        # Reset en passant by default (only lasts for one opponent move)
        new_ep_target = None

        moved_piece = self.board.get_piece(to_square)
        from_row, from_col = self.board.square_to_index(from_square)
        to_row, to_col = self.board.square_to_index(to_square)

        # If a pawn just moved two squares, set en passant target to the jumped-over square
        if moved_piece.lower() == "p" and abs(to_row - from_row) == 2:
            jumped_row = (from_row + to_row) // 2
            jumped_square = self.board.index_to_square(jumped_row, to_col)
            new_ep_target = jumped_square

        self.en_passant_target = new_ep_target

        self.move_list.append(move_text)

        # normal flow
        self.turn = "black" if self.turn == "white" else "white"
        self.update_end_state_for_side_to_move()
        return True

