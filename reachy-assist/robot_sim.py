"""Visual Reachy Mini simulator — shows an animated robot face in a window.
The face changes expression based on commands from the interaction loop.

Run standalone:  python robot_sim.py
Or used automatically when robot.py is in simulation mode."""

import math
import queue
import subprocess
import threading
import time

import pygame

# ── Window config ───────────────────────────────────────────────────
WIDTH, HEIGHT = 480, 600
BG_COLOR = (15, 17, 23)
FACE_COLOR = (30, 33, 48)
EYE_WHITE = (220, 225, 240)
PUPIL_COLOR = (60, 130, 246)
MOUTH_COLOR = (220, 225, 240)
ANTENNA_COLOR = (60, 130, 246)
TEXT_COLOR = (180, 180, 190)
ACCENT_COLOR = (60, 130, 246)

# ── Expression definitions ──────────────────────────────────────────
# Each expression defines: eye_scale, pupil_size, mouth_type, antenna_angle, blush
EXPRESSIONS = {
    "neutral": {"eye_h": 1.0, "pupil": 1.0, "mouth": "smile", "antenna": 0, "blush": False},
    "joy": {"eye_h": 0.7, "pupil": 1.2, "mouth": "big_smile", "antenna": 25, "blush": True},
    "sadness": {"eye_h": 0.8, "pupil": 0.8, "mouth": "frown", "antenna": -15, "blush": False},
    "anger": {"eye_h": 0.6, "pupil": 0.9, "mouth": "flat", "antenna": -25, "blush": False},
    "fear": {"eye_h": 1.3, "pupil": 1.4, "mouth": "open", "antenna": 10, "blush": False},
    "surprise": {"eye_h": 1.4, "pupil": 1.3, "mouth": "open_wide", "antenna": 30, "blush": False},
    "disgust": {"eye_h": 0.7, "pupil": 0.7, "mouth": "squiggle", "antenna": -10, "blush": False},
}

# ── Shared state (thread-safe) ──────────────────────────────────────
_command_queue = queue.Queue()
_current_expression = "neutral"
_current_action = ""
_last_speech = ""
_running = False
_sim_thread = None


def send_expression(emotion):
    _command_queue.put(("express", emotion))

def send_action(action):
    _command_queue.put(("action", action))

def send_speech(text):
    _command_queue.put(("speech", text))


