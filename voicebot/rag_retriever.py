import os
import json
import re
import time
from typing import Dict, List, Any, Union, Callable
from datetime import datetime, timedelta
from prompt import SYSTEM_PROMPT
# LangChain components
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.llms import OpenAI
from langchain.chains import RetrievalQA

# For Function Calling / Agents
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage

from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "./faiss_index")

# --- Global variables to hold the passed functions ---
_get_all_agents_func: Callable = None
_get_agent_availability_func: Callable = None
_book_appointment_func: Callable = None


# --- Helper for Date Parsing ---
def parse_relative_date(date_str: str) -> str:
    today = datetime.now().date()
    date_str_lower = date_str.lower()

    if "today" in date_str_lower:
        return today.strftime("%Y-%m-%d")
    elif "tomorrow" in date_str_lower:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "day after tomorrow" in date_str_lower:
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")
    elif "next" in date_str_lower:
        days_of_week = [
            "monday", "tuesday", "wednesday",
            "thursday", "friday", "saturday", "sunday"
        ]
        for i, day in enumerate(days_of_week):
            if day in date_str_lower:
                current_day_of_week = today.weekday()
                days_until_next = (i - current_day_of_week + 7) % 7
                if days_until_next == 0:
                    days_until_next = 7
                return (today + timedelta(days=days_until_next)).strftime("%Y-%m-%d")

    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        try:
            return datetime.strptime(date_str, "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

    return date_str


# --- Tool Definitions ---
@tool
def get_all_agents() -> str:
    """
    Retrieves a list of all available sales and service agents.
    Returns a JSON string with agent types and names.
    """
    print("Retrieving all agents via internal function...")
    if _get_all_agents_func:
        return _get_all_agents_func()
    return "Error: Calendar function not initialized."


@tool
def get_agent_availability(agent_name: str, date: str) -> str:
    """
    Retrieves available time slots for a specific agent on a given date.
    The date should be in YYYY-MM-DD format.
    Returns a list of available slots or an error message.
    """
    parsed_date = parse_relative_date(date)
    if not re.match(r"\d{4}-\d{2}-\d{2}", parsed_date):
        return f"I need a valid date in YYYY-MM-DD format or a clear relative date like 'tomorrow' or 'next Monday' to check availability. You provided: {date}"

    print(f"Checking availability for {agent_name} on {parsed_date} via internal function...")
    if _get_agent_availability_func:
        return _get_agent_availability_func(agent_name=agent_name, date=parsed_date)
    return "Error: Calendar function not initialized."


@tool
def find_available_agent(agent_type: str, date: str, time: str = None) -> str:
    """
    Finds an available agent of a specific type (Sales or Service) for a given date and time.
    If a specific time is provided, it checks for that time. If not, it returns the first available slot.
    """
    parsed_date = parse_relative_date(date)
    if not re.match(r"\d{4}-\d{2}-\d{2}", parsed_date):
        return f"I need a valid date in YYYY-MM-DD format to find an available agent. You provided: {date}"

    print(f"Finding available {agent_type} agent for {parsed_date} at {time if time else 'any time'} via internal function...")
    try:
        # --- MODIFIED TOOL CALL ---
        all_agents_json = get_all_agents.func()  # Call the underlying function directly
        # --- END MODIFIED TOOL CALL ---
        all_agents_data = json.loads(all_agents_json)
        all_agents = all_agents_data.get(agent_type, [])

        if not all_agents:
            return f"No {agent_type} agents found."

        best_found_agent = None
        best_found_slot = None

        # First, try to find the exact requested time
        if time:
            for agent_name in all_agents:
                avail_json = get_agent_availability.func(agent_name=agent_name, date=parsed_date)
                avail_data = json.loads(avail_json)
                available_slots = avail_data.get("available_slots", [])
                if time in available_slots:
                    return f"Agent {agent_name} is available at {time} on {parsed_date}."

        # Otherwise, find first available slot
        for agent_name in all_agents:
            avail_json = get_agent_availability.func(agent_name=agent_name, date=parsed_date)
            avail_data = json.loads(avail_json)
            available_slots = avail_data.get("available_slots", [])

            if available_slots:
                best_found_agent = agent_name
                best_found_slot = available_slots[0]
                break

        if best_found_agent and best_found_slot:
            if time and time != best_found_slot:
                return f"Agent {best_found_agent} is not available at {time} on {parsed_date}, but is available at {best_found_slot}. Would you like to book at {best_found_slot} instead?"
            else:
                return f"Agent {best_found_agent} is available at {best_found_slot} on {parsed_date}."
        else:
            if time:
                return f"No {agent_type} agents are available at {time} on {parsed_date}."
            else:
                return f"No {agent_type} agents have any available slots on {parsed_date}."
    except Exception as e:
        return f"An error occurred while trying to find an available agent: {e}"


@tool
def book_appointment(
    date: str,
    time: str,
    customer_name: str,
    customer_contact: str,
    agent_name: str = None,
    agent_type: str = None,
    service_type: str = None
) -> str:
    """
    Books an appointment with a specific agent (if provided) or finds an available agent of a given type.
    """
    parsed_date = parse_relative_date(date)
    if not re.match(r"\d{4}-\d{2}-\d{2}", parsed_date):
        return f"I need a valid date in YYYY-MM-DD format to book the appointment. You provided: {date}"

    if not agent_name and not agent_type:
        return "To book an appointment, I need either a specific agent's name or the type of agent (Sales or Service)."

    final_agent_to_book = agent_name
    final_time_slot = time

    if not final_agent_to_book and agent_type:
        print(f"No specific agent provided, trying to find an available {agent_type} agent...")
        find_result = find_available_agent.invoke({"agent_type": agent_type, "date": parsed_date, "time": time})

        if "Agent " in find_result and " is available" in find_result:
            match = re.search(r"Agent (.*?) is available at (.*?) on (.*)", find_result)
            if match:
                final_agent_to_book = match.group(1).strip()
                final_time_slot = match.group(2).strip()
                print(f"Found available agent: {final_agent_to_book} at {final_time_slot}")
            else:
                return f"Could not parse available agent details from: {find_result}"
        else:
            return f"Could not find an available {agent_type} agent for {time} on {parsed_date}. {find_result}"

    if not final_agent_to_book:
        return "Could not determine which agent to book the appointment with."

    print(f"Attempting to book appointment via internal function for {final_agent_to_book} on {parsed_date} at {final_time_slot}...")
    if _book_appointment_func:
        request_body = {
            "agent_name": final_agent_to_book,
            "date": parsed_date,
            "time_slot": final_time_slot,
            "customer_name": customer_name,
            "customer_contact": customer_contact,
            "service_type": service_type if service_type else ""
        }
        booking_json = _book_appointment_func(request_body)
        booking_result = json.loads(booking_json)

        if booking_result.get("message"):
            confirmation = booking_result["message"]
            if booking_result.get("booking_id"):
                confirmation += f" Your booking ID is: {booking_result['booking_id']}."
            return confirmation
        else:
            return "Appointment booking initiated, but no confirmation message received."
    return "Error: Calendar function not initialized."


@tool
def retrieve_information(query: str) -> str:
    """
    Retrieves relevant information from the Chevrolet of Stevens Creek knowledge base.
    """
    global _retriever_instance
    if "_retriever_instance" not in globals():
        raise RuntimeError("RAG retriever not initialized.")

    qa_chain = RetrievalQA.from_chain_type(
        llm=OpenAI(temperature=0.0),
        chain_type="stuff",
        retriever=_retriever_instance,
        return_source_documents=False
    )
    result = qa_chain.invoke({"query": query})
    return result["result"]


# --- RAG Pipeline Initialization ---
_retriever_instance = None


def initialize_rag_pipeline(
    get_all_agents_func: Callable,
    get_agent_availability_func: Callable,
    book_appointment_func: Callable
):
    global _retriever_instance, _get_all_agents_func, _get_agent_availability_func, _book_appointment_func

    _get_all_agents_func = get_all_agents_func
    _get_agent_availability_func = get_agent_availability_func
    _book_appointment_func = book_appointment_func

    print("--- Initializing RAG Pipeline ---")

    print("Initializing OpenAI Embeddings...")
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set.")
        return None
    embeddings = OpenAIEmbeddings()

    if not (os.path.exists(FAISS_INDEX_PATH) and os.path.isdir(FAISS_INDEX_PATH)):
        print(f"ERROR: FAISS index not found at {FAISS_INDEX_PATH}.")
        return None

    print(f"Loading FAISS index from {FAISS_INDEX_PATH}...")
    vectordb = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    print("FAISS index loaded.")

    _retriever_instance = vectordb.as_retriever(search_kwargs={"k": 3})

    print("Initializing ChatOpenAI LLM for Agent...")
    llm_agent = ChatOpenAI(model="gpt-3.5-turbo-0125", temperature=0.0)

    tools = [
        get_all_agents,
        get_agent_availability,
        find_available_agent,
        book_appointment,
        retrieve_information
    ]



    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])


    agent = create_openai_tools_agent(llm_agent, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    print("--- RAG Pipeline Initialized with Agent Capabilities ---")
    return agent_executor


async def ask_rag(query: str, agent_executor_instance: AgentExecutor, chat_history: List[Union[AIMessage, HumanMessage]]) -> str:
    """Pass a query to the RAG agent and return final text answer."""
    if not agent_executor_instance:
        print("Error: RAG agent not initialized.")
        return "I'm sorry, the assistant is not available right now."

    print(f"\n--- Processing Query: '{query}' ---")
    start_time = time.time()
    try:
        response = await agent_executor_instance.ainvoke({"input": query, "chat_history": chat_history})
        final_answer = response.get("output", "I'm sorry, I couldn't process your request fully.")
        return final_answer
    except Exception as e:
        print(f"An error occurred: {e}")
        return f"I'm sorry, an error occurred: {e}"
    finally:
        execution_time = time.time() - start_time
        print(f"Execution time: {execution_time:.2f} seconds")


if __name__ == "__main__":
    def dummy_get_all_agents():
        return json.dumps({"Sales": ["Sarah Johnson", "Mike Rodriguez"], "Service": ["Tom Wilson", "Lisa Martinez"]})

    def dummy_get_agent_availability(agent_name: str, date: str):
        if agent_name == "Sarah Johnson" and date == datetime.now().date().strftime("%Y-%m-%d"):
            return json.dumps({"agent_name": agent_name, "date": date, "available_slots": ["10:00-11:00", "14:00-15:00"]})
        elif agent_name == "Mike Rodriguez" and date == datetime.now().date().strftime("%Y-%m-%d"):
            return json.dumps({"agent_name": agent_name, "date": date, "available_slots": ["09:00-10:00", "11:00-12:00"]})
        return json.dumps({"agent_name": agent_name, "date": date, "available_slots": []})

    def dummy_book_appointment(req_data: Dict[str, Any]):
        return json.dumps({"message": "Appointment booked successfully (dummy)!", "booking_id": "DUMMY-BOOK-ID"})

    agent_executor = initialize_rag_pipeline(
        get_all_agents_func=dummy_get_all_agents,
        get_agent_availability_func=dummy_get_agent_availability,
        book_appointment_func=dummy_book_appointment
    )

    chat_history = []
    if agent_executor:
        print("\n--- RAG Agent Ready ---")
        print("Type your query and press Enter. Type 'quit' to exit.")
        while True:
            user_query = input("Enter your query: ")
            if user_query.lower() == "quit":
                break
            import asyncio
            answer = asyncio.run(ask_rag(user_query, agent_executor, chat_history))
            print("\n--- Agent Answer ---")
            print(answer)
            chat_history.append(HumanMessage(content=user_query))
            chat_history.append(AIMessage(content=answer))
            chat_history = chat_history[-10:]
    else:
        print("\n--- RAG agent could not be initialized. ---")
