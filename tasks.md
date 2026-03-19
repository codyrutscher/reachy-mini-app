# Reachy Care Dashboard — Practice Tasks

Difficulty: 🟢 easy | 🟡 medium | 🔴 hard
Skills in parentheses. Check off as you complete them.

Work through these one at a time — each one teaches a specific skill.

---

## 🟦 activity.html (8 tasks)

- [x] 1. 🟢 Add `display: flex` and `gap: 10px` to `.activity-row` so icon and text sit side by side (CSS)
- [x] 2. 🟢 Add a row count next to the subtitle that updates when you filter, like "Showing 12 events" (JS)
- [x] 3. 🟡 Color-code the left border of each row by action type — red for alerts, green for meds, blue for messages (JS + CSS)
- [x] 4. 🟡 Add a search input that filters rows by text content in real-time as you type (HTML + JS)
- [x] 5. 🟡 Write a `timeAgo()` function that shows "2 hours ago" instead of raw timestamps (JS)
- [x] 6. 🟡 Add a "Clear Filters" button that resets the dropdown and search box (HTML + JS)
- [x] 7. 🔴 Add summary stat cards above the list — total events, alerts count, med events, patient interactions (HTML + JS)
- [x] 8. 🔴 Group activities by date with sticky date headers like "Today", "Yesterday", "March 13" (JS + CSS)

## 🟦 dashboard.html (15 tasks)

- [x] 9. 🟢 Change the camera "offline" message to something more helpful with a retry button (HTML + CSS)
- [x] 10. 🟢 Add a pulsing animation to the alert stat cards when count is > 0 (CSS)
- [x] 11. 🟡 Add a "last updated" timestamp that shows when data was last refreshed (JS)
- [x] 12. 🟡 Make the conversation bubbles show relative time ("2m ago") instead of raw timestamps (JS)
- [x] 13. 🟡 Add a notification sound toggle button in the header (HTML + JS)
- [x] 14. 🔴 Add a mini mood chart in the patient bar showing the last 10 mood readings as colored dots (JS + CSS)
- [x] 15. 🔴 Make the quick message buttons customizable — save custom ones to localStorage (JS)
- [ ] 16. 🟢 Add a welcome banner that shows the caregiver's name and current shift time (HTML + JS)
- [ ] 17. 🟡 Add a "patient at a glance" summary card — name, mood, last spoke, current activity (HTML + JS)
- [x] 18. 🟡 Add auto-scroll to the conversation panel so new messages are always visible (JS)
- [ ] 19. 🟡 Add a typing indicator animation when Reachy is processing a response (CSS + JS)
- [ ] 20. 🔴 Add a real-time vitals mini-dashboard — heart rate, SpO2, temperature in gauge widgets (HTML + JS + CSS)
- [ ] 21. 🔴 Add a daily timeline showing all events (alerts, meds, conversations) on a horizontal bar (JS + CSS)
- [ ] 22. 🔴 Add drag-and-drop reordering of dashboard cards so caregivers can customize layout (JS)
- [ ] 23. 🔴 Add a "night mode" that dims the screen and uses larger fonts for overnight shifts (CSS + JS)

## 🟦 patients.html (15 tasks)

