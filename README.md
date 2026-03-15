# The Smart Geography & History Teacher
### Name: Mamdoh Amaryh
### GitHub Username: [mamdiam1-bot-GitHub]
### edX Username: [mamdiam1-edX]
### City: [Ibtin, Haifa ]
### Country: Israel
### Date: March 12, 2026

#### My Video : [https://youtu.be/Al-xLPThbsA?si=K_W180YCRjbTTjun]

#### Description:
The "Smart Geography & History Teacher" is an interactive web-based educational platform...

## Project Overview
The "Smart Geography & History Teacher" is an interactive web-based educational platform designed to provide students and lifelong learners with an engaging way to explore historical events and geographical phenomena. Built as a final project for CS50x, this application leverages the power of Large Language Models (LLMs) to act as a specialized pedagogical assistant.

The project solves a common problem in digital learning: the lack of immediate, conversational feedback when students have specific questions about complex topics like the Urban Heat Island effect or historical imperial expansions.

## Features
- **WhatsApp-Inspired UI:** A familiar, user-friendly interface that reduces the learning curve for students.
- **Multimodal Learning:** Users can upload images (maps, landscapes, historical documents) for the AI to analyze.
- **Database Persistence:** Every interaction is stored in a SQLite database, allowing users to track their learning progress over time.
- **Dynamic History:** A dedicated history page that retrieves and displays past conversations using SQL queries.
- **Text-to-Speech:** Integrated audio feedback to assist with accessibility and pronunciation.
- **PDF Export:** Allows users to download their learning sessions for offline study.

## Technical Implementation
### Backend (Python & Flask)
The backend is powered by **Flask**. It manages the routing between the chat interface and the history database. I implemented a robust integration with the **Gemini 1.5 Flash / Gemini 3** API, enabling the application to process both text and image data.

### Database (SQL)
For data persistence, I used **SQLite**. This was a crucial design choice to meet the requirements of CS50x. I created a database named `project.db` with a table `chats` that stores the user's message, the bot's response, and the language of the interaction. This allows the application to be "stateful," meaning it remembers the user's history even after the server restarts.

### Frontend (JavaScript, HTML, CSS)
The frontend uses **JavaScript** to handle asynchronous requests (AJAX/Fetch), ensuring the chat feels fluid without page reloads. I used **CSS Flexbox** to mimic a modern mobile messaging app. The **jsPDF** library was integrated to handle client-side PDF generation.

## File Structure
- `app.py`: The main controller of the application. Handles Flask routes, SQL connections, and API calls.
- `project.db`: The SQLite database file storing chat history.
- `templates/index.html`: The main chat interface, including JS for UI updates.
- `templates/history.html`: The history view that renders data retrieved via SQL.
- `static/`: Contains images and CSS files for UI styling.
- `requirements.txt`: Lists the necessary Python libraries (Flask, requests, etc.).

## Design Choices
I chose a WhatsApp-like interface because it creates a sense of "informal learning," which has been shown to reduce student anxiety. Furthermore, I decided to use the `gemini-3-flash-preview` model for its superior speed and bilingual capabilities, which are essential for an educational tool targeting diverse subjects.

## Acknowledgments
This project was developed as part of Harvard's CS50x 2026. I utilized Google's Gemini AI as a development assistant and pedagogical core, as permitted by the course's academic honesty policy for the final project.
