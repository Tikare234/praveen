# rag_setup.py (No functional changes, just confirming it's ready for Docker build)

import os
import shutil
import json
import requests
from bs4 import BeautifulSoup

# LangChain components
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.docstore.document import Document

from dotenv import load_dotenv

load_dotenv()

# Target URLs to scrape for building RAG knowledge base
TARGET_URLS = [
    "https://www.stevenscreekchevy.com/service-parts-specials.html",
    "https://www.stevenscreekchevy.com/ev-incentives",
    "https://www.stevenscreekchevy.com/searchnew.aspx",  # Corrected typo
    "https://www.stevenscreekchevy.com/newspecials.html",
    "https://www.stevenscreekchevy.com/service",
]

# Path for FAISS index (inside Docker image working directory)
FAISS_INDEX_PATH = "./faiss_index"


def scrape_page(url: str) -> str:
    """Fetch and return cleaned text from a webpage body."""
    try:
        print(f"  Fetching {url}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.body.get_text(separator=" ", strip=True)
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching {url}: {e}")
        return ""
    except AttributeError:
        print(f"  Error: Could not find <body> tag in {url} (malformed HTML?).")
        return ""


def setup_rag_knowledge_base():
    """
    Scrape target URLs, split content into chunks, embed with OpenAI,
    and save a FAISS index. Always overwrites for Docker builds.
    """
    print("--- Starting RAG Knowledge Base Setup for Docker Build ---")

    # Initialize embeddings
    print("Initializing OpenAI Embeddings...")
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not found in environment. Embeddings might fail.")
        # Note: For Docker build, pass via --build-arg or environment variable.

    embeddings = OpenAIEmbeddings()

    # Clear existing FAISS index if found
    if os.path.exists(FAISS_INDEX_PATH) and os.path.isdir(FAISS_INDEX_PATH):
        print(f"Existing FAISS index found at {FAISS_INDEX_PATH}. Deleting to re-index...")
        try:
            shutil.rmtree(FAISS_INDEX_PATH)
            print("Existing index deleted.")
        except OSError as e:
            print(f"Error deleting existing index: {e}")
            return None
    else:
        print("No existing FAISS index found. Creating new index...")

    all_texts = []

    # Scrape and chunk all target URLs
    for url in TARGET_URLS:
        print(f"\nProcessing URL: {url}")
        full_text = scrape_page(url)

        if not full_text:
            print(f"  No text scraped from {url}. Skipping this URL.")
            continue

        print(f"  Scraped {len(full_text)} characters from {url}.")
        print("  Chunking the scraped text...")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            add_start_index=True,
        )

        docs_from_page = text_splitter.split_documents(
            [Document(page_content=full_text, metadata={"source": url})]
        )
        all_texts.extend(docs_from_page)
        print(f"  Added {len(docs_from_page)} chunks from {url}.")

    if not all_texts:
        print("No content was successfully scraped and chunked from any URL. Cannot create FAISS index.")
        return None

    print(f"\nTotal chunks created from all URLs: {len(all_texts)}")
    print("Storing embeddings in FAISS...")

    os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
    vectordb = FAISS.from_documents(documents=all_texts, embedding=embeddings)

    print("FAISS vector store created.")
    print(f"Saving FAISS index to {FAISS_INDEX_PATH}...")
    vectordb.save_local(FAISS_INDEX_PATH)

    print("FAISS index saved.")
    print("--- RAG Knowledge Base Setup Complete ---")

    return vectordb


if __name__ == "__main__":
    setup_rag_knowledge_base()