- [x] 24. 🟢 Add alternating row colors to the patient table — every other row slightly different (CSS)
- [x] 25. 🟢 Style the mood badges with emoji instead of just text (JS)
- [ ] 26. 🟢 Add a patient avatar circle with their initials when no photo exists (HTML + CSS + JS)
- [x] 27. 🟡 Add a "sort by" dropdown — sort by name, room, mood, or last active (HTML + JS)
- [x] 28. 🟡 Show a confirmation toast notification after adding a patient instead of just reloading (JS + CSS)
- [x] 29. 🟡 Add a patient count badge in the nav link, like "Patients (5)" (JS)
- [x] 30. 🟡 Add a search/filter bar that filters patients by name or room number as you type (HTML + JS)
- [x] 31. 🟡 Add a patient detail slide-out panel that shows full info when you click a row (HTML + JS + CSS)
- [ ] 32. 🔴 Add inline editing — click a patient's room or conditions to edit it directly in the table (JS)
- [ ] 33. 🔴 Add a "print patient summary" button that opens a print-friendly view (JS + CSS)
- [ ] 34. 🔴 Add a patient card view toggle — switch between table and card grid layout (HTML + JS + CSS)
- [ ] 35. 🔴 Add patient photo upload with preview (HTML + JS + Python)
- [ ] 36. 🔴 Add a patient timeline showing their mood, meds, and conversations over the past 24h (JS + CSS)
- [ ] 37. 🔴 Add patient tags/labels (e.g. "fall risk", "diabetic", "new") with color coding (HTML + JS + CSS)
- [ ] 38. 🔴 Add a patient comparison view — select 2 patients and see their stats side by side (JS + CSS)

## 🟦 schedule.html (10 tasks)

- [x] 39. 🟢 Add color coding to the timeline dots — green for delivered, blue for upcoming, gray for future (CSS)
- [x] 40. 🟢 Style the quick schedule buttons with more spacing and a subtle border (CSS)
- [ ] 41. 🟡 Add a "next up" banner at the top showing the next scheduled message and countdown (JS + CSS)
- [ ] 42. 🟡 Add drag-to-reorder on the schedule table rows (JS)
- [ ] 43. 🟡 Show a preview of what Reachy will say when you hover over a scheduled message (CSS tooltip)
- [ ] 44. 🟡 Add a "duplicate schedule" button that copies an existing schedule entry (JS)
- [ ] 45. 🔴 Add a weekly calendar grid view as an alternative to the timeline (HTML + JS + CSS)
- [ ] 46. 🔴 Add recurring schedule patterns — "every Monday and Wednesday" not just daily/weekdays (HTML + JS + Python)
- [ ] 47. 🔴 Add a schedule conflict detector — warn if two messages overlap within 5 minutes (JS)
- [ ] 48. 🔴 Add schedule templates — "Morning Routine", "Evening Wind-down", "Med Reminders" (HTML + JS)

## 🟦 reports.html (10 tasks)

- [x] 49. 🟢 Add loading spinners while the charts are fetching data (CSS)
- [x] 50. 🟢 Style the report items with a left color border based on mood (CSS + JS)
- [ ] 51. 🟡 Add a date range picker that filters the report data (HTML + JS)
- [ ] 52. 🟡 Add a "print report" button that opens a clean print view (JS + CSS)
- [ ] 53. 🟡 Animate the chart bars so they grow from 0 to their value on load (CSS transitions)
- [ ] 54. 🟡 Add a "compare periods" toggle — this week vs last week side by side (JS)
- [ ] 55. 🔴 Add a trend arrow next to each vital showing if it's going up or down compared to yesterday (JS + Python)
- [ ] 56. 🔴 Add a heatmap showing conversation frequency by hour of day and day of week (JS + CSS)
- [ ] 57. 🔴 Add an AI-generated summary paragraph at the top using GPT to describe the week (JS + Python)
- [ ] 58. 🔴 Add PDF export for the full report with charts rendered as images (JS + Python)

## 🟦 medications.html (10 tasks)

- [ ] 59. 🟢 Add a color indicator — green dot for taken, red for missed, yellow for upcoming (CSS)
- [ ] 60. 🟢 Add a "next dose" countdown timer for each medication (JS)
- [ ] 61. 🟡 Add a medication adherence percentage bar for each med (JS + CSS)
- [ ] 62. 🟡 Add a "log dose" button that records when a medication was taken with timestamp (HTML + JS)
- [ ] 63. 🟡 Add medication interaction warnings — flag if two meds shouldn't be taken together (JS)
- [ ] 64. 🟡 Add a medication history timeline showing taken/missed over the past 7 days (JS + CSS)
- [ ] 65. 🔴 Add medication refill tracking — show days until refill needed based on doses remaining (JS + Python)
- [ ] 66. 🔴 Add a medication schedule calendar showing all meds on a weekly grid (HTML + JS + CSS)
- [ ] 67. 🔴 Add barcode/QR scanning to quickly log a medication (JS — camera API)
- [ ] 68. 🔴 Add medication photo upload so caregivers can identify pills visually (HTML + JS + Python)