def _draw_face(screen, expr_data, t, action_text, speech_text):
    """Draw the robot face with current expression."""
    cx, cy = WIDTH // 2, 240  # face center

    # Face circle
    pygame.draw.circle(screen, FACE_COLOR, (cx, cy), 140)
    pygame.draw.circle(screen, (50, 55, 70), (cx, cy), 140, 2)

    # Antennas
    antenna_angle = expr_data["antenna"]
    # Add gentle idle sway
    sway = math.sin(t * 1.5) * 3
    for side in [-1, 1]:
        base_x = cx + side * 50
        base_y = cy - 130
        angle_rad = math.radians(antenna_angle * side + sway * side)
        tip_x = base_x + math.sin(angle_rad) * 50
        tip_y = base_y - math.cos(angle_rad) * 50
        pygame.draw.line(screen, ANTENNA_COLOR, (base_x, base_y), (int(tip_x), int(tip_y)), 4)
        pygame.draw.circle(screen, ANTENNA_COLOR, (int(tip_x), int(tip_y)), 7)

    # Eyes
    eye_h_scale = expr_data["eye_h"]
    pupil_scale = expr_data["pupil"]
    # Gentle blink every ~4 seconds
    blink = 1.0
    blink_cycle = t % 4.0
    if 3.8 < blink_cycle < 4.0:
        blink = max(0.05, 1.0 - (blink_cycle - 3.8) * 10)
    elif 0.0 < blink_cycle < 0.1:
        blink = min(1.0, blink_cycle * 10)

    for side in [-1, 1]:
        ex = cx + side * 55
        ey = cy - 15
        eye_w, eye_h = 32, int(38 * eye_h_scale * blink)
        if eye_h < 3:
            eye_h = 3
        # White of eye
        pygame.draw.ellipse(screen, EYE_WHITE, (ex - eye_w, ey - eye_h, eye_w * 2, eye_h * 2))
        # Pupil (follows a gentle pattern)
        px_off = math.sin(t * 0.7 + side) * 5
        py_off = math.cos(t * 0.5) * 3
        pr = int(12 * pupil_scale)
        pygame.draw.circle(screen, PUPIL_COLOR, (int(ex + px_off), int(ey + py_off)), pr)
        # Pupil highlight
        pygame.draw.circle(screen, (200, 220, 255), (int(ex + px_off - 3), int(ey + py_off - 3)), 4)

    # Blush
    if expr_data["blush"]:
        for side in [-1, 1]:
            bx = cx + side * 80
            by = cy + 25
            s = pygame.Surface((40, 20), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (255, 100, 100, 60), (0, 0, 40, 20))
            screen.blit(s, (bx - 20, by - 10))

    # Mouth
    mouth = expr_data["mouth"]
    my = cy + 50
    if mouth == "smile":
        pygame.draw.arc(screen, MOUTH_COLOR, (cx - 30, my - 15, 60, 30), math.pi + 0.3, 2 * math.pi - 0.3, 3)
    elif mouth == "big_smile":
        pygame.draw.arc(screen, MOUTH_COLOR, (cx - 40, my - 20, 80, 40), math.pi + 0.2, 2 * math.pi - 0.2, 3)
        # Teeth hint
        pygame.draw.line(screen, FACE_COLOR, (cx - 25, my + 2), (cx + 25, my + 2), 2)
    elif mouth == "frown":
        pygame.draw.arc(screen, MOUTH_COLOR, (cx - 25, my, 50, 25), 0.3, math.pi - 0.3, 3)
    elif mouth == "flat":
        pygame.draw.line(screen, MOUTH_COLOR, (cx - 25, my), (cx + 25, my), 3)
    elif mouth == "open":
        pygame.draw.ellipse(screen, MOUTH_COLOR, (cx - 15, my - 10, 30, 25), 2)
    elif mouth == "open_wide":
        pygame.draw.ellipse(screen, MOUTH_COLOR, (cx - 22, my - 15, 44, 35), 2)
    elif mouth == "squiggle":
        points = [(cx - 25, my), (cx - 10, my - 8), (cx + 10, my + 8), (cx + 25, my)]
        pygame.draw.lines(screen, MOUTH_COLOR, False, points, 3)

    # Action text
    font_sm = pygame.font.SysFont("Helvetica", 16)
    if action_text:
        action_surf = font_sm.render(f"♦ {action_text}", True, ACCENT_COLOR)
        screen.blit(action_surf, (cx - action_surf.get_width() // 2, cy + 160))

    # Speech bubble
    if speech_text:
        font_speech = pygame.font.SysFont("Helvetica", 15)
        # Word wrap
        words = speech_text.split()
        lines = []
        current = ""
        for w in words:
            test = current + " " + w if current else w
            if font_speech.size(test)[0] < WIDTH - 60:
                current = test
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)
        lines = lines[:4]  # max 4 lines

        bubble_h = len(lines) * 22 + 16
        bubble_y = HEIGHT - bubble_h - 20
        # Bubble background
        pygame.draw.rect(screen, (35, 38, 55), (20, bubble_y, WIDTH - 40, bubble_h), border_radius=12)
        pygame.draw.rect(screen, (60, 65, 85), (20, bubble_y, WIDTH - 40, bubble_h), 1, border_radius=12)
        # Text
        for i, line in enumerate(lines):
            line_surf = font_speech.render(line, True, (220, 220, 230))
            screen.blit(line_surf, (32, bubble_y + 8 + i * 22))


def _sim_loop():
    """Main pygame loop for the simulator window."""
    global _current_expression, _current_action, _last_speech, _running

    # On macOS, pygame/SDL display MUST run on the main thread.
    # When started from a background thread, skip the visual window entirely.
    import os
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    try:
        pygame.init()
        # dummy driver won't give us a real window, so just run headless
        print("[SIM] Running headless -- no simulator window (camera still works)")
        _running = True
        while _running:
            while not _command_queue.empty():
                try:
                    cmd, val = _command_queue.get_nowait()
                    if cmd == "express":
                        _current_expression = val if val in EXPRESSIONS else "neutral"
                    elif cmd == "action":
                        _current_action = val
                    elif cmd == "speech":
                        _last_speech = val
                except queue.Empty:
                    break
            time.sleep(0.1)
        return
    except Exception as e:
        print(f"[SIM] Could not start simulator: {e}")
        _running = True
        while _running:
            while not _command_queue.empty():
                try:
                    _command_queue.get_nowait()
                except queue.Empty:
                    break
            time.sleep(0.1)
        return

    font_title = pygame.font.SysFont("Helvetica", 14)
    action_clear_time = 0
    speech_clear_time = 0

    _running = True
    start_time = time.time()

    while _running:
        t = time.time() - start_time

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                _running = False
                break

        # Process commands
        while not _command_queue.empty():
            try:
                cmd, val = _command_queue.get_nowait()
                if cmd == "express":
                    _current_expression = val if val in EXPRESSIONS else "neutral"
                elif cmd == "action":
                    _current_action = val
                    action_clear_time = time.time() + 3
                elif cmd == "speech":
                    _last_speech = val
                    speech_clear_time = time.time() + max(4, len(val) * 0.06)
            except queue.Empty:
                break

        # Clear stale text
        if time.time() > action_clear_time:
            _current_action = ""
        if time.time() > speech_clear_time:
            _last_speech = ""

        # Draw
        screen.fill(BG_COLOR)

        # Title bar
        title_surf = font_title.render(
            f"REACHY MINI  •  {_current_expression.upper()}", True, TEXT_COLOR
        )
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 12))

        expr_data = EXPRESSIONS.get(_current_expression, EXPRESSIONS["neutral"])
        _draw_face(screen, expr_data, t, _current_action, _last_speech)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


