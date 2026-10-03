# Instructor Notes — Lab 5

## Objective
Teach beginner-level phishing and social-engineering awareness with a
story-driven investigation. This lab is intentionally less technical than
Lab 4 — there is no code vulnerability to exploit. The "vulnerability" is
a lack of awareness, and the learner practices spotting it.

## Architecture
- Flask backend
- Dark TechCorp training UI (shared with Lab 4)
- Left-side mission/quiz workflow
- Right-side virtual-lab workspace
- Embedded, fully simulated Mail Center (no real email sending/receiving)
- Session-based progress
- Final flag after all five missions

## Content
`/lab` renders a static mail-client mockup with five fictional messages
(three legitimate, two phishing) plus:
- A link inspector that shows the mismatch between displayed text and the
  real destination when the learner hovers/clicks the training link.
- A five-message "human firewall" classification exercise (self-checking,
  not tied to mission scoring).
- A static attack-chain diagram (Attacker -> Fake Message -> Victim ->
  Fake Login Page -> Credential Theft).
- A safe-actions checklist emphasizing reporting and MFA.

None of this content contains a working phishing site, a real link, or any
credential-harvesting code. It is purely illustrative.

## Expected concept
Suspicious message -> human notices red flags -> verifies through a
trusted channel -> reports it -> account stays protected (ideally with MFA
as a backstop).

## Test
Open the Mail Center from the lab and read through each mission's
content, then answer the five knowledge-check quizzes in the sidebar.

## Reset
Use Reset Lab.