## 🟦 facilities.html (8 tasks)

- [x] 69. 🟢 Add a hover effect on facility cards — slight scale up and shadow (CSS)
- [x] 70. 🟢 Make the address a clickable Google Maps link (JS)
- [ ] 71. 🟡 Add a patient count per facility by cross-referencing the patients API (JS)
- [ ] 72. 🟡 Add an "edit facility" modal that pre-fills with existing data (HTML + JS)
- [ ] 73. 🟡 Add facility status indicators — green for active, yellow for maintenance, red for issues (CSS + JS)
- [ ] 74. 🔴 Add a simple map view using an embedded iframe from OpenStreetMap (HTML + JS)
- [ ] 75. 🔴 Add facility capacity tracking — show occupied vs total beds (JS + CSS)
- [ ] 76. 🔴 Add a facility dashboard showing aggregate stats for all patients at that location (JS + Python)

## 🟦 family.html (10 tasks)

- [x] 77. 🟢 Add quick message buttons like "I love you", "See you soon", "Thinking of you" (HTML + JS)
- [x] 78. 🟢 Add emoji reactions to the mood display — bigger emoji, more color (CSS)
- [x] 79. 🟡 Add relative timestamps to messages — "sent 3 hours ago" (JS)
- [x] 80. 🟡 Add a character counter on the message textarea showing remaining chars (JS)
- [ ] 81. 🟡 Add a "read receipt" indicator on messages — show if Reachy delivered it (JS + CSS)
- [ ] 82. 🟡 Add a "schedule visit" button that creates a calendar entry (HTML + JS)
- [ ] 83. 🔴 Add a photo/image upload that sends as a family message (HTML + JS + Python)
- [ ] 84. 🔴 Add a video call button that opens a WebRTC connection to the robot's camera (JS + Python)
- [ ] 85. 🔴 Add a family activity feed showing what the patient did today (conversations, exercises, moods) (JS)
- [ ] 86. 🔴 Add a "memory book" section where family can upload photos with captions for reminiscence (HTML + JS + Python)

## 🟦 history.html (8 tasks)

- [ ] 87. 🟢 Add alternating background colors to mood history rows (CSS)
- [x] 88. 🟢 Add emoji next to each mood entry — 😊 for joy, 😢 for sadness, etc. (JS)
- [ ] 89. 🟡 Add a date filter — show history for today, this week, this month, or custom range (HTML + JS)
- [ ] 90. 🟡 Add a mood distribution pie chart using CSS-only (no library) (HTML + CSS + JS)
- [ ] 91. 🟡 Add a "mood streak" counter — how many consecutive happy days (JS)
- [x] 92. 🔴 Add a conversation replay — click a history entry to see the full conversation from that session (JS + Python)
- [ ] 93. 🔴 Add a mood prediction indicator — "based on patterns, tomorrow might be a tough day" (JS + Python)
- [ ] 94. 🔴 Add export to CSV for the mood history data (JS)

## 🟦 settings.html (10 tasks)

