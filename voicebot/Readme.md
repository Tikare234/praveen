---

# Audio RAG Assistant with OpenAI Function Calling

This project demonstrates an advanced Retrieval Augmented Generation (RAG) assistant that allows users to interact via voice. It can answer questions based on a custom knowledge base and perform actions like booking appointments through a conversational interface. The assistant transcribes audio queries, processes them using a powerful LLM agent, and responds with synthesized audio.

## Features

- **Voice Interaction:** Seamless natural language voice input and audio output.
- **Custom Knowledge Base:** Answers questions based on dynamically scraped web content, stored in a FAISS vector database.
- **Conversational Agent:** Leverages LangChain's agent framework with OpenAI Function Calling for:
  - Intelligent multi-turn dialogues.
  - Contextual understanding and information extraction.
  - **Automated Appointment Booking:** Integrates with an internal calendar system to check agent availability and book appointments.
  - **Smart Agent Selection:** Automatically finds and assigns an available sales or service agent if a specific name isn't provided.
- **Monolithic FastAPI Backend:** A single, robust FastAPI application orchestrates all AI, calendar, and audio processing logic.
- **Persistent Data:** Uses SQLite for persistent storage of calendar data (agents, appointments) and FAISS for the RAG knowledge base.
- **Pure Voicebot UI:** A simple HTML/JavaScript frontend designed for a voice-only interaction experience.

## Project Structure

```
your_project_folder/
├── main.py               # Main FastAPI application (orchestrates all logic)
├── rag_retriever.py      # Core RAG logic: LangChain Agent, Tools (booking, availability, info retrieval)
├── app_calendar.py       # Calendar business logic: SQLite DB setup, agent management, booking functions
├── rag_setup.py          # Script to scrape data and build/update the FAISS knowledge base
├── index.html            # Simple web UI for microphone input and audio output
├── .env                  # Environment variables for local development (e.g., OpenAI API Key)
├── faiss_index/          # Directory where the FAISS vector store is saved (created by rag_setup.py)
├── calendar.db           # SQLite database file for calendar data (created by main.py on startup)
└── requirements.txt      # Python dependencies
```

## Setup Instructions

### 1. Clone the Repository (or create files)

Create a project directory and place all the Python (`.py`) and HTML (`.html`) files inside it.

### 2. Create a Python Virtual Environment

It's highly recommended to use a virtual environment to manage dependencies.

```bash
# Navigate to your project directory
cd your_project_folder

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies

Install all required Python packages using the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 4. Set Up OpenAI API Key

You need an OpenAI API key for Whisper (STT), TTS, Embeddings, and the LLM (GPT-3.5-turbo).

**Create a `.env` file:**
In the root of your project directory, create a file named `.env` and add your API key:

```
# .env
OPENAI_API_KEY="sk-YOUR_ACTUAL_OPENAI_API_KEY"
```

_(Replace `sk-YOUR_ACTUAL_OPENAI_API_KEY` with your actual key)_

**Important:** Do NOT commit your `.env` file to version control. Add `.env` to your `.gitignore`.

## Running the Application (Local Development)

You will need to run three separate components concurrently. Open **three separate terminal/command prompt windows**, activate your virtual environment in each, and navigate to your project directory.

### 1. Build/Update the RAG Knowledge Base

This script scrapes data and creates/updates the FAISS vector index. You only need to run this once, or whenever you want to update the knowledge base.

```bash
# In Terminal 1
.venv\Scripts\activate
python rag_setup.py
```

This will scrape the specified URLs, chunk the text, create embeddings, and save the FAISS index to the `./faiss_index` folder. Wait for it to complete.

### 2. Start the FastAPI Backend

This is your main application that now includes all the calendar logic.

```bash
# In Terminal 2
.venv\Scripts\activate
uvicorn main:app --port 8000 --reload
```

You should see output indicating it's running on `http://127.0.0.1:8000`. This terminal will also show logs from the RAG agent and calendar functions. Keep this terminal window open.