def start_sim():
    """Start the simulator in a background thread."""
    global _sim_thread
    _sim_thread = threading.Thread(target=_sim_loop, daemon=True)
    _sim_thread.start()
    time.sleep(0.5)  # let pygame init
    print("[SIM] Visual simulator started")


def stop_sim():
    global _running
    _running = False


# ── Standalone mode ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("Reachy Mini Visual Simulator")
    print("Testing expressions... close window to quit.\n")

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Reachy Mini Simulator — Demo")
    clock = pygame.time.Clock()
    font_title = pygame.font.SysFont("Helvetica", 14)

    expressions_list = list(EXPRESSIONS.keys())
    expr_idx = 0
    last_switch = time.time()
    start_time = time.time()

    # Speak the first one
    subprocess.Popen(["say", "-v", "Samantha", "-r", "160",
                       f"Hello! I'm Reachy. Let me show you my expressions."])

    running = True
    while running:
        t = time.time() - start_time

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    expr_idx = (expr_idx + 1) % len(expressions_list)
                    last_switch = time.time()
                if event.key == pygame.K_q:
                    running = False

        # Auto-cycle every 3 seconds
        if time.time() - last_switch > 3:
            expr_idx = (expr_idx + 1) % len(expressions_list)
            last_switch = time.time()
            expr_name = expressions_list[expr_idx]
            messages = {
                "neutral": "This is my neutral face. Calm and ready.",
                "joy": "I'm happy! See my big smile?",
                "sadness": "I'm feeling a bit sad right now.",
                "anger": "Grr, I'm a little frustrated.",
                "fear": "Oh no, something scared me!",
                "surprise": "Wow! I didn't expect that!",
                "disgust": "Hmm, I'm not sure about that.",
            }
            msg = messages.get(expr_name, "")
            if msg:
                subprocess.Popen(["say", "-v", "Samantha", "-r", "160", msg])

        screen.fill(BG_COLOR)
        current_expr = expressions_list[expr_idx]
        title_surf = font_title.render(
            f"REACHY MINI  •  {current_expr.upper()}  •  Space=next  Q=quit",
            True, TEXT_COLOR
        )
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 12))

        expr_data = EXPRESSIONS.get(current_expr, EXPRESSIONS["neutral"])
        msg = {
            "neutral": "I'm calm and ready to help.",
            "joy": "This makes me so happy!",
            "sadness": "I'm here if you need me.",
            "anger": "Let me take a deep breath.",
            "fear": "That startled me!",
            "surprise": "Oh wow!",
            "disgust": "Hmm, not sure about that.",
        }.get(current_expr, "")
        _draw_face(screen, expr_data, t, f"Expression: {current_expr}", msg)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