- [x] 95. 🟢 Add a version number and build date at the bottom of the page (HTML)
- [ ] 96. 🟡 Build the user management table — list users from `/api/users` with role badges (HTML + JS)
- [ ] 97. 🟡 Add a password change form using the existing `/api/change-password` endpoint (HTML + JS)
- [ ] 98. 🟡 Add a dark/light theme toggle that saves to localStorage and swaps CSS variables (JS + CSS)
- [ ] 99. 🟡 Add notification preferences — choose which alert types trigger sounds/push (HTML + JS)
- [ ] 100. 🔴 Add an "Add User" modal with username, password, role, and name fields (HTML + JS)
- [ ] 101. 🔴 Add a data backup/restore feature — export all settings as JSON, import from file (JS + Python)
- [ ] 102. 🔴 Add an audit log viewer showing who changed what and when (HTML + JS + Python)
- [ ] 103. 🔴 Add robot configuration panel — set voice, language, personality from the dashboard (HTML + JS + Python)
- [ ] 104. 🔴 Add a system health monitor — show Supabase connection, robot status, API latency (JS + Python)

## 🟦 login.html (6 tasks)

- [x] 105. 🟢 Add a fade-in animation on the login box (CSS)
- [x] 106. 🟢 Add a show/hide password toggle eye icon (HTML + JS)
- [x] 107. 🟡 Add "remember me" that saves the username to localStorage (HTML + JS)
- [x] 108. 🟡 Shake the login box when credentials are wrong instead of just showing text (CSS + JS)
- [ ] 109. 🟡 Add a loading spinner on the login button while authenticating (JS + CSS)
- [ ] 110. 🔴 Add two-factor authentication with a TOTP code input (HTML + JS + Python)

## 🟦 _base.html / global (12 tasks)

- [ ] 111. 🟡 Add a notification bell icon in the nav that shows unread alert count as a red badge (HTML + JS + CSS)
- [ ] 112. 🟡 Make the nav responsive — hamburger menu on mobile (CSS + JS)
- [ ] 113. 🟡 Add breadcrumbs below the nav showing current page path (HTML + CSS + JS)
- [ ] 114. 🟡 Add a global toast notification system — success/error/info toasts that auto-dismiss (JS + CSS)
- [ ] 115. 🟡 Add a "back to top" floating button that appears when you scroll down (HTML + CSS + JS)
- [ ] 116. 🔴 Add keyboard shortcuts — press "?" to show a help overlay with all shortcuts (JS + CSS)
- [ ] 117. 🔴 Add a global command palette (Cmd+K) that lets you search and jump to any page (JS + CSS)
- [ ] 118. 🔴 Add a sidebar layout option as an alternative to the top nav (HTML + CSS + JS)
- [ ] 119. 🔴 Add page transition animations when navigating between pages (CSS + JS)
- [ ] 120. 🔴 Add offline support — cache pages and show cached data when network is down (JS — Service Worker)
- [ ] 121. 🔴 Add a global search that searches across patients, alerts, conversations, and meds (JS + Python)
- [ ] 122. 🔴 Add multi-language support for all dynamic content (not just labels) using the i18n system (JS + Python)

## 🟦 camera.html (6 tasks)

- [x] 123. 🟢 Add a "camera offline" placeholder image instead of a broken frame (HTML + CSS)
- [ ] 124. 🟡 Add a snapshot button that captures the current frame and saves it (JS)
- [x] 125. 🟡 Add a fullscreen toggle for the camera feed (JS)
- [ ] 126. 🟡 Add a timestamp overlay on the camera feed showing current date/time (CSS + JS)
- [ ] 127. 🔴 Add motion detection indicators — highlight when movement is detected (JS)
- [ ] 128. 🔴 Add a recording button that saves a clip of the camera feed (JS + Python)

## 🟦 Python backend — app.py / db.py (20 tasks)

