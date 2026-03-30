# Reachy Care — 100 Tasks

Organized by category. Each task is a concrete, buildable feature.

---

## 🔊 Sound & Audio (1-12)

- [x] 1. Sound effects engine — play WAV files through Reachy's speaker for game sounds (ding, buzzer, applause, drumroll)
- [x] 2. Ambient soundscapes — play rain, ocean, birds, fireplace through Reachy during calm moments or night mode
- [x] 3. Voice speed control — "speak slower" / "speak faster" adjusts OpenAI TTS speed parameter
- [x] 4. Volume control — "speak louder" / "speak quieter" adjusts Reachy's speaker output level
- [x] 5. Sound-based games — Reachy plays a sound and patient guesses what it is (animal sounds, instruments, nature)
- [x] 6. Musical instrument mode — antennas play different notes based on position, patient conducts
- [x] 7. Doorbell detection — Reachy hears the doorbell and tells the patient "I think someone's at the door!"
- [x] 8. Sound direction awareness — use `get_DoA()` to detect where sound comes from and turn toward it
- [x] 9. Ambient noise monitoring — detect if the room is too loud/quiet and adjust Reachy's voice volume
- [x] 10. Lullaby player — play gentle lullabies through Reachy's speaker at bedtime
- [x] 11. Audiobook reader — Reachy reads a book aloud with expressive head movements matching the story
- [x] 12. Sound memory game — Reachy plays a sequence of sounds, patient repeats them back

## 🎯 Spatial Awareness (13-22)

- [x] 13. Sound direction head tracking — use `get_DoA()` to turn toward whoever is speaking
- [x] 14. Object look-at — detect objects in camera, patient says "look at the cup" and Reachy turns to it using `look_at_image()`
- [x] 15. Room scanning — Reachy slowly looks around the room using `look_at_world()` and describes what it sees
- [x] 16. Multi-person awareness — detect multiple faces, track who's speaking, address them by position
- [ ] 17. Point-and-describe — patient points at something, Reachy follows the point direction and describes it
- [x] 18. Spatial memory — remember where objects are in the room ("Your glasses are on the table to your left")
- [x] 19. Body rotation for multi-person — use `set_target_body_yaw()` to face different people in the room
- [x] 20. Distance awareness — estimate how far the patient is and adjust voice volume accordingly
- [x] 21. Room change detection — notice when furniture moves or new objects appear ("Oh, you rearranged!")
- [x] 22. Window/light awareness — detect if it's bright or dark in the room and comment on it

## 🤸 Physical Interaction & Games (23-38)

- [x] 23. Teach Reachy moves — enable gravity compensation, patient physically poses Reachy, record with `start_recording()`, play back with `play_move()`
- [x] 24. Emotion charades — Reachy acts out an emotion with body language, patient guesses
- [x] 25. Simon Says — Reachy does a move, patient copies, then patient does a move, Reachy copies via head mirror
- [x] 26. Rhythm game — Reachy taps a beat with antennas, patient claps along, difficulty increases
- [x] 27. Antenna semaphore — teach a simple antenna language (both up = happy, one up = question, etc.)
- [x] 28. Choreographed performances — `play_move()` with synced audio for dance routines
- [x] 29. Reaction time game — Reachy moves suddenly, patient says "now!" as fast as possible, track reaction time
- [x] 30. Head gesture language — patient defines custom gestures ("two wiggles means I love you")
- [x] 31. Puppet mode — patient controls Reachy in real-time through gravity compensation, like a puppet
- [x] 32. Bump/shake detection — use IMU to detect if someone touches/bumps Reachy, react ("That tickles!")
- [x] 33. Tilt game — Reachy tilts its head and patient has to match the angle, scored by camera
- [x] 34. Antenna counting game — Reachy raises antennas a certain number of times, patient counts
- [x] 35. Follow the leader — alternate between Reachy leading moves and patient leading (using head mirror)
- [x] 36. Freeze dance — play music, Reachy dances, music stops, both freeze, camera checks if patient moved
- [x] 37. Gentle exercise coach — Reachy demonstrates head/neck stretches, patient follows along
- [x] 38. Morning stretch routine — guided stretching with Reachy demonstrating each move

## 📷 Camera Intelligence (39-52)

- [x] 39. Object show-and-tell — patient holds up an object, Reachy identifies and talks about it
- [x] 40. Facial expression reading — use camera to read patient's face expression for more accurate mood detection
- [x] 41. Room awareness narration — "I can see your cozy chair, the window with sunlight, and some books"
- [x] 42. Clothing compliments — detect what the patient is wearing and compliment them
- [x] 43. Meal detection — see when the patient is eating and log it to nutrition tracker
- [x] 44. Fall detection via camera — detect if the patient falls and alert caregiver immediately
- [x] 45. Visitor recognition — learn faces of family members and greet them by name when they visit
- [x] 46. Pet detection — notice when a pet is in the room and comment on it
- [x] 47. Plant/garden monitoring — patient shows their plants, Reachy tracks growth over time
- [x] 48. Art appreciation — patient shows artwork or photos, Reachy gives thoughtful commentary
- [x] 49. Medication verification — patient shows their pill, Reachy confirms it looks right
- [x] 50. Weather-from-window — look out the window and describe the weather it sees
- [x] 51. Activity detection — detect if patient is reading, knitting, watching TV and comment naturally
- [x] 52. Smile counter — count how many times the patient smiled today, share the count at end of session

