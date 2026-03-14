"""Guided physical exercises — Reachy leads the patient through
gentle seated exercises with verbal instructions and robot movements."""

import random

EXERCISES = {
    "neck_rolls": {
        "name": "Neck Rolls",
        "duration": "2 minutes",
        "steps": [
            "Let's start with some gentle neck rolls.",
            "Slowly tilt your head to the right... hold for 3 seconds.",
            "Now roll it forward, chin to chest... hold.",
            "Continue to the left side... hold for 3 seconds.",
            "And back to center. Great job!",
            "Let's do that one more time in the other direction.",
            "Tilt left... forward... right... and center.",
            "Wonderful! Your neck should feel a bit looser now.",
        ],
        "robot_action": "stretch",
    },
    "shoulder_shrugs": {
        "name": "Shoulder Shrugs",
        "duration": "2 minutes",
        "steps": [
            "Time for shoulder shrugs! These help release tension.",
            "Raise both shoulders up toward your ears... hold...",
            "And release. Let them drop down. Feel that relief?",
            "Again — shoulders up... hold... and release.",
            "One more time. Up... hold... and let go.",
            "Now roll your shoulders forward in circles... 3 times.",
            "And backward... 3 times.",
            "Great work! Shoulders feeling better?",
        ],
        "robot_action": "stretch",
    },
    "arm_raises": {
        "name": "Arm Raises",
        "duration": "3 minutes",
        "steps": [
            "Let's do some gentle arm raises.",
            "If you can, raise your right arm slowly above your head.",
            "Hold it there for a moment... and slowly bring it down.",
            "Now your left arm. Raise it up... hold... and down.",
            "Let's try both arms together. Up... hold... and down.",
            "Again — both arms up... hold... and gently down.",
            "One more time. Up... hold... and relax.",
            "Excellent! That helps with circulation and flexibility.",
        ],
        "robot_action": "stretch",
    },
    "ankle_circles": {
        "name": "Ankle Circles",
        "duration": "2 minutes",
        "steps": [
            "Let's move to your ankles. You can do this sitting down.",
            "Lift your right foot slightly off the ground.",
            "Rotate your ankle in circles... 5 times clockwise.",
            "Now 5 times counter-clockwise.",
            "Switch to your left foot. 5 circles clockwise.",
            "And 5 circles counter-clockwise.",
            "Great! This helps prevent stiffness and improves balance.",
        ],
        "robot_action": "rock",
    },
    "deep_breathing": {
        "name": "Deep Breathing Exercise",
        "duration": "3 minutes",
        "steps": [
            "Let's do some deep breathing together.",
            "Sit comfortably and close your eyes if you'd like.",
            "Breathe in through your nose... 1... 2... 3... 4...",
            "Hold gently... 1... 2... 3... 4...",
            "Breathe out through your mouth... 1... 2... 3... 4...",
            "Again. In... 1... 2... 3... 4...",
            "Hold... 1... 2... 3... 4...",
            "Out... 1... 2... 3... 4...",
            "One more time. In... hold... and out...",
            "Beautiful. How do you feel?",
        ],
        "robot_action": "breathe",
    },
    "hand_exercises": {
        "name": "Hand & Finger Exercises",
        "duration": "2 minutes",
        "steps": [
            "Let's exercise our hands and fingers.",
            "Make a fist with both hands. Squeeze tight... and release.",
            "Spread your fingers wide apart... and relax.",
            "Again — fist... squeeze... and open wide.",
            "Now touch each finger to your thumb. Index... middle... ring... pinky.",
            "And back. Pinky... ring... middle... index.",
            "One more round. This helps with dexterity and grip strength.",
            "Wonderful job! Your hands are getting a nice workout.",
        ],
        "robot_action": "curious",
    },
    "seated_march": {
        "name": "Seated Marching",
        "duration": "2 minutes",
        "steps": [
            "Time for some seated marching! Stay in your chair.",
            "Lift your right knee up... and down.",
            "Left knee up... and down.",
            "Right... left... right... left...",
            "Keep going at your own pace. You're doing great!",
            "A few more... right... left... right... left...",
            "And rest. That gets the blood flowing!",
        ],
        "robot_action": "dance",
    },
}

# Quick routines that combine multiple exercises
ROUTINES = {
    "morning": ["deep_breathing", "neck_rolls", "shoulder_shrugs", "arm_raises"],
    "afternoon": ["hand_exercises", "ankle_circles", "seated_march"],
    "evening": ["neck_rolls", "deep_breathing"],
    "quick": ["shoulder_shrugs", "hand_exercises"],
}


class GuidedExercises:
    def __init__(self):
        self.active = False
        self._current_exercise = None
        self._step_index = 0
        self._routine_queue = []

    @property
    def is_active(self):
        return self.active

    def list_exercises(self) -> str:
        names = [e["name"] for e in EXERCISES.values()]
        routines = ", ".join(ROUTINES.keys())
        return (
            "Here are the exercises I can guide you through:\n"
            + "\n".join(f"- {n}" for n in names)
            + f"\n\nOr try a routine: {routines}\n"
            "Just say the name of an exercise or routine!"
        )

    def start_exercise(self, text: str) -> tuple[str, str]:
        """Start an exercise. Returns (response_text, robot_action)."""
        lower = text.lower()

        # Check for routines first
        for routine_name, exercise_list in ROUTINES.items():
            if routine_name in lower:
                self._routine_queue = list(exercise_list)
                return self._start_next_from_queue()

        # Check for specific exercises
        for key, ex in EXERCISES.items():
            if key.replace("_", " ") in lower or ex["name"].lower() in lower:
                return self._begin_exercise(key)

        # Random exercise
        key = random.choice(list(EXERCISES.keys()))
        return self._begin_exercise(key)

    def _begin_exercise(self, key: str) -> tuple[str, str]:
        ex = EXERCISES[key]
        self.active = True
        self._current_exercise = key
        self._step_index = 0
        step = ex["steps"][0]
        self._step_index = 1
        intro = f"Let's do {ex['name']}! This takes about {ex['duration']}."
        return f"{intro}\n{step}", ex["robot_action"]

    def _start_next_from_queue(self) -> tuple[str, str]:
        if not self._routine_queue:
            self.active = False
            return "Great routine! You did an amazing job. How do you feel?", "celebrate"
        key = self._routine_queue.pop(0)
        return self._begin_exercise(key)

    def next_step(self) -> tuple[str, str]:
        """Advance to the next step. Returns (text, robot_action)."""
        if not self.active or not self._current_exercise:
            return "No exercise in progress. Say 'exercise' to start!", ""

        ex = EXERCISES[self._current_exercise]
        if self._step_index >= len(ex["steps"]):
            # Exercise done
            if self._routine_queue:
                done_msg = f"Finished {ex['name']}! "
                next_text, next_action = self._start_next_from_queue()
                return done_msg + next_text, next_action
            self.active = False
            return f"All done with {ex['name']}! Great job! How do you feel?", "celebrate"

        step = ex["steps"][self._step_index]
        self._step_index += 1
        return step, ex["robot_action"]

    def stop(self) -> str:
        self.active = False
        self._current_exercise = None
        self._routine_queue = []
        return "Okay, we'll stop the exercise. You did well! We can try again anytime."
