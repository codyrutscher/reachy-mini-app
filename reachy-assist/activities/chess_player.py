"""Chess Player — Reachy recognizes a chessboard via camera and plays chess.

Uses GPT-4o vision to read the board state, then GPT to pick a move.
Reachy comments on openings, tactics, and verbally states its next move.
"""

import logging
import os

logger = logging.getLogger(__name__)


class ChessPlayer:
    """Camera-based chess player using GPT-4o vision."""

    def __init__(self):
        self._game_active = False
        self._move_history = []
        self._player_color = "white"
        self._board_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    def start_game(self, player_color: str = "white") -> str:
        self._game_active = True
        self._move_history = []
        self._player_color = player_color.lower()
        self._board_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        logger.info("Chess game started, player is %s", player_color)
        return (
            f"Let's play chess! You're {player_color}. "
            f"Set up the board and make your first move, then say 'your turn' "
            f"and I'll look at the board through my camera."
        )

    def stop_game(self) -> str:
        if not self._game_active:
            return "No chess game in progress."
        self._game_active = False
        moves = len(self._move_history)
        return f"Good game! We played {moves} moves."

    def analyze_board(self) -> str:
        """Capture the board via camera and analyze it with GPT-4o vision."""
        if not self._game_active:
            return "Start a game first! Say 'let's play chess'."

        try:
            from perception.vision import capture_frame
            frame_b64 = capture_frame()
            if not frame_b64:
                return "I can't see the board right now. Make sure it's in front of my camera."
        except Exception:
            return "Camera not available. Describe your move instead!"

        # Ask GPT-4o to read the board and suggest a move
        try:
            import json
            import urllib.request

            api_key = os.environ.get("OPENAI_API_KEY", "")
            history_str = ", ".join(self._move_history[-10:]) if self._move_history else "none yet"

            body = json.dumps({
                "model": "gpt-4o",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": (
                            f"You are a chess-playing robot. Look at this chessboard photo. "
                            f"Previous moves: {history_str}. "
                            f"I am playing {self._player_color}. "
                            f"1) Describe the current board position briefly. "
                            f"2) Identify what move the opponent just made. "
                            f"3) Suggest your best move in algebraic notation (e.g. e4, Nf3, Bxc6). "
                            f"4) Add a fun comment about the position (mention openings if applicable). "
                            f"Format: MOVE: [your move]\\nCOMMENT: [your comment]"
                        )},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_b64}",
                            "detail": "high",
                        }},
                    ],
                }],
                "max_tokens": 400,
            }).encode()

            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp = urllib.request.urlopen(req, timeout=20)
            result = json.loads(resp.read().decode())
            text = result["choices"][0]["message"]["content"].strip()

            # Extract move
            move = ""
            for line in text.split("\n"):
                if line.upper().startswith("MOVE:"):
                    move = line.split(":", 1)[1].strip()
                    break
            if move:
                self._move_history.append(move)

            logger.info("Chess move: %s", move)
            return text

        except Exception as e:
            logger.error("Chess analysis failed: %s", e)
            return f"I had trouble analyzing the board: {e}"

    def describe_move(self, move_text: str) -> str:
        """Player describes their move verbally instead of using camera."""
        if not self._game_active:
            return "Start a game first!"
        self._move_history.append(f"player:{move_text}")

        try:
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            history_str = ", ".join(self._move_history[-10:])
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": (
                        "You are a friendly chess-playing robot. The player described their move. "
                        "Respond with your counter-move and a fun comment. "
                        "Format: MOVE: [your move]\\nCOMMENT: [comment]"
                    ),
                }, {
                    "role": "user",
                    "content": f"Move history: {history_str}\nPlayer's move: {move_text}",
                }],
                max_tokens=200,
            )
            text = resp.choices[0].message.content.strip()
            for line in text.split("\n"):
                if line.upper().startswith("MOVE:"):
                    self._move_history.append(line.split(":", 1)[1].strip())
                    break
            return text
        except Exception as e:
            return f"Hmm, let me think... I had trouble: {e}"

    @property
    def is_active(self) -> bool:
        return self._game_active

    def get_status(self) -> dict:
        return {
            "active": self._game_active,
            "moves": len(self._move_history),
            "player_color": self._player_color,
            "history": self._move_history[-10:],
        }
