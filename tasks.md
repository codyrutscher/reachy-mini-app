# Reachy Care Dashboard — Practice Tasks

Difficulty: 🟢 easy | 🟡 medium | 🔴 hard
Skills in parentheses. Check off as you complete them.

---

## activity.html

- [ ] 1. 🟢 Add `display: flex` and `gap: 10px` to `.activity-row` so icon and text sit side by side (CSS)
- [ ] 2. 🟢 Add a row count next to the subtitle that updates when you filter, like "Showing 12 events" (JS)
- [ ] 3. 🟡 Color-code the left border of each row by action type — red for alerts, green for meds, blue for messages (JS + CSS)
- [ ] 4. 🟡 Add a search input that filters rows by text content in real-time as you type (HTML + JS)
- [ ] 5. 🟡 Write a `timeAgo()` function that shows "2 hours ago" instead of raw timestamps (JS)
- [ ] 6. 🟡 Add a "Clear Filters" button that resets the dropdown and search box (HTML + JS)
- [ ] 7. 🔴 Add summary stat cards above the list — total events, alerts count, med events, patient interactions (HTML + JS)
- [ ] 8. 🔴 Group activities by date with sticky date headers like "Today", "Yesterday", "March 13" (JS + CSS)

## dashboard.html

- [ ] 9. 🟢 Change the camera "offline" message to something more helpful with a retry button (HTML + CSS)
- [ ] 10. 🟢 Add a pulsing animation to the alert stat cards when count is > 0 (CSS)
- [ ] 11. 🟡 Add a "last updated" timestamp that shows when data was last refreshed (JS)
- [ ] 12. 🟡 Make the conversation bubbles show relative time ("2m ago") instead of raw timestamps (JS)
- [ ] 13. 🟡 Add a notification sound toggle button in the header (HTML + JS)
- [ ] 14. 🔴 Add a mini mood chart in the patient bar showing the last 10 mood readings as colored dots (JS + CSS)
- [ ] 15. 🔴 Make the quick message buttons customizable — save custom ones to localStorage (JS)

## patients.html

- [ ] 16. 🟢 Add alternating row colors to the patient table — every other row slightly different (CSS)
- [ ] 17. 🟢 Style the mood badges with emoji instead of just text (JS)
- [ ] 18. 🟡 Add a "sort by" dropdown — sort by name, room, mood, or last active (HTML + JS)
- [ ] 19. 🟡 Show a confirmation toast notification after adding a patient instead of just reloading (JS + CSS)
- [ ] 20. 🟡 Add a patient count badge in the nav link, like "Patients (5)" (JS)
- [ ] 21. 🔴 Add inline editing — click a patient's room or conditions to edit it directly in the table (JS)
- [ ] 22. 🔴 Add a "print patient summary" button in the detail panel that opens a print-friendly view (JS + CSS)

## schedule.html

- [ ] 23. 🟢 Add color coding to the timeline dots — green for delivered, blue for upcoming, gray for future (CSS)
- [ ] 24. 🟢 Style the quick schedule buttons with more spacing and a subtle border (CSS)
- [ ] 25. 🟡 Add a "next up" banner at the top showing the next scheduled message and countdown (JS + CSS)
- [ ] 26. 🟡 Add drag-to-reorder on the schedule table rows (JS)
- [ ] 27. 🟡 Show a preview of what Reachy will say when you hover over a scheduled message (CSS tooltip)
- [ ] 28. 🔴 Add a weekly calendar grid view as an alternative to the timeline (HTML + JS + CSS)
- [ ] 29. 🔴 Add recurring schedule patterns — "every Monday and Wednesday" not just daily/weekdays (HTML + JS + Python)

## reports.html

- [ ] 30. 🟢 Add loading spinners while the charts are fetching data (CSS)
- [ ] 31. 🟢 Style the report items with a left color border based on mood (CSS + JS)
- [ ] 32. 🟡 Add a date range picker that filters the report data (HTML + JS)
- [ ] 33. 🟡 Add a "print report" button that opens a clean print view (JS + CSS)
- [ ] 34. 🟡 Animate the chart bars so they grow from 0 to their value on load (CSS transitions)
- [ ] 35. 🔴 Add a trend arrow next to each vital showing if it's going up or down compared to yesterday (JS + Python)

## facilities.html

- [ ] 36. 🟢 Add a hover effect on facility cards — slight scale up and shadow (CSS)
- [ ] 37. 🟢 Make the address a clickable Google Maps link (JS)
- [ ] 38. 🟡 Add a patient count per facility by cross-referencing the patients API (JS)
- [ ] 39. 🟡 Add an "edit facility" modal that pre-fills with existing data (HTML + JS)
- [ ] 40. 🔴 Add a simple map view using an embedded iframe from OpenStreetMap (HTML + JS)

## family.html

- [ ] 41. 🟢 Add quick message buttons like "I love you", "See you soon", "Thinking of you" (HTML + JS)
- [ ] 42. 🟢 Add emoji reactions to the mood display — bigger emoji, more color (CSS)
- [ ] 43. 🟡 Add relative timestamps to messages — "sent 3 hours ago" (JS)
- [ ] 44. 🟡 Add a character counter on the message textarea showing remaining chars (JS)
- [ ] 45. 🟡 Add a "read receipt" indicator on messages — show if Reachy delivered it (JS + CSS)
- [ ] 46. 🔴 Add a photo/image upload that sends as a family message (HTML + JS + Python)

## settings.html

- [ ] 47. 🟢 Add a version number and build date at the bottom of the page (HTML)
- [ ] 48. 🟡 Build the user management table — list users from `/api/users` with role badges (HTML + JS)
- [ ] 49. 🟡 Add a password change form using the existing `/api/change-password` endpoint (HTML + JS)
- [ ] 50. 🟡 Add a dark/light theme toggle that saves to localStorage and swaps CSS variables (JS + CSS)
- [ ] 51. 🔴 Add an "Add User" modal with username, password, role, and name fields (HTML + JS)

## login.html

- [ ] 52. 🟢 Add a fade-in animation on the login box (CSS)
- [ ] 53. 🟢 Add a show/hide password toggle eye icon (HTML + JS)
- [ ] 54. 🟡 Add "remember me" that saves the username to localStorage (HTML + JS)
- [ ] 55. 🟡 Shake the login box when credentials are wrong instead of just showing text (CSS + JS)

## _base.html (global)

- [ ] 56. 🟡 Add a notification bell icon in the nav that shows unread alert count as a red badge (HTML + JS + CSS)
- [ ] 57. 🟡 Make the nav responsive — hamburger menu on mobile (CSS + JS)
- [ ] 58. 🔴 Add keyboard shortcuts — press "?" to show a help overlay with all shortcuts (JS + CSS)
- [ ] 59. 🔴 Add a global command palette (Cmd+K) that lets you search and jump to any page (JS + CSS)

## Python backend (app.py / db.py)

- [ ] 60. 🟡 Add a `/api/activity/stats` endpoint that returns counts grouped by action type (Python)
- [ ] 61. 🟡 Add a `/api/patients/<id>` GET endpoint that returns a single patient with their notes and vitals (Python)
- [ ] 62. 🔴 Add a `/api/export/pdf` endpoint that generates a PDF report using reportlab (Python)
- [ ] 63. 🔴 Add WebSocket support using flask-socketio for true real-time updates instead of SSE (Python + JS)
