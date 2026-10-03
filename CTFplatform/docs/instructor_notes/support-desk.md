# Instructor Notes — Lab 4

## Objective
Teach beginner-level reflected XSS with a story-driven investigation.

## Architecture
- Flask backend
- Dark TechCorp training UI
- Left-side mission/quiz workflow
- Right-side virtual-lab workspace
- Embedded Support Desk browser
- Session-based progress
- Final flag after all five missions

## Vulnerability
`/lab?message=...` intentionally reflects the `message` parameter into the HTML
using Jinja's `|safe` filter.

This is deliberately vulnerable and must stay isolated to the training lab.

## Expected concept
User input -> HTTP request -> reflected HTTP response -> browser -> execution

## Test
Open the Support Desk from the lab and submit the harmless payload supplied
in the interface. The browser should show an alert.

## Reset
Use Reset Lab.
