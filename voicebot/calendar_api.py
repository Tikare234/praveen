# calendar.py (NO FastAPI, just functions)

import sqlite3
import json
from datetime import datetime
from typing import Dict, Any

# --- Database Setup ---
DATABASE_FILE = "calendar.db"  # SQLite database file


def get_db_connection():
    """Establish a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def init_calendar_db():
    """Initialize the database schema and populate initial agent data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            name TEXT PRIMARY KEY,
            type TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            booking_id TEXT PRIMARY KEY,
            agent_name TEXT NOT NULL,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_contact TEXT NOT NULL,
            service_type TEXT,
            booked_at TEXT NOT NULL
        )
    """)
    conn.commit()

    # Populate agents if table is empty
    cursor.execute("SELECT COUNT(*) FROM agents")
    if cursor.fetchone()[0] == 0:
        AGENTS_DATA = {
            "Sales": ["Sarah Johnson", "Mike Rodriguez", "Jennifer Chen"],
            "Service": ["Tom Wilson", "Lisa Martinez", "David Park"],
        }
        for agent_type, names in AGENTS_DATA.items():
            for name in names:
                cursor.execute(
                    "INSERT INTO agents (name, type) VALUES (?, ?)",
                    (name, agent_type),
                )
        conn.commit()

    conn.close()
    print("Calendar database initialized.")


# --- Calendar API Functions (formerly endpoints, now just Python functions) ---

def get_all_agents_func() -> str:
    """Return a JSON string with agent types and names from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, type FROM agents")
    agents_list = cursor.fetchall()
    conn.close()

    agents_dict = {"Sales": [], "Service": []}
    for row in agents_list:
        agents_dict.setdefault(row["type"], []).append(row["name"])

    return json.dumps(agents_dict)


def get_agent_availability_func(agent_name: str, date: str) -> str:
    """Return a JSON string with available time slots for a specific agent on a given date."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if agent exists
    cursor.execute("SELECT COUNT(*) FROM agents WHERE name = ?", (agent_name,))
    if cursor.fetchone()[0] == 0:
        conn.close()
        return json.dumps({"detail": "Agent not found"})

    # Fetch already booked slots
    cursor.execute(
        "SELECT time_slot FROM appointments WHERE agent_name = ? AND date = ?",
        (agent_name, date),
    )
    booked_slots = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Working hours: 9 AM to 5 PM
    all_slots = [f"{h:02d}:00-{h+1:02d}:00" for h in range(9, 17)]
    available_slots = [slot for slot in all_slots if slot not in booked_slots]

    return json.dumps({
        "agent_name": agent_name,
        "date": date,
        "available_slots": available_slots,
        "booked_slots": booked_slots,  # Helpful for debugging
    })


def book_appointment_func(req_data: Dict[str, Any]) -> str:
    """
    Book an appointment and return a JSON string with confirmation or error.
    `req_data` should be a dictionary matching the AppointmentRequest structure.
    """
    agent_name = req_data.get("agent_name")
    date = req_data.get("date")
    time_slot = req_data.get("time_slot")
    customer_name = req_data.get("customer_name")
    customer_contact = req_data.get("customer_contact")
    service_type = req_data.get("service_type")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if agent exists
    cursor.execute("SELECT COUNT(*) FROM agents WHERE name = ?", (agent_name,))
    if cursor.fetchone()[0] == 0:
        conn.close()
        return json.dumps({"detail": "Agent not found"})

    # Validate date/time format
    try:
        datetime.strptime(date, "%Y-%m-%d")
        datetime.strptime(time_slot.split("-")[0], "%H:%M")
    except ValueError:
        conn.close()
        return json.dumps({"detail": "Invalid date or time_slot format."})

    # Check if slot already booked
    cursor.execute(
        """
        SELECT COUNT(*) FROM appointments
        WHERE agent_name = ? AND date = ? AND time_slot = ?
        """,
        (agent_name, date, time_slot),
    )
    if cursor.fetchone()[0] > 0:
        conn.close()
        return json.dumps({"detail": "Time slot already booked."})

    booking_id = f"BOOK-{agent_name}-{date}-{time_slot}-{datetime.now().timestamp()}"
    booked_at = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO appointments (
            booking_id, agent_name, date, time_slot,
            customer_name, customer_contact, service_type, booked_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (booking_id, agent_name, date, time_slot, customer_name,
          customer_contact, service_type, booked_at))

    conn.commit()
    conn.close()

    return json.dumps({
        "message": "Appointment booked successfully!",
        "booking_id": booking_id,
    })


# --- Optional: Add initial dummy bookings here for testing after DB initialization ---
