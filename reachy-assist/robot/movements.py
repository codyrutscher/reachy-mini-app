"""Full movement pattern library for Reachy Mini.

Uses head (pitch/roll/yaw + xyz), two antennas, body yaw,
and multiple interpolation styles to create expressive animations."""

import math
import time
from typing import Optional
import numpy as np
from reachy_mini.utils import create_head_pose
from reachy_mini.utils.interpolation import InterpolationTechnique


class Movements:
    """Collection of expressive movement patterns for Reachy Mini."""

    def __init__(self, mini: object) -> None:
        self.mini = mini

    # ── Helpers ──────────────────────────────────────────────────────

    def _go(self, head: Optional[object] = None, antennas: Optional[list[float]] = None,
            duration: float = 0.5, method: object = InterpolationTechnique.MIN_JERK,
            body_yaw: Optional[float] = None) -> None:
        kwargs = {"duration": duration, "method": method}
        if head is not None:
            kwargs["head"] = head
        if antennas is not None:
            kwargs["antennas"] = antennas
        if body_yaw is not None:
            kwargs["body_yaw"] = body_yaw
        self.mini.goto_target(**kwargs)

    def _home(self, duration: float = 0.4) -> None:
        self._go(
            head=create_head_pose(),
            antennas=[0, 0],
            duration=duration,
            body_yaw=0.0,
        )

    # ── Basic gestures ──────────────────────────────────────────────

    def nod_yes(self) -> None:
        """Nod head up and down — 'yes'."""
        for _ in range(2):
            self._go(head=create_head_pose(pitch=-12, degrees=True), duration=0.25)
            self._go(head=create_head_pose(pitch=8, degrees=True), duration=0.25)
        self._home(0.3)

    def shake_no(self) -> None:
        """Shake head side to side — 'no'."""
        for _ in range(2):
            self._go(head=create_head_pose(yaw=-15, degrees=True), duration=0.25)
            self._go(head=create_head_pose(yaw=15, degrees=True), duration=0.25)
        self._home(0.3)

    def greeting(self) -> None:
        """Friendly greeting — head tilt + antenna wave."""
        self._go(
            head=create_head_pose(roll=10, pitch=-5, degrees=True),
            antennas=[-0.8, -0.8],
            duration=0.5,
            method=InterpolationTechnique.CARTOON,
        )
        time.sleep(0.3)
        # Antenna wave
        for _ in range(2):
            self._go(antennas=[-0.8, -0.2], duration=0.2)
            self._go(antennas=[-0.2, -0.8], duration=0.2)
        self._go(
            head=create_head_pose(roll=-5, degrees=True),
            antennas=[-0.6, -0.6],
            duration=0.3,
        )
        self._home(0.4)

    def goodbye(self) -> None:
        """Sad goodbye — slow droop then wave."""
        self._go(
            head=create_head_pose(pitch=8, roll=-8, degrees=True),
            antennas=[0.3, 0.3],
            duration=0.6,
        )
        time.sleep(0.4)
        # Little wave
        self._go(antennas=[-0.5, 0.3], duration=0.3)
        self._go(antennas=[0.3, -0.5], duration=0.3)
        self._home(0.5)

    # ── Emotional expressions ───────────────────────────────────────

    def happy_wiggle(self) -> None:
        """Excited happy wiggle — fast antenna bouncing + head bob."""
        for _ in range(3):
            self._go(
                head=create_head_pose(roll=8, pitch=-5, degrees=True),
                antennas=[-0.7, -0.3],
                duration=0.15,
                method=InterpolationTechnique.CARTOON,
            )
            self._go(
                head=create_head_pose(roll=-8, pitch=-5, degrees=True),
                antennas=[-0.3, -0.7],
                duration=0.15,
                method=InterpolationTechnique.CARTOON,
            )
        self._home(0.3)

    def celebrate(self) -> None:
        """Big celebration — antennas go wild + head bounces."""
        for _ in range(4):
            self._go(
                head=create_head_pose(pitch=-10, degrees=True),
                antennas=[-1.0, -1.0],
                duration=0.15,
                method=InterpolationTechnique.CARTOON,
            )
            self._go(
                head=create_head_pose(pitch=5, degrees=True),
                antennas=[0.2, 0.2],
                duration=0.15,
                method=InterpolationTechnique.CARTOON,
            )
        self._home(0.3)

    def sad_droop(self) -> None:
        """Sad expression — slow droop of head and antennas."""
        self._go(
            head=create_head_pose(pitch=12, roll=-8, degrees=True),
            antennas=[0.5, 0.5],
            duration=1.0,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(1.0)
        self._home(0.8)

    def empathy_lean(self) -> None:
        """Lean forward with gentle head tilt — showing empathy."""
        self._go(
            head=create_head_pose(pitch=-8, roll=6, z=-5, degrees=True, mm=True),
            antennas=[-0.2, -0.2],
            duration=0.7,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(1.5)
        self._home(0.6)

    def scared_startle(self) -> None:
        """Quick startle — pull back then freeze."""
        self._go(
            head=create_head_pose(pitch=15, z=8, degrees=True, mm=True),
            antennas=[0.8, 0.8],
            duration=0.2,
            method=InterpolationTechnique.LINEAR,
        )
        time.sleep(0.5)
        # Slowly recover
        self._go(
            head=create_head_pose(pitch=5, degrees=True),
            antennas=[0.3, 0.3],
            duration=0.5,
        )
        self._home(0.5)

    def surprised(self) -> None:
        """Surprise — quick antenna raise + head back."""
        self._go(
            head=create_head_pose(pitch=8, degrees=True),
            antennas=[-1.0, -1.0],
            duration=0.2,
            method=InterpolationTechnique.CARTOON,
        )
        time.sleep(0.6)
        self._home(0.4)

    def angry_huff(self) -> None:
        """Frustrated/angry — antennas flatten, head shakes slightly."""
        self._go(
            head=create_head_pose(pitch=-5, degrees=True),
            antennas=[1.0, 1.0],
            duration=0.3,
        )
        for _ in range(2):
            self._go(head=create_head_pose(yaw=-5, pitch=-5, degrees=True), duration=0.15)
            self._go(head=create_head_pose(yaw=5, pitch=-5, degrees=True), duration=0.15)
        time.sleep(0.3)
        self._home(0.5)

    def confused_tilt(self) -> None:
        """Confused — head tilts, one antenna up one down."""
        self._go(
            head=create_head_pose(roll=15, degrees=True),
            antennas=[-0.6, 0.4],
            duration=0.5,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(0.8)
        self._go(
            head=create_head_pose(roll=-10, degrees=True),
            antennas=[0.4, -0.6],
            duration=0.5,
        )
        time.sleep(0.5)
        self._home(0.4)

    # ── Activity movements ──────────────────────────────────────────

    def thinking(self) -> None:
        """Thinking pose — slow head tilt + antenna droop."""
        self._go(
            head=create_head_pose(roll=12, pitch=-3, degrees=True),
            antennas=[0.1, -0.3],
            duration=0.6,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(1.2)
        self._home(0.5)

    def listening(self) -> None:
        """Attentive listening — lean forward, antennas perked."""
        self._go(
            head=create_head_pose(pitch=-10, degrees=True),
            antennas=[-0.4, -0.4],
            duration=0.5,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(2.0)
        self._home(0.4)

    def curious_look(self) -> None:
        """Curious — head tilts side to side like a puppy."""
        self._go(
            head=create_head_pose(roll=18, pitch=-5, degrees=True),
            antennas=[-0.5, 0.1],
            duration=0.4,
        )
        time.sleep(0.4)
        self._go(
            head=create_head_pose(roll=-18, pitch=-5, degrees=True),
            antennas=[0.1, -0.5],
            duration=0.4,
        )
        time.sleep(0.4)
        self._home(0.3)

    def look_around(self) -> None:
        """Look around the room — scanning left, right, up."""
        self._go(
            head=create_head_pose(yaw=25, degrees=True),
            duration=0.6,
            body_yaw=math.radians(15),
        )
        time.sleep(0.3)
        self._go(
            head=create_head_pose(yaw=-25, degrees=True),
            duration=0.8,
            body_yaw=math.radians(-15),
        )
        time.sleep(0.3)
        self._go(
            head=create_head_pose(pitch=-15, degrees=True),
            duration=0.5,
            body_yaw=0.0,
        )
        time.sleep(0.3)
        self._home(0.5)

    # ── Fun / entertainment ─────────────────────────────────────────

    def dance(self) -> None:
        """Rhythmic dance — head bobs, antennas bounce, body sways."""
        for _ in range(4):
            self._go(
                head=create_head_pose(roll=10, pitch=-8, degrees=True),
                antennas=[-0.7, -0.2],
                duration=0.25,
                method=InterpolationTechnique.CARTOON,
                body_yaw=math.radians(10),
            )
            self._go(
                head=create_head_pose(roll=-10, pitch=-8, degrees=True),
                antennas=[-0.2, -0.7],
                duration=0.25,
                method=InterpolationTechnique.CARTOON,
                body_yaw=math.radians(-10),
            )
        # Finish with a flourish
        self._go(
            head=create_head_pose(pitch=-12, degrees=True),
            antennas=[-1.0, -1.0],
            duration=0.3,
            method=InterpolationTechnique.CARTOON,
        )
        time.sleep(0.3)
        self._home(0.4)

    def silly_wiggle(self) -> None:
        """Silly/playful wiggle — fast alternating everything."""
        for _ in range(3):
            self._go(
                head=create_head_pose(roll=12, yaw=8, degrees=True),
                antennas=[-0.8, 0.4],
                duration=0.15,
                body_yaw=math.radians(8),
            )
            self._go(
                head=create_head_pose(roll=-12, yaw=-8, degrees=True),
                antennas=[0.4, -0.8],
                duration=0.15,
                body_yaw=math.radians(-8),
            )
        self._home(0.3)

    def bow(self) -> None:
        """Polite bow — head dips forward slowly."""
        self._go(
            head=create_head_pose(pitch=-20, degrees=True),
            antennas=[-0.3, -0.3],
            duration=0.6,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(0.8)
        self._home(0.6)

    # ── Wellness / therapeutic ──────────────────────────────────────

    def breathing_guide(self, cycles: int = 3) -> None:
        """Guide a breathing exercise with slow rhythmic movement.
        Antennas rise on inhale, lower on exhale. Head follows."""
        for i in range(cycles):
            # Inhale (4 seconds)
            self._go(
                head=create_head_pose(pitch=-8, degrees=True),
                antennas=[-0.7, -0.7],
                duration=4.0,
                method=InterpolationTechnique.EASE_IN_OUT,
            )
            # Hold (3 seconds)
            time.sleep(3.0)
            # Exhale (5 seconds)
            self._go(
                head=create_head_pose(pitch=5, degrees=True),
                antennas=[0.2, 0.2],
                duration=5.0,
                method=InterpolationTechnique.EASE_IN_OUT,
            )
            # Pause between cycles
            if i < cycles - 1:
                time.sleep(1.0)
        self._home(0.8)

    def gentle_rock(self) -> None:
        """Gentle rocking motion — soothing/calming."""
        for _ in range(4):
            self._go(
                head=create_head_pose(roll=8, degrees=True),
                antennas=[-0.2, -0.1],
                duration=1.0,
                method=InterpolationTechnique.EASE_IN_OUT,
            )
            self._go(
                head=create_head_pose(roll=-8, degrees=True),
                antennas=[-0.1, -0.2],
                duration=1.0,
                method=InterpolationTechnique.EASE_IN_OUT,
            )
        self._home(0.6)

    def stretch(self) -> None:
        """Stretch routine — Reachy stretches to encourage user to move."""
        # Look up and extend
        self._go(
            head=create_head_pose(pitch=-20, degrees=True),
            antennas=[-1.0, -1.0],
            duration=1.0,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(1.0)
        # Tilt left
        self._go(
            head=create_head_pose(roll=20, pitch=-10, degrees=True),
            antennas=[-0.5, 0.2],
            duration=1.0,
        )
        time.sleep(1.0)
        # Tilt right
        self._go(
            head=create_head_pose(roll=-20, pitch=-10, degrees=True),
            antennas=[0.2, -0.5],
            duration=1.0,
        )
        time.sleep(1.0)
        # Roll neck
        self._go(
            head=create_head_pose(pitch=10, degrees=True),
            antennas=[0.1, 0.1],
            duration=0.8,
        )
        time.sleep(0.5)
        self._home(0.6)

    def sleepy(self) -> None:
        """Drowsy/sleepy — slow droop, antennas sag."""
        self._go(
            head=create_head_pose(pitch=15, roll=5, degrees=True),
            antennas=[0.6, 0.6],
            duration=1.5,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(1.0)
        # Little head bob like nodding off
        self._go(
            head=create_head_pose(pitch=20, roll=5, degrees=True),
            antennas=[0.7, 0.7],
            duration=0.5,
        )
        time.sleep(0.3)
        self._go(
            head=create_head_pose(pitch=12, roll=5, degrees=True),
            antennas=[0.5, 0.5],
            duration=0.3,
        )
        time.sleep(0.5)
        self._home(0.8)

    def wake_up_stretch(self) -> None:
        """Wake up animation — stretch and perk up."""
        # Start droopy
        self._go(
            head=create_head_pose(pitch=15, degrees=True),
            antennas=[0.5, 0.5],
            duration=0.3,
        )
        time.sleep(0.3)
        # Stretch up
        self._go(
            head=create_head_pose(pitch=-15, degrees=True),
            antennas=[-0.9, -0.9],
            duration=0.8,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(0.5)
        # Shake it off
        for _ in range(2):
            self._go(head=create_head_pose(roll=8, degrees=True), duration=0.15)
            self._go(head=create_head_pose(roll=-8, degrees=True), duration=0.15)
        self._home(0.4)

    # ── Expressive / situational ──────────────────────────────────────

    def excited_bounce(self) -> None:
        """Quick bouncy up-down with antenna flapping — something exciting happened!"""
        for _ in range(3):
            self._go(
                head=create_head_pose(pitch=-10, degrees=True),
                antennas=[-1.0, -1.0],
                duration=0.2,
                method=InterpolationTechnique.CARTOON,
            )
            self._go(
                head=create_head_pose(pitch=5, degrees=True),
                antennas=[0.3, 0.3],
                duration=0.2,
                method=InterpolationTechnique.CARTOON,
            )
        # Final big bounce
        self._go(
            head=create_head_pose(pitch=-14, degrees=True),
            antennas=[-1.0, -1.0],
            duration=0.15,
            method=InterpolationTechnique.CARTOON,
        )
        time.sleep(0.3)
        self._home(0.3)

    def comfort_pat(self) -> None:
        """Gentle forward lean with slow side-to-side — like patting a shoulder."""
        self._go(
            head=create_head_pose(pitch=-10, roll=5, z=-4, degrees=True, mm=True),
            antennas=[-0.2, -0.2],
            duration=0.7,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        for _ in range(3):
            self._go(
                head=create_head_pose(pitch=-10, roll=6, z=-4, degrees=True, mm=True),
                antennas=[-0.2, -0.1],
                duration=0.5,
                method=InterpolationTechnique.EASE_IN_OUT,
            )
            self._go(
                head=create_head_pose(pitch=-10, roll=-6, z=-4, degrees=True, mm=True),
                antennas=[-0.1, -0.2],
                duration=0.5,
                method=InterpolationTechnique.EASE_IN_OUT,
            )
        self._home(0.5)

    def storytelling(self) -> None:
        """Animated head movements and antenna gestures for telling stories."""
        # Dramatic lean in
        self._go(
            head=create_head_pose(pitch=-8, yaw=-10, degrees=True),
            antennas=[-0.5, -0.3],
            duration=0.4,
            body_yaw=math.radians(-8),
        )
        time.sleep(0.3)
        # Sweep to the other side
        self._go(
            head=create_head_pose(pitch=-5, yaw=12, degrees=True),
            antennas=[-0.3, -0.6],
            duration=0.5,
            body_yaw=math.radians(8),
        )
        time.sleep(0.3)
        # Surprise beat — antennas pop up
        self._go(
            head=create_head_pose(pitch=5, degrees=True),
            antennas=[-1.0, -1.0],
            duration=0.2,
            method=InterpolationTechnique.CARTOON,
            body_yaw=0.0,
        )
        time.sleep(0.4)
        # Settle back
        self._go(
            head=create_head_pose(roll=6, degrees=True),
            antennas=[-0.3, -0.3],
            duration=0.4,
        )
        time.sleep(0.3)
        self._home(0.4)

    def exercise_demo(self) -> None:
        """Exaggerated stretch movements to demonstrate exercises."""
        # Big reach up
        self._go(
            head=create_head_pose(pitch=-22, degrees=True),
            antennas=[-1.0, -1.0],
            duration=0.8,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(0.5)
        # Lean left
        self._go(
            head=create_head_pose(roll=25, pitch=-10, degrees=True),
            antennas=[-0.6, 0.3],
            duration=0.7,
            body_yaw=math.radians(10),
        )
        time.sleep(0.5)
        # Lean right
        self._go(
            head=create_head_pose(roll=-25, pitch=-10, degrees=True),
            antennas=[0.3, -0.6],
            duration=0.7,
            body_yaw=math.radians(-10),
        )
        time.sleep(0.5)
        # Forward bend
        self._go(
            head=create_head_pose(pitch=-18, z=-6, degrees=True, mm=True),
            antennas=[0.1, 0.1],
            duration=0.8,
            body_yaw=0.0,
        )
        time.sleep(0.5)
        self._home(0.5)

    def music_sway(self) -> None:
        """Rhythmic swaying side to side with antenna conducting motions."""
        for _ in range(4):
            self._go(
                head=create_head_pose(roll=12, pitch=-5, degrees=True),
                antennas=[-0.7, -0.1],
                duration=0.5,
                method=InterpolationTechnique.EASE_IN_OUT,
                body_yaw=math.radians(8),
            )
            self._go(
                head=create_head_pose(roll=-12, pitch=-5, degrees=True),
                antennas=[-0.1, -0.7],
                duration=0.5,
                method=InterpolationTechnique.EASE_IN_OUT,
                body_yaw=math.radians(-8),
            )
        self._home(0.4)

    def attention_grab(self) -> None:
        """Quick antenna perk + head turn to get patient's attention."""
        # Antennas snap up
        self._go(
            head=create_head_pose(pitch=-5, degrees=True),
            antennas=[-1.0, -1.0],
            duration=0.15,
            method=InterpolationTechnique.LINEAR,
        )
        time.sleep(0.2)
        # Quick head turn
        self._go(
            head=create_head_pose(yaw=-15, pitch=-8, degrees=True),
            antennas=[-0.8, -0.8],
            duration=0.25,
            method=InterpolationTechnique.CARTOON,
        )
        time.sleep(0.4)
        # Turn to face forward
        self._go(
            head=create_head_pose(pitch=-6, degrees=True),
            antennas=[-0.6, -0.6],
            duration=0.3,
        )
        time.sleep(0.3)
        self._home(0.3)

    def proud(self) -> None:
        """Chest-out posture with antennas high — celebrating patient achievements."""
        self._go(
            head=create_head_pose(pitch=-12, z=-3, degrees=True, mm=True),
            antennas=[-1.0, -1.0],
            duration=0.6,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(1.0)
        # Little triumphant nod
        self._go(
            head=create_head_pose(pitch=-5, z=-3, degrees=True, mm=True),
            antennas=[-0.8, -0.8],
            duration=0.3,
        )
        self._go(
            head=create_head_pose(pitch=-12, z=-3, degrees=True, mm=True),
            antennas=[-1.0, -1.0],
            duration=0.3,
        )
        time.sleep(0.5)
        self._home(0.5)

    def worried(self) -> None:
        """Slight forward lean with antenna droop — showing concern."""
        self._go(
            head=create_head_pose(pitch=-6, roll=-4, z=-3, degrees=True, mm=True),
            antennas=[0.4, 0.4],
            duration=0.7,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(1.0)
        # Tiny anxious side-glance
        self._go(
            head=create_head_pose(pitch=-6, yaw=8, degrees=True),
            antennas=[0.3, 0.5],
            duration=0.4,
        )
        time.sleep(0.5)
        self._go(
            head=create_head_pose(pitch=-6, yaw=-8, degrees=True),
            antennas=[0.5, 0.3],
            duration=0.4,
        )
        time.sleep(0.5)
        self._home(0.5)

    def playful_peek(self) -> None:
        """Peek left then right like playing peekaboo."""
        # Hide (look down)
        self._go(
            head=create_head_pose(pitch=15, degrees=True),
            antennas=[0.5, 0.5],
            duration=0.3,
        )
        time.sleep(0.3)
        # Peek left
        self._go(
            head=create_head_pose(yaw=20, pitch=-5, degrees=True),
            antennas=[-0.6, -0.2],
            duration=0.3,
            method=InterpolationTechnique.CARTOON,
            body_yaw=math.radians(12),
        )
        time.sleep(0.4)
        # Hide again
        self._go(
            head=create_head_pose(pitch=15, degrees=True),
            antennas=[0.5, 0.5],
            duration=0.25,
            body_yaw=0.0,
        )
        time.sleep(0.3)
        # Peek right
        self._go(
            head=create_head_pose(yaw=-20, pitch=-5, degrees=True),
            antennas=[-0.2, -0.6],
            duration=0.3,
            method=InterpolationTechnique.CARTOON,
            body_yaw=math.radians(-12),
        )
        time.sleep(0.4)
        self._home(0.4)

    def meditation_guide(self, cycles: int = 3) -> None:
        """Very slow, flowing movements for meditation sessions.
        Slower and more serene than breathing_guide."""
        for i in range(cycles):
            # Slow rise — inhale (6 seconds)
            self._go(
                head=create_head_pose(pitch=-6, degrees=True),
                antennas=[-0.5, -0.5],
                duration=6.0,
                method=InterpolationTechnique.EASE_IN_OUT,
            )
            # Hold stillness (4 seconds)
            time.sleep(4.0)
            # Gentle sway at peak
            self._go(
                head=create_head_pose(pitch=-6, roll=4, degrees=True),
                antennas=[-0.4, -0.5],
                duration=2.0,
                method=InterpolationTechnique.EASE_IN_OUT,
            )
            self._go(
                head=create_head_pose(pitch=-6, roll=-4, degrees=True),
                antennas=[-0.5, -0.4],
                duration=2.0,
                method=InterpolationTechnique.EASE_IN_OUT,
            )
            # Slow descent — exhale (7 seconds)
            self._go(
                head=create_head_pose(pitch=4, degrees=True),
                antennas=[0.1, 0.1],
                duration=7.0,
                method=InterpolationTechnique.EASE_IN_OUT,
            )
            # Rest between cycles
            if i < cycles - 1:
                time.sleep(2.0)
        self._home(1.0)

    # ── Utility ─────────────────────────────────────────────────────

    def sleep(self) -> None:
        """Go to sleep pose."""
        self.mini.goto_sleep()

    def wake(self) -> None:
        """Wake up from sleep."""
        self.mini.wake_up()

    def reset(self, duration: float = 0.5) -> None:
        """Return to neutral."""
        self._home(duration)

    # ── Idle / ambient animations ───────────────────────────────────

    def idle_look(self) -> None:
        """Subtle look to one side then back — Reachy seems aware."""
        import random
        yaw = random.choice([-8, 8, -5, 5])
        self._go(head=create_head_pose(yaw=yaw, mm=True, degrees=True), duration=1.2)
        time.sleep(1.5)
        self._home(1.0)

    def idle_tilt(self) -> None:
        """Gentle head tilt — Reachy looks curious/alive."""
        import random
        roll = random.choice([-6, 6, -4, 4])
        self._go(head=create_head_pose(roll=roll, mm=True, degrees=True), duration=0.8)
        time.sleep(1.0)
        self._home(0.8)

    def idle_breathe(self) -> None:
        """Subtle breathing motion — very gentle up/down."""
        self._go(head=create_head_pose(z=3, mm=True, degrees=True), duration=1.5)
        time.sleep(0.3)
        self._go(head=create_head_pose(z=-2, mm=True, degrees=True), duration=1.5)
        time.sleep(0.3)
        self._home(1.0)

    def idle_antenna_twitch(self) -> None:
        """Quick antenna twitch — Reachy seems alert."""
        import random
        a1 = random.randint(-15, 15)
        a2 = random.randint(-15, 15)
        self._go(antennas=[a1, a2], duration=0.3)
        time.sleep(0.4)
        self._go(antennas=[0, 0], duration=0.4)