## 🧠 Conversation & Intelligence (53-68)

- [x] 53. Life story builder — compile conversations into a structured life narrative over many sessions
- [x] 54. Daily journal — auto-generate a journal entry from each day's conversations for family to read
- [x] 55. Relationship map — build a visual family tree from mentioned names and relationships
- [x] 56. Conversation replay — store timestamped turns, build a player UI to replay past sessions
- [x] 57. Dream journal — if patient describes a dream, log it and reference it later
- [x] 58. Wish list tracker — "I wish I could..." statements get saved and shared with family
- [x] 59. Advice book — collect wisdom and advice the patient shares, compile into a "book"
- [x] 60. Recipe collector — when patient describes a recipe, save it structured with ingredients and steps
- [x] 61. Joke library — learn which jokes the patient tells and never repeat them back, but laugh every time
- [x] 62. Song request memory — remember their favorite songs and offer to play them at the right moments
- [x] 63. Holiday awareness — know what holiday it is and bring it up naturally with relevant memories
- [x] 64. Birthday tracker — remember birthdays of mentioned family members, remind patient when they're coming up
- [x] 65. "This day in history" — share an interesting historical event from today's date
- [x] 66. Compliment generator — give genuine, specific compliments based on what Reachy knows about them
- [x] 67. Worry jar — patient shares worries, Reachy "puts them in the jar" and checks back later
- [x] 68. Gratitude chain — build on previous gratitude sessions, creating a growing list over weeks

## 👨‍👩‍👧 Family & Caregiver (69-80)

- [x] 69. Family portal — separate dashboard login for family to leave voice messages and see highlights
- [x] 70. Voice message relay — family records a message on dashboard, Reachy plays it at the right moment
- [x] 71. Photo sharing — family uploads photos to dashboard, Reachy shows them via camera description
- [x] 72. Daily highlight reel — auto-generate a 3-sentence summary of the best moments for family
- [x] 73. Caregiver shift briefing — when a new caregiver logs in, Reachy summarizes the patient's day
- [x] 74. Family Q&A — family submits questions ("Ask mom about her garden"), Reachy works them into conversation
- [x] 75. Milestone alerts — notify family when patient hits milestones (100th conversation, 30-day streak)
- [x] 76. Mood report email — daily/weekly mood summary emailed to family
- [x] 77. Emergency contact chain — if distress detected and caregiver doesn't respond, escalate to family
- [x] 78. Visitor log — Reachy notes when visitors come (via face detection) and logs it
- [x] 79. Care plan integration — pull care plan from dashboard and weave tasks into conversation naturally
- [x] 80. Multi-patient handoff — when Reachy moves to a different patient, smooth context switch

## 🎨 Dashboard & UI (81-92)

- [x] 81. Live view page — watch conversation in real-time with camera feed, mood indicator, engagement score
- [x] 82. Conversation search — full-text search across all past conversations
- [x] 83. Mood calendar — calendar view showing dominant mood for each day, click to see details
- [x] 84. Topic cloud — word cloud visualization of most-discussed topics
- [x] 85. Relationship graph — visual network of mentioned people and their connections
- [x] 86. Session comparison — compare two sessions side by side (engagement, mood, topics)
- [x] 87. Export life story — generate a PDF of the patient's life story from collected conversations
- [x] 88. Customizable dashboard widgets — drag-and-drop widgets for different data views
- [x] 89. Mobile PWA improvements — push notifications for alerts, offline mode, native feel
- [x] 90. Dark/light theme per user — save theme preference per login
- [x] 91. Patient profile editor — edit patient details, birth year, preferences, photo from dashboard
- [x] 92. Activity scheduler — visual calendar to schedule activities, reminders, and routines

## 🔧 Technical & Infrastructure (93-100)

- [ ] 93. Auto-deploy to Railway — CI/CD pipeline deploys on merge to main
- [ ] 94. Type hints for remaining files — `realtime_conversation.py`, `brain.py`, `app.py`
- [ ] 95. Offline mode — fallback to Ollama + local Whisper when internet is down
- [ ] 96. Multi-patient support — real patient switching with isolated data per patient
- [ ] 97. WebRTC video calling — real browser-to-browser video calls through the dashboard
- [ ] 98. Rate limiting — protect API endpoints from abuse
- [ ] 99. Database backup system — automated Supabase backups with restore capability
- [ ] 100. Performance monitoring — track response times, API latency, and system health metrics
