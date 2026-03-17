"""Story reader — Reachy reads short stories and fables aloud,
one passage at a time so the patient can enjoy at their pace."""

import random

STORIES = {
    "the_tortoise_and_the_hare": {
        "title": "The Tortoise and the Hare",
        "category": "fable",
        "pages": [
            "Once upon a time, there was a very fast hare who loved to brag about how quick he was.",
            "One day, a slow but steady tortoise challenged the hare to a race. The hare laughed and said, 'You? Race me? This will be easy!'",
            "The race began. The hare sprinted ahead and was so far in front that he decided to take a nap under a tree.",
            "Meanwhile, the tortoise kept walking. Slowly, steadily, one step at a time. He never stopped.",
            "When the hare woke up, he saw the tortoise was almost at the finish line! He ran as fast as he could, but it was too late.",
            "The tortoise crossed the finish line first! The moral of the story: slow and steady wins the race.",
        ],
    },
    "the_golden_fish": {
        "title": "The Golden Fish",
        "category": "fairy tale",
        "pages": [
            "An old fisherman lived by the sea with his wife in a tiny hut. Every day he went fishing.",
            "One day, he caught a beautiful golden fish. The fish spoke! 'Please let me go, and I will grant you a wish.'",
            "The kind fisherman let the fish go without asking for anything. When he told his wife, she was angry. 'Go back and ask for a new house!'",
            "The fisherman went back to the sea and called the golden fish. The fish granted the wish, and they had a lovely new house.",
            "But the wife wanted more and more — a palace, then to be queen, then to rule the sea itself.",
            "The golden fish said, 'Enough.' And everything went back to the way it was — the tiny hut by the sea.",
            "The fisherman learned that being grateful for what you have is the greatest treasure of all.",
        ],
    },
    "the_kind_elephant": {
        "title": "The Kind Elephant",
        "category": "children's story",
        "pages": [
            "In a lush green forest, there lived a big, gentle elephant named Ellie.",
            "Ellie loved helping the other animals. She would carry the little ones across the river on her back.",
            "One stormy night, a tiny bird lost her nest. She was cold and scared, sitting in the rain.",
            "Ellie found the bird and sheltered her under her big ears. 'Don't worry, little one. You're safe with me.'",
            "The next morning, all the animals helped rebuild the bird's nest, even bigger and stronger than before.",
            "The little bird sang the most beautiful song as a thank you. And Ellie smiled her big elephant smile.",
            "From that day on, whenever anyone needed help, they knew Ellie would be there. Because kindness always comes back around.",
        ],
    },
    "the_stars_at_night": {
        "title": "The Stars at Night",
        "category": "bedtime story",
        "pages": [
            "When the sun goes down and the sky turns dark, something magical happens.",
            "One by one, tiny lights appear in the sky. These are the stars, and each one has a story.",
            "There's the North Star, always pointing the way home for travelers.",
            "And the Big Dipper, which looks like a giant ladle scooping up the night sky.",
            "Some people say that when you see a shooting star, you should make a wish.",
            "So tonight, if you look up at the sky, pick your favorite star. That one is yours.",
            "And every night, it will be there, shining just for you. Goodnight, and sweet dreams.",
        ],
    },
    "grandmas_garden": {
        "title": "Grandma's Garden",
        "category": "nostalgic",
        "pages": [
            "Grandma had the most wonderful garden in the whole neighborhood.",
            "There were roses of every color — red, pink, yellow, and white. And sunflowers that stood taller than the fence.",
            "In the summer, the garden was full of butterflies and the sweet smell of lavender.",
            "Grandma would sit in her rocking chair and tell stories while we picked tomatoes and strawberries.",
            "She always said, 'A garden is like life. You plant seeds of kindness, water them with love, and watch beautiful things grow.'",
            "Even now, whenever I smell fresh flowers, I think of Grandma and her magical garden.",
        ],
    },
}


class StoryReader:
    def __init__(self):
        self.active = False
        self._current_story = None
        self._page_index = 0

    @property
    def is_active(self):
        return self.active

    def list_stories(self) -> str:
        lines = ["Here are the stories I can read to you:"]
        for key, story in STORIES.items():
            lines.append(f"- {story['title']} ({story['category']})")
        lines.append("\nJust say the name, or say 'read me a story' for a surprise!")
        return "\n".join(lines)

    def start_story(self, text: str = "") -> str:
        lower = text.lower() if text else ""
        chosen = None
        for key, story in STORIES.items():
            if story["title"].lower() in lower or key.replace("_", " ") in lower:
                chosen = key
                break
        # Category match
        if not chosen:
            for key, story in STORIES.items():
                if story["category"] in lower:
                    chosen = key
                    break
        if not chosen:
            chosen = random.choice(list(STORIES.keys()))

        story = STORIES[chosen]
        self.active = True
        self._current_story = chosen
        self._page_index = 0
        first_page = story["pages"][0]
        self._page_index = 1
        return f"Let me read you '{story['title']}'.\n\n{first_page}\n\nSay 'next' to continue, or 'stop' to end."

    def next_page(self) -> str:
        if not self.active or not self._current_story:
            return "No story in progress. Say 'read me a story' to start!"
        story = STORIES[self._current_story]
        if self._page_index >= len(story["pages"]):
            self.active = False
            return f"The end! That was '{story['title']}'. Would you like to hear another story?"
        page = story["pages"][self._page_index]
        self._page_index += 1
        remaining = len(story["pages"]) - self._page_index
        if remaining > 0:
            return f"{page}\n\n({remaining} pages left. Say 'next' to continue.)"
        return f"{page}\n\n(Last page coming up! Say 'next'.)"

    def stop(self) -> str:
        title = STORIES.get(self._current_story, {}).get("title", "the story")
        self.active = False
        self._current_story = None
        return f"Okay, we'll stop {title} for now. We can pick it up again anytime!"
    
def get_story_count() -> int:
    return len(STORIES)