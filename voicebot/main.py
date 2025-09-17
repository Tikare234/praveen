# main.py (MODIFIED to return text in headers)

import os
import io
import shutil
import tempfile
from typing import Annotated, Any, List, Union

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from rag_retriever import initialize_rag_pipeline, ask_rag
from langchain_core.messages import AIMessage, HumanMessage
from openai import OpenAI
from calendar_api import init_calendar_db

init_calendar_db()
# --- FastAPI App Initialization ---
app = FastAPI(
    title="Audio RAG Assistant",
    description="Receives audio query, transcribes, queries RAG, and returns audio answer.",
)

# --- CORS Configuration ---
PORT = int(os.getenv("PORT", 8000))
origins = [
    "http://localhost",
    f"http://localhost:{PORT}",
    "http://localhost:8001",  # For local frontend server
    "http://127.0.0.1",
    f"http://127.0.0.1:{PORT}",
    "http://127.0.0.1:8001",
    os.getenv("FRONTEND_URL", "*"),
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Allow all headers, including custom ones
)

# --- Global Instances ---
qa_pipeline: Any = None
openai_client: Any = None
chat_history: List[Union[AIMessage, HumanMessage]] = []  # In-memory chat history


# --- FastAPI Startup Event ---
@app.on_event("startup")
async def startup_event():
    global qa_pipeline, openai_client
    print("FastAPI app starting up...")

    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable not set.")
        print("Please set it before starting the FastAPI application.")
        return

    # Initialize OpenAI client
    try:
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception as e:
        print(f"ERROR: Failed to initialize OpenAI client: {e}")
        return

    # Initialize RAG pipeline
    try:
        import calendar_api  # Assuming this exists in the same directory

        qa_pipeline = initialize_rag_pipeline(
            get_all_agents_func=calendar_api.get_all_agents_func,
            get_agent_availability_func=calendar_api.get_agent_availability_func,
            book_appointment_func=calendar_api.book_appointment_func,
        )
        if qa_pipeline is None:
            print("ERROR: Failed to initialize RAG pipeline. Check rag_retriever.py logs for errors.")
            return
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during RAG pipeline initialization: {e}")
        return

    print("FastAPI app startup complete.")


# --- Health Check Endpoint ---
@app.get("/")
async def read_root():
    return {"message": "Audio RAG Assistant is running!"}


# --- Audio Query Endpoint ---
@app.post("/query_audio/")
async def query_audio_endpoint(
    audio_file: Annotated[UploadFile, File(description="Audio query in WAV, MP3, or M4A format")]
):
    global chat_history

    if qa_pipeline is None or openai_client is None:
        raise HTTPException(status_code=503, detail="Server not fully initialized.")

    print(f"Received audio file: {audio_file.filename} ({audio_file.content_type})")
    temp_audio_path = None

    # --- Audio Transcription ---
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{audio_file.filename}") as tmp:
            shutil.copyfileobj(audio_file.file, tmp)
            temp_audio_path = tmp.name

        print("Transcribing audio using OpenAI Whisper...")
        with open(temp_audio_path, "rb") as audio_file_for_whisper:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file_for_whisper,
            )
        query_text = transcript.text
        print(f"Transcription: '{query_text}'")

    except Exception as e:
        print(f"Error during audio transcription: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Audio transcription failed: {e}. Ensure audio format is supported and API key is valid.",
        )
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

    # --- Update Chat History ---
    chat_history.append(HumanMessage(content=query_text))

    # --- Query RAG ---
    print(f"Querying RAG Agent with: '{query_text}'")
    final_answer_text = await ask_rag(query_text, qa_pipeline, chat_history)

    print(f"Final Answer from RAG Agent: '{final_answer_text}'")

    if not final_answer_text:
        final_answer_text = "I'm sorry, I couldn't generate a response."

    chat_history.append(AIMessage(content=final_answer_text))
    chat_history = chat_history[-10:]  # Keep last 10 messages

    # --- Text-to-Speech Conversion ---
    print("Converting final answer to audio using OpenAI TTS...")
    try:
        tts_response = openai_client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=final_answer_text,
            response_format="mp3",
        )

        audio_stream = io.BytesIO()
        for chunk in tts_response.iter_bytes(chunk_size=4096):
            audio_stream.write(chunk)
        audio_stream.seek(0)

        # --- Custom headers with text content ---
        headers = {
            "X-User-Query-Text": query_text,
            "X-Bot-Answer-Text": final_answer_text,
        }
        return StreamingResponse(audio_stream, media_type="audio/mpeg")

    except Exception as e:
        print(f"Error during Text-to-Speech conversion: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Text-to-Speech conversion failed: {e}. Ensure API key is valid and text is not too long.",
        )
