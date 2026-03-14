"""Full movement pattern library for Reachy Mini.

Uses head (pitch/roll/yaw + xyz), two antennas, body yaw,
and multiple interpolation styles to create expressive animations."""

import math
import time
import numpy as np
from reachy_mini.utils import create_head_pose
from reachy_mini.utils.interpolation import InterpolationTechnique


class Movements:
    """Collection of expressive movement patterns for Reachy Mini."""

    def __init__(self, mini):
        self.mini = mini

    # ── Helpers ──────────────────────────────────────────────────────

    def _go(self, head=None, antennas=None, duration=0.5,
            method=InterpolationTechnique.MIN_JERK, body_yaw=None):
        kwargs = {"duration": duration, "method": method}
        if head is not None:
            kwargs["head"] = head
        if antennas is not None:
            kwargs["antennas"] = antennas
        if body_yaw is not None:
            kwargs["body_yaw"] = body_yaw
        self.mini.goto_target(**kwargs)

    def _home(self, duration=0.4):
        self._go(
            head=create_head_pose(),
            antennas=[0, 0],
            duration=duration,
            body_yaw=0.0,
        )

    # ── Basic gestures ──────────────────────────────────────────────

    def nod_yes(self):
        """Nod head up and down — 'yes'."""
        for _ in range(2):
            self._go(head=create_head_pose(pitch=-12, degrees=True), duration=0.25)
            self._go(head=create_head_pose(pitch=8, degrees=True), duration=0.25)
        self._home(0.3)

    def shake_no(self):
        """Shake head side to side — 'no'."""
        for _ in range(2):
            self._go(head=create_head_pose(yaw=-15, degrees=True), duration=0.25)
            self._go(head=create_head_pose(yaw=15, degrees=True), duration=0.25)
        self._home(0.3)

    def greeting(self):
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

    def goodbye(self):
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

    def happy_wiggle(self):
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

    def celebrate(self):
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

    def sad_droop(self):
        """Sad expression — slow droop of head and antennas."""
        self._go(
            head=create_head_pose(pitch=12, roll=-8, degrees=True),
            antennas=[0.5, 0.5],
            duration=1.0,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(1.0)
        self._home(0.8)

    def empathy_lean(self):
        """Lean forward with gentle head tilt — showing empathy."""
        self._go(
            head=create_head_pose(pitch=-8, roll=6, z=-5, degrees=True, mm=True),
            antennas=[-0.2, -0.2],
            duration=0.7,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(1.5)
        self._home(0.6)

    def scared_startle(self):
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

    def surprised(self):
        """Surprise — quick antenna raise + head back."""
        self._go(
            head=create_head_pose(pitch=8, degrees=True),
            antennas=[-1.0, -1.0],
            duration=0.2,
            method=InterpolationTechnique.CARTOON,
        )
        time.sleep(0.6)
        self._home(0.4)

    def angry_huff(self):
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

    def confused_tilt(self):
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

    def thinking(self):
        """Thinking pose — slow head tilt + antenna droop."""
        self._go(
            head=create_head_pose(roll=12, pitch=-3, degrees=True),
            antennas=[0.1, -0.3],
            duration=0.6,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(1.2)
        self._home(0.5)

    def listening(self):
        """Attentive listening — lean forward, antennas perked."""
        self._go(
            head=create_head_pose(pitch=-10, degrees=True),
            antennas=[-0.4, -0.4],
            duration=0.5,
            method=InterpolationTechnique.EASE_IN_OUT,
        )
        time.sleep(2.0)
        self._home(0.4)

    def curious_look(self):
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

    def look_around(self):
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

    def dance(self):
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

    def silly_wiggle(self):
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

    def bow(self):
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

    def breathing_guide(self, cycles: int = 3):
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

    def gentle_rock(self):
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

    def stretch(self):
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

    def sleepy(self):
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

    def wake_up_stretch(self):
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

    # ── Utility ─────────────────────────────────────────────────────

    def sleep(self):
        """Go to sleep pose."""
        self.mini.goto_sleep()

    def wake(self):
        """Wake up from sleep."""
        self.mini.wake_up()

    def reset(self, duration=0.5):
        """Return to neutral."""
        self._home(duration)
