"""Stargazing Buddy — Reachy as a companion for astronomical observation.

Identifies constellations, shares facts about stars and planets,
and tells stories about the night sky.
"""

import logging
import os
import random

logger = logging.getLogger(__name__)

CONSTELLATIONS = {
    "orion": {
        "name": "Orion the Hunter",
        "best_season": "winter",
        "stars": ["Betelgeuse", "Rigel", "Bellatrix"],
        "fact": "Orion's Belt is made of three stars in a row — Alnitak, Alnilam, and Mintaka. Ancient Egyptians aligned the pyramids of Giza with these three stars.",
        "story": "In Greek mythology, Orion was a giant huntsman placed among the stars by Zeus. He's forever chasing the Pleiades across the sky.",
    },
    "ursa_major": {
        "name": "Ursa Major (Big Dipper)",
        "best_season": "spring",
        "stars": ["Dubhe", "Merak", "Alioth", "Mizar"],
        "fact": "The two stars at the end of the Big Dipper's bowl point directly to Polaris, the North Star. Sailors have used this trick for centuries.",
        "story": "The Greeks saw a great bear in these stars. Zeus placed the bear in the sky to protect her from hunters.",
    },
    "cassiopeia": {
        "name": "Cassiopeia",
        "best_season": "autumn",
        "stars": ["Schedar", "Caph", "Navi"],
        "fact": "Cassiopeia looks like a W or M depending on the time of year. It never sets below the horizon in northern latitudes.",
        "story": "Queen Cassiopeia boasted she was more beautiful than the sea nymphs. As punishment, she was placed in the sky on a throne that sometimes hangs upside down.",
    },
    "leo": {
        "name": "Leo the Lion",
        "best_season": "spring",
        "stars": ["Regulus", "Denebola", "Algieba"],
        "fact": "Regulus, Leo's brightest star, is actually four stars orbiting each other. It spins so fast it's shaped like a flattened ball.",
        "story": "Leo represents the Nemean Lion from Greek mythology, whose golden fur was impervious to weapons. Hercules defeated it as his first labor.",
    },
    "scorpius": {
        "name": "Scorpius",
        "best_season": "summer",
        "stars": ["Antares", "Shaula", "Sargas"],
        "fact": "Antares, the heart of the scorpion, is a red supergiant 700 times the size of our Sun. Its name means 'rival of Mars' because of its red color.",
        "story": "Scorpius was sent by the goddess Artemis to defeat Orion. That's why they're on opposite sides of the sky — when Scorpius rises, Orion sets.",
    },
    "cygnus": {
        "name": "Cygnus the Swan",
        "best_season": "summer",
        "stars": ["Deneb", "Albireo", "Sadr"],
        "fact": "Deneb is one of the most luminous stars visible to the naked eye — about 200,000 times brighter than our Sun, but so far away it looks like just another star.",
        "story": "Zeus disguised himself as a swan to visit the mortal Leda. The constellation flies along the Milky Way with wings spread wide.",
    },
}

PLANETS = {
    "mercury": "The smallest planet and closest to the Sun. A year on Mercury is just 88 Earth days, but a single day lasts 59 Earth days!",
    "venus": "The hottest planet in our solar system at 900°F, even hotter than Mercury. It spins backwards compared to most planets.",
    "mars": "The Red Planet has the tallest volcano in the solar system — Olympus Mons, three times the height of Mount Everest.",
    "jupiter": "So massive that 1,300 Earths could fit inside it. The Great Red Spot is a storm that's been raging for at least 400 years.",
    "saturn": "Its rings are made of billions of pieces of ice and rock. Saturn is so light it would float in water if you had a big enough bathtub.",
}

SPACE_FACTS = [
    "A teaspoon of neutron star material would weigh about 6 billion tons.",
    "There are more stars in the universe than grains of sand on all of Earth's beaches.",
    "Light from the Sun takes 8 minutes and 20 seconds to reach Earth.",
    "The footprints on the Moon will be there for 100 million years because there's no wind.",
    "A day on Venus is longer than a year on Venus.",
    "The Milky Way and Andromeda galaxies will collide in about 4.5 billion years.",
    "Space is completely silent because there's no air for sound to travel through.",
    "The International Space Station orbits Earth every 90 minutes.",
]


class StargazingBuddy:
    """Astronomical companion that shares constellation facts and stories."""

    def __init__(self):
        self._facts_shared = 0

    def identify_sky(self) -> str:
        """Use camera to try to identify what's in the night sky."""
        try:
            from perception.vision import capture_frame
            frame_b64 = capture_frame()
            if not frame_b64:
                return self.random_fact()
        except Exception:
            return self.random_fact()

        try:
            import json
            import urllib.request
            api_key = os.environ.get("OPENAI_API_KEY", "")
            body = json.dumps({
                "model": "gpt-4o",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": (
                            "You are a friendly stargazing companion. Look at this image of the sky. "
                            "Identify any constellations, planets, or celestial objects you can see. "
                            "Share interesting facts about them in a warm, conversational way. "
                            "If you can't identify specific objects, describe what you see and share "
                            "a related astronomy fact. Keep it to 3-5 sentences."
                        )},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_b64}",
                            "detail": "low",
                        }},
                    ],
                }],
                "max_tokens": 300,
            }).encode()
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=body,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=15)
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error("Sky identification failed: %s", e)
            return self.random_fact()

    def constellation_info(self, name: str) -> str:
        """Get info about a specific constellation."""
        key = name.lower().replace(" ", "_").replace("the ", "")
        if key in CONSTELLATIONS:
            c = CONSTELLATIONS[key]
            self._facts_shared += 1
            return (
                f"{c['name']} — best seen in {c['best_season']}. "
                f"Key stars: {', '.join(c['stars'])}. "
                f"{c['fact']} {c['story']}"
            )
        # Try partial match
        for k, c in CONSTELLATIONS.items():
            if name.lower() in c["name"].lower() or name.lower() in k:
                self._facts_shared += 1
                return (
                    f"{c['name']} — best seen in {c['best_season']}. "
                    f"Key stars: {', '.join(c['stars'])}. "
                    f"{c['fact']} {c['story']}"
                )
        return f"I don't have info on '{name}' yet, but here's a fun fact: {self.random_fact()}"

    def planet_info(self, name: str) -> str:
        key = name.lower().strip()
        if key in PLANETS:
            self._facts_shared += 1
            return f"{name.title()}: {PLANETS[key]}"
        return f"I don't have info on '{name}'. Try Mercury, Venus, Mars, Jupiter, or Saturn!"

    def random_fact(self) -> str:
        self._facts_shared += 1
        return random.choice(SPACE_FACTS)

    def list_constellations(self) -> str:
        names = [c["name"] for c in CONSTELLATIONS.values()]
        return f"I know about: {', '.join(names)}. Ask me about any of them!"

    def get_status(self) -> dict:
        return {
            "facts_shared": self._facts_shared,
            "constellations_available": len(CONSTELLATIONS),
            "planets_available": len(PLANETS),
        }
