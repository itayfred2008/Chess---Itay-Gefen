import socket
import threading
import json
import traceback

from engine import Game
from database import init_db, login, signup

HOST = "0.0.0.0"
PORT = 5000


def send_json(sock, data, lock=None):
    raw = (json.dumps(data) + "\n").encode("utf-8")
    if lock:
        with lock:
            sock.sendall(raw)
    else:
        sock.sendall(raw)


def recv_json_line(file_obj):
    line = file_obj.readline()
    if not line:
        return None
    return json.loads(line.strip())


class Room:
    def __init__(self, room_id, name, owner_session):
        self.room_id = room_id
        self.name = name
        self.game = Game()
        self.players = {"white": owner_session, "black": None}
        self.lock = threading.Lock()

        self.rematch_votes = set()
        self.draw_offer_from = None

    def player_count(self):
        return sum(1 for p in self.players.values() if p is not None)

    def reset_match_flow_state(self):
        self.rematch_votes.clear()
        self.draw_offer_from = None

    def both_players_connected(self):
        return self.players["white"] is not None and self.players["black"] is not None

    def usernames(self):
        return {
            "white": self.players["white"].username if self.players["white"] else None,
            "black": self.players["black"].username if self.players["black"] else None,
        }

    def snapshot_for(self, session):
        board_rows = ["".join(row) for row in self.game.board.grid]
        users = self.usernames()

        your_color = None
        if self.players["white"] is session:
            your_color = "white"
        elif self.players["black"] is session:
            your_color = "black"

        return {
            "type": "game_state",
            "room_id": self.room_id,
            "room_name": self.name,
            "board": board_rows,
            "moved": self.game.board.moved,
            "turn": self.game.turn,
            "last_message": self.game.last_message,
            "game_over": self.game.game_over,
            "result": self.game.result,
            "promotion_pending": self.game.promotion_pending,
            "en_passant_target": self.game.en_passant_target,
            "move_list": self.game.move_list,
            "white_username": users["white"],
            "black_username": users["black"],
            "your_color": your_color,
            "both_connected": self.both_players_connected(),
            "draw_offer_from": self.draw_offer_from,
            "rematch_votes": list(self.rematch_votes),
        }

    def broadcast_state(self):
        for color in ("white", "black"):
            sess = self.players[color]
            if sess is not None:
                sess.send(self.snapshot_for(sess))


class ClientSession:
    def __init__(self, server, sock, addr):
        self.server = server
        self.sock = sock
        self.addr = addr
        self.file = sock.makefile("r", encoding="utf-8")
        self.send_lock = threading.Lock()

        self.username = None
        self.room = None

    def send(self, data):
        try:
            send_json(self.sock, data, self.send_lock)
        except Exception:
            pass

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


class ChessServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port

        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.global_lock = threading.Lock()
        self.rooms = {}
        self.next_room_id = 1
        self.logged_in_users = set()

    def start(self):
        init_db()

        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen()

        print(f"Server listening on {self.host}:{self.port}")

        while True:
            client_sock, addr = self.server_sock.accept()
            session = ClientSession(self, client_sock, addr)
            threading.Thread(target=self.handle_client, args=(session,), daemon=True).start()

    def handle_client(self, session):
        print(f"Client connected: {session.addr}")
        try:
            session.send({"type": "info", "message": "Connected to server."})

            while True:
                msg = recv_json_line(session.file)
                if msg is None:
                    break

                msg_type = msg.get("type")

                if msg_type == "signup":
                    self.handle_signup(session, msg)

                elif msg_type == "login":
                    self.handle_login(session, msg)

                elif msg_type == "list_rooms":
                    self.handle_list_rooms(session)

                elif msg_type == "create_room":
                    self.handle_create_room(session, msg)

                elif msg_type == "join_room":
                    self.handle_join_room(session, msg)

                elif msg_type == "leave_room":
                    self.handle_leave_room(session)

                elif msg_type == "make_move":
                    self.handle_make_move(session, msg)

                elif msg_type == "promote":
                    self.handle_promote(session, msg)

                elif msg_type == "surrender":
                    self.handle_surrender(session)

                elif msg_type == "new_game":
                    self.handle_new_game(session)

                elif msg_type == "offer_draw":
                    self.handle_offer_draw(session)

                elif msg_type == "respond_draw":
                    self.handle_respond_draw(session, msg)

                elif msg_type == "vote_rematch":
                    self.handle_vote_rematch(session)

                else:
                    session.send({"type": "error", "message": "Unknown request type."})

        except Exception as e:
            print(f"Client error {session.addr}: {e}")
            traceback.print_exc()
        finally:
            self.cleanup_session(session)
            print(f"Client disconnected: {session.addr}")

    def require_auth(self, session):
        if not session.username:
            session.send({"type": "error", "message": "You must log in first."})
            return False
        return True

    def get_player_color(self, room, session):
        if room.players["white"] is session:
            return "white"
        if room.players["black"] is session:
            return "black"
        return None

    def handle_offer_draw(self, session):
        room = session.room
        if room is None:
            session.send({"type": "error", "message": "You are not in a room."})
            return

        with room.lock:
            player_color = self.get_player_color(room, session)
            if player_color is None:
                session.send({"type": "error", "message": "You are not a player in this room."})
                return

            if not room.both_players_connected():
                session.send({"type": "error", "message": "Both players must be present."})
                return

            if room.game.game_over:
                session.send({"type": "error", "message": "Game is already over."})
                return

            if room.game.promotion_pending is not None:
                session.send({"type": "error", "message": "Finish the promotion first."})
                return

            if room.draw_offer_from is not None:
                session.send({"type": "error", "message": "A draw offer is already pending."})
                return

            room.draw_offer_from = player_color
            offerer = "White" if player_color == "white" else "Black"
            room.game.last_message = f"{offerer} offered a draw."

            room.broadcast_state()

    def handle_respond_draw(self, session, msg):
        room = session.room
        if room is None:
            session.send({"type": "error", "message": "You are not in a room."})
            return

        accept = bool(msg.get("accept"))

        with room.lock:
            player_color = self.get_player_color(room, session)
            if player_color is None:
                session.send({"type": "error", "message": "You are not a player in this room."})
                return

            if room.draw_offer_from is None:
                session.send({"type": "error", "message": "There is no draw offer to respond to."})
                return

            if room.draw_offer_from == player_color:
                session.send({"type": "error", "message": "You cannot respond to your own draw offer."})
                return

            offerer = "White" if room.draw_offer_from == "white" else "Black"
            responder = "White" if player_color == "white" else "Black"

            if accept:
                room.game.game_over = True
                room.game.result = "draw_agreed"
                room.game.last_message = f"Draw agreed. {offerer} offered, {responder} accepted."
                room.draw_offer_from = None
                room.rematch_votes.clear()
            else:
                room.draw_offer_from = None
                room.game.last_message = f"{responder} declined the draw offer."

            room.broadcast_state()

    def handle_vote_rematch(self, session):
        room = session.room
        if room is None:
            session.send({"type": "error", "message": "You are not in a room."})
            return

        with room.lock:
            player_color = self.get_player_color(room, session)
            if player_color is None:
                session.send({"type": "error", "message": "You are not a player in this room."})
                return

            if not room.both_players_connected():
                session.send({"type": "error", "message": "Both players must be in the room."})
                return

            if not room.game.game_over:
                session.send(
                    {"type": "error", "message": "You can only vote for a new game after the current game ends."})
                return

            room.rematch_votes.add(player_color)

            if room.rematch_votes == {"white", "black"}:
                room.game.reset()
                room.reset_match_flow_state()
                room.broadcast_state()
                return

            voter = "White" if player_color == "white" else "Black"
            room.game.last_message = f"{voter} voted for a new game. Waiting for the other player."
            room.broadcast_state()

    def handle_surrender(self, session):
        room = session.room
        if room is None:
            session.send({"type": "error", "message": "You are not in a room."})
            return

        with room.lock:
            player_color = None
            if room.players["white"] is session:
                player_color = "white"
            elif room.players["black"] is session:
                player_color = "black"

            if player_color is None:
                session.send({"type": "error", "message": "You are not a player in this room."})
                return

            if not room.both_players_connected():
                session.send({"type": "error", "message": "You cannot surrender before both players join."})
                return

            if room.game.game_over:
                session.send({"type": "error", "message": "Game is already over."})
                return

            winner = "Black" if player_color == "white" else "White"
            loser = "White" if player_color == "white" else "Black"

            room.game.game_over = True
            room.game.result = "surrender"
            room.game.last_message = f"{loser} surrendered. {winner} wins."
            room.game.promotion_pending = None
            room.draw_offer_from = None
            room.rematch_votes.clear()

            room.broadcast_state()

    def handle_signup(self, session, msg):
        username = msg.get("username", "")
        password = msg.get("password", "")

        ok, response = signup(username, password)
        if not ok:
            session.send({
                "type": "auth_error",
                "message": response
            })
            return

        actual_username = username.strip()

        with self.global_lock:
            if actual_username in self.logged_in_users:
                session.send({
                    "type": "auth_error",
                    "message": "This account is already logged in."
                })
                return

            self.logged_in_users.add(actual_username)
            session.username = actual_username

        session.send({
            "type": "auth_ok",
            "username": session.username,
            "message": "Account created successfully."
        })

    def handle_login(self, session, msg):
        username = msg.get("username", "")
        password = msg.get("password", "")

        ok, response = login(username, password)
        if not ok:
            session.send({
                "type": "auth_error",
                "message": response
            })
            return

        actual_username = response

        with self.global_lock:
            if actual_username in self.logged_in_users:
                session.send({
                    "type": "auth_error",
                    "message": "This account is already logged in."
                })
                return

            self.logged_in_users.add(actual_username)
            session.username = actual_username

        session.send({
            "type": "auth_ok",
            "username": session.username,
            "message": "Login successful."
        })

    def handle_list_rooms(self, session):
        if not self.require_auth(session):
            return

        with self.global_lock:
            rooms_data = []
            for room in self.rooms.values():
                users = room.usernames()
                rooms_data.append({
                    "room_id": room.room_id,
                    "name": room.name,
                    "players": room.player_count(),
                    "white_username": users["white"],
                    "black_username": users["black"],
                })

        session.send({
            "type": "room_list",
            "rooms": rooms_data
        })

    def handle_create_room(self, session, msg):
        if not self.require_auth(session):
            return

        if session.room is not None:
            session.send({"type": "error", "message": "Leave your current room first."})
            return

        room_name = msg.get("name", "").strip()
        if not room_name:
            room_name = f"{session.username}'s Room"

        with self.global_lock:
            room_id = self.next_room_id
            self.next_room_id += 1

            room = Room(room_id, room_name, session)
            self.rooms[room_id] = room
            session.room = room

        session.send({
            "type": "room_joined",
            "room_id": room.room_id,
            "room_name": room.name,
            "your_color": "white"
        })
        room.broadcast_state()

    def handle_join_room(self, session, msg):
        if not self.require_auth(session):
            return

        if session.room is not None:
            session.send({"type": "error", "message": "Leave your current room first."})
            return

        room_id = msg.get("room_id")
        if room_id is None:
            session.send({"type": "error", "message": "Missing room id."})
            return

        with self.global_lock:
            room = self.rooms.get(room_id)

        if room is None:
            session.send({"type": "error", "message": "Room does not exist."})
            return

        with room.lock:
            if room.players["white"] is None:
                room.players["white"] = session
                color = "white"
            elif room.players["black"] is None:
                room.players["black"] = session
                color = "black"
            else:
                session.send({"type": "error", "message": "Room is full."})
                return

            session.room = room

        session.send({
            "type": "room_joined",
            "room_id": room.room_id,
            "room_name": room.name,
            "your_color": color
        })
        room.broadcast_state()

    def handle_leave_room(self, session):
        room = session.room
        if room is None:
            return

        with room.lock:
            white_player = room.players["white"]
            black_player = room.players["black"]

            other_session = None
            if white_player is session:
                other_session = black_player
            elif black_player is session:
                other_session = white_player

            # Clear room references for both players
            if white_player is not None:
                white_player.room = None
            if black_player is not None:
                black_player.room = None

            room.players["white"] = None
            room.players["black"] = None
            room.draw_offer_from = None
            room.rematch_votes.clear()

        with self.global_lock:
            if room.room_id in self.rooms:
                del self.rooms[room.room_id]

        # Tell the player who did not leave that the opponent left
        if other_session is not None and other_session is not session:
            other_session.send({
                "type": "opponent_left",
                "message": "The other player left the room."
            })
            other_session.send({"type": "left_room"})

        # Tell the leaving player that they left
        session.send({"type": "left_room"})

    def handle_make_move(self, session, msg):
        room = session.room
        if room is None:
            session.send({"type": "error", "message": "You are not in a room."})
            return

        from_sq = msg.get("from")
        to_sq = msg.get("to")
        if not from_sq or not to_sq:
            session.send({"type": "error", "message": "Missing move squares."})
            return

        with room.lock:
            player_color = None
            if room.players["white"] is session:
                player_color = "white"
            elif room.players["black"] is session:
                player_color = "black"

            if player_color is None:
                session.send({"type": "error", "message": "You are not a player in this room."})
                return

            if not room.both_players_connected():
                session.send({"type": "error", "message": "You must wait for the second player to join."})
                return

            if room.game.game_over:
                session.send({"type": "error", "message": "Game is over."})
                return

            if room.game.promotion_pending is not None:
                session.send({"type": "error", "message": "Promotion required first."})
                return

            if room.game.turn != player_color:
                session.send({"type": "error", "message": "It is not your turn."})
                return

            moved = room.game.try_move(from_sq, to_sq)
            if not moved:
                session.send({"type": "error", "message": room.game.last_message})
                room.broadcast_state()
                return

            room.broadcast_state()

    def handle_promote(self, session, msg):
        room = session.room
        if room is None:
            session.send({"type": "error", "message": "You are not in a room."})
            return

        piece = msg.get("piece", "").lower()

        with room.lock:
            player_color = None
            if room.players["white"] is session:
                player_color = "white"
            elif room.players["black"] is session:
                player_color = "black"

            if player_color is None:
                session.send({"type": "error", "message": "You are not a player in this room."})
                return

            if room.game.promotion_pending is None:
                session.send({"type": "error", "message": "No promotion pending."})
                return

            if room.game.turn != player_color:
                session.send({"type": "error", "message": "It is not your turn."})
                return

            ok = room.game.promote(piece)
            if not ok:
                session.send({"type": "error", "message": room.game.last_message})
                room.broadcast_state()
                return

            room.broadcast_state()

    def cleanup_session(self, session):
        try:
            self.handle_leave_room(session)
        except Exception:
            pass

        with self.global_lock:
            if session.username in self.logged_in_users:
                self.logged_in_users.remove(session.username)

        session.close()


if __name__ == "__main__":
    ChessServer(HOST, PORT).start()