### 3. Serve the Frontend UI

This serves your `index.html` file.

```bash
# In Terminal 3
.venv\Scripts\activate
python -m http.server 8001
```

You should see output like `Serving HTTP on :: port 8001`. Keep this terminal window open.

### 4. Access the Web UI

Once all backend components are running, open your web browser and go to:
**[http://localhost:8001/index.html](http://localhost:8001/index.html)**

## Demo and Usage

### Interacting with the Assistant

1.  **Grant Microphone Access:** When you open `index.html`, your browser will likely ask for permission to access your microphone. Grant it.
2.  **Start Recording:** Click the "Start Recording" button.
3.  **Speak Your Query:** Speak clearly into your microphone.
4.  **Stop Recording:** Click the "Stop Recording" button when you are done speaking.
5.  **Listen for Response:** The assistant will process your audio, transcribe it, query the RAG agent, and respond with an audio message.

### Sample Conversation Flows

Here are examples of how you can interact with the assistant, demonstrating both information retrieval and appointment booking:

**Scenario 1: General Information Retrieval**

- **User:** "What are the current oil change specials?"
- **Bot:** (Audio response detailing oil change specials from the scraped data)

- **User:** "Tell me about EV incentives."
- **Bot:** (Audio response summarizing EV incentives from the scraped data)

**Scenario 2: Multi-Turn Appointment Booking (Automated Agent Selection)**

- **User:** "I want to book an appointment."
- **Bot:** "Okay, I can help you with that. What type of agent are you looking for? Sales or Service?"

- **User:** "A sales agent."
- **Bot:** "Great. And what date would you like to book the appointment for?"

- **User:** "Tomorrow."
- **Bot:** "Okay, for tomorrow. And what time would you prefer for the appointment?"

- **User:** "Around 10 AM."
- **Bot:** "Okay, I found Sarah Johnson available for a sales appointment tomorrow at 9:00 AM. Does that time work for you?" _(Note: The agent found the first available slot if 10 AM was busy, and proposes it.)_

- **User:** "Yes, that works."
- **Bot:** "Great. What is your name and contact information (email or phone number)?"

- **User:** "My name is John Doe and my email is john.doe@example.com."
- **Bot:** "Thank you, John Doe. Your appointment with Sarah Johnson for tomorrow at 9:00 AM has been successfully booked. Your booking ID is: BOOK-Sarah Johnson-YYYY-MM-DD-09:00-10:00-..."

**Scenario 3: Direct Appointment Booking (if all info provided)**

- **User:** "Book an appointment with Mike Rodriguez for a test drive on September 15th at 2 PM. My name is Jane Smith and my contact is jane@example.com."
- **Bot:** "Thank you, Jane Smith. Your appointment with Mike Rodriguez for a test drive on September 15th at 2:00 PM has been successfully booked. Your booking ID is: BOOK-Mike Rodriguez-YYYY-MM-DD-14:00-15:00-..."

## Troubleshooting

- **"Failed to fetch" / CORS Errors:** Ensure your `main.py` has the `CORSMiddleware` configured correctly and that your `index.html` is served from an allowed origin (e.g., `http://localhost:8001`). Restart `uvicorn main:app` after changes.
- **API Key Errors:** Verify your `OPENAI_API_KEY` is correctly set in your `.env` file and that you have sufficient OpenAI credits.
- **FAISS Index Not Found:** Run `python rag_setup.py` to create the `./faiss_index` folder.
- **"Server not fully initialized" (503 error):** Check the terminal running `uvicorn main:app` for detailed error messages during startup.
- **No Audio Playback:** Check your browser's media settings, ensure volume is up, and inspect the network tab (F12 -> Console/Network) to see if an audio file was successfully returned from the `/query_audio/` endpoint.
- **Agent Not Responding / Unexpected Responses:**
  - Check the terminal running `uvicorn main:app` for the agent's `verbose=True` output. This shows the agent's thought process and tool calls.
  - Ensure your queries are clear and provide enough information for the agent to act.