- [ ] 129. 🟡 Add a `/api/patients/<id>` GET endpoint that returns a single patient with their notes and vitals (Python)
- [ ] 130. 🟡 Add a `/api/patients/<id>` PUT endpoint for updating patient info (Python)
- [ ] 131. 🟡 Add a `/api/dashboard/summary` endpoint that returns all dashboard data in one call (Python)
- [ ] 132. 🟡 Add rate limiting to the API endpoints to prevent abuse (Python)
- [ ] 133. 🟡 Add request logging middleware that logs all API calls with timing (Python)
- [ ] 134. 🟡 Add input validation on all POST endpoints — reject missing/invalid fields (Python)
- [ ] 135. 🔴 Add a `/api/export/pdf` endpoint that generates a PDF report using reportlab (Python)
- [ ] 136. 🔴 Add WebSocket support using flask-socketio for true real-time updates instead of SSE (Python + JS)
- [ ] 137. 🔴 Add a `/api/ai/summary` endpoint that uses GPT to generate a natural language patient summary (Python)
- [ ] 138. 🔴 Add a `/api/ai/recommendations` endpoint that suggests care actions based on patient data (Python)
- [ ] 139. 🔴 Add database migrations so schema changes don't require wiping data (Python)
- [ ] 140. 🔴 Add a `/api/alerts/escalate` endpoint that sends critical alerts via email/SMS (Python)
- [ ] 141. 🔴 Add a `/api/patients/<id>/timeline` endpoint returning all events for a patient chronologically (Python)
- [ ] 142. 🔴 Add role-based access control — nurses see different things than admins (Python)
- [ ] 143. 🔴 Add a `/api/shifts` endpoint for managing caregiver shift schedules (Python)
- [ ] 144. 🔴 Add a `/api/incidents` endpoint for logging and tracking care incidents (Python)
- [ ] 145. 🔴 Add automated daily report generation that runs at midnight via a background thread (Python)
- [ ] 146. 🔴 Add a `/api/vitals/trends` endpoint that returns vitals data formatted for charting (Python)
- [ ] 147. 🔴 Add a `/api/search` global search endpoint that searches across all data types (Python)
- [ ] 148. 🔴 Add API documentation page at `/api/docs` using auto-generated OpenAPI spec (Python)

## 🟦 New pages to build from scratch (12 tasks)

- [ ] 149. 🔴 Build a **Vitals Dashboard** page — real-time heart rate, SpO2, BP charts with alert thresholds (HTML + JS + CSS)
- [ ] 150. 🔴 Build a **Shift Handoff** page — outgoing caregiver writes notes, incoming caregiver acknowledges (HTML + JS + Python)
- [ ] 151. 🔴 Build a **Incident Report** page — form to log falls, medication errors, behavioral incidents (HTML + JS + Python)
- [ ] 152. 🔴 Build a **Care Plan** page — editable care goals, interventions, and progress tracking (HTML + JS + Python)
- [ ] 153. 🔴 Build a **Communication Center** page — unified inbox for family messages, caregiver notes, robot alerts (HTML + JS)
- [ ] 154. 🔴 Build a **Robot Control** page — send commands to Reachy, change voice/personality, trigger actions (HTML + JS + Python)
- [ ] 155. 🔴 Build a **Analytics** page — advanced charts, trends, predictions, exportable dashboards (HTML + JS + Python)
- [ ] 156. 🔴 Build a **Knowledge Base** page — view the patient's knowledge graph visually as a network diagram (HTML + JS)
- [ ] 157. 🔴 Build a **Memory Browser** page — search and browse all of Reachy's memories about a patient (HTML + JS + Python)
- [ ] 158. 🔴 Build a **Conversation Replay** page — play back past conversations with timestamps and emotions (HTML + JS + Python)
- [ ] 159. 🔴 Build a **Alerts Management** page — configure alert rules, escalation paths, notification preferences (HTML + JS + Python)
- [ ] 160. 🔴 Build a **Multi-Patient Dashboard** — overview of all patients at once with status cards (HTML + JS + CSS)

---

**Total: 160 tasks**
- 🟢 Easy: 28 tasks
- 🟡 Medium: 62 tasks  
- 🔴 Hard: 70 tasks

Pick a number and let's build it together!
