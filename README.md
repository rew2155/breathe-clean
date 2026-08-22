# Breathe Clean

The beginning of Breathe Clean: an application that monitors the air quality of a room and adjusts a nearby air purifier accordingly :)

## Overview

Breathe Clean is an IoT-style project for monitoring indoor air quality and controlling an air purifier based on the PM2.5 air quality reading. 
The project currently includes a four-room home simulator, automatic purifier
control, a FastAPI and PostgreSQL backend, MQTT device messaging, and a React
dashboard with room-specific reading history.

### Current Data Flow

```text
Four-room Sensor Simulator
    |
    | POST /readings
    v
FastAPI Backend
    |                    |
    | SQLAlchemy         | purifier commands
    v
PostgreSQL
    |
    | GET /rooms and room history
    v
React Dashboard
```

The simulator generates independent PM2.5 readings for each room. FastAPI stores
them, evaluates that room's recent air quality, and controls only its purifier. The
dashboard shows the latest state of every room, and each room card links to its
complete reading history.

## Installation

### Prerequisites

- Python 3.12 or later
- Node.js 24 or later
- PostgreSQL
- Eclipse Mosquitto for local MQTT development

Clone the repository and move into its root directory. Then create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Install the backend dependencies:

```bash
python -m pip install -r backend/requirements.txt
```

Install the frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

## Database Setup

Create a local PostgreSQL database:

```bash
createdb breathe_clean
```

Copy the example environment file:

```bash
cp .envexample .env
```

Update `DATABASE_URL` in `.env` with your PostgreSQL username and password:

```env
DATABASE_URL=postgresql+psycopg://username:password@localhost/breathe_clean
```

Apply all database migrations:

```bash
cd backend
alembic upgrade head
cd ..
```

If you created `sensor_readings` with the earlier manual setup command, record the initial migration as already applied instead of trying to create the table again:

```bash
cd backend
alembic stamp head
cd ..
```

Only use `alembic stamp head` when the existing table already matches the current SQLAlchemy model.

When the SQLAlchemy models change, create and review a new migration before applying it:

```bash
cd backend
alembic revision --autogenerate -m "describe the schema change"
alembic upgrade head
```

## Running the Project

From the repository root, start the FastAPI development server:

```bash
cd backend
uvicorn main:app --reload
```

The API is available at `http://127.0.0.1:8000`, and its interactive documentation is available at `http://127.0.0.1:8000/docs`.

In another terminal, start the React development server:

```bash
cd frontend
npm run dev
```

The dashboard is available at `http://127.0.0.1:5173` and calls FastAPI at `http://127.0.0.1:8000`. FastAPI allows requests from the local Vite origins through its CORS configuration.

Configure comma-separated frontend origins in `.env` when the dashboard runs at different URLs:

```env
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

For a deployed frontend, replace these development origins with the exact production origin. Do not use a wildcard when adding credentialed requests later.

Seed the four-room demo once before starting the API or simulator:

```bash
source .venv/bin/activate
cd backend
python seed.py
```

The seed is safe to run more than once. It creates Master Bedroom, Living Room,
Kitchen, and Home Office, each with its own sensor and purifier. If the migration
created a Legacy Room, the seed renames it to Master Bedroom so its existing
readings are preserved.

With the API running, start the home simulator from another terminal:

```bash
source .venv/bin/activate
cd backend
python mock_sensor.py
```

It publishes one reading for every room immediately and then every four minutes.
Each room changes independently, and an active purifier gradually lowers only that
room's simulated PM2.5. For a faster local demo, override the interval:

```bash
SIMULATION_INTERVAL_SECONDS=10 python mock_sensor.py
```

The React dashboard refreshes its rooms, readings, and purifier states every 15
seconds. Click a room card to open `/rooms/{room_id}`, where a trend chart and
timestamped reading list show that room's history. You can also retrieve the stored
readings directly with:

```bash
curl http://127.0.0.1:8000/readings
```

Run the backend unit tests with:

```bash
cd backend
python -m unittest discover -s tests
```

Run the frontend checks with:

```bash
cd frontend
npm run lint
npm run build
```

## Air-Quality Policy

The initial purifier policy uses separate thresholds to avoid rapid on/off cycling:

- When off, the purifier turns on at an average PM2.5 reading of `15 µg/m³` or higher.
- When on, the purifier turns off at an average PM2.5 reading of `8 µg/m³` or lower.
- Between those thresholds, the purifier keeps its current state.
- The average uses all of that sensor's readings from the previous five minutes.
- One recent reading is enough to make a decision, so elevated air turns the
  purifier on immediately.
- A sensor with historical readings but none in the window is reported as stale.

This policy is an initial engineering rule and does not represent regulatory compliance. The thresholds and averaging window will be tuned using real sensor data.

## Purifier Control

The backend currently uses a simulated purifier adapter. When an air-quality evaluation is ready and its desired state differs from the purifier's requested state, the adapter records an on/off command. Repeated readings do not issue duplicate commands when the purifier already has that requested state.

Purifiers track two states:

- `desired_is_on` records the state requested by the backend.
- `is_on` records the state confirmed by the device.
- `pending_command_id` links an outstanding MQTT command to its acknowledgment.

The simulator confirms commands immediately, so it updates both state values. The MQTT adapter publishes a command, records it as pending, and leaves `is_on` unchanged. A matching state message confirms the command and updates `is_on`; acknowledgments for older commands are ignored.

A failed purifier command returns `503 Service Unavailable`, leaves the purifier state unchanged, and rolls back the reading being processed.

## MQTT Protocol

Device messages use versioned MQTT topics so the protocol can evolve without silently breaking existing clients:

```text
breathe-clean/v1/sensors/{sensor_id}/readings
breathe-clean/v1/purifiers/{purifier_id}/commands
breathe-clean/v1/purifiers/{purifier_id}/state
```

Every JSON message includes a UUID message identifier, a device identifier, and a timezone-aware timestamp. Purifier state messages also reference the command they acknowledge.

Sensor message IDs are stored with their readings and uniquely constrained. If a QoS 1 message is delivered again, the consumer recognizes it as already processed instead of storing another reading or repeating a purifier command.

The backend MQTT transport defaults to a local broker. These values can be changed in `.env`:

```env
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_CLIENT_ID=breathe-clean-backend
MQTT_ENABLED=false
```

Start an installed Mosquitto broker for local development with:

```bash
mosquitto -v
```

Set `MQTT_ENABLED=true` after the broker is running. When enabled, FastAPI connects during application startup, consumes sensor readings and purifier acknowledgments, and publishes purifier commands. When disabled, the REST API continues to use the simulated purifier adapter and does not require a broker.

MQTT publishes use quality of service level 1 and wait for broker acknowledgment. Subscriptions are renewed whenever the transport reconnects.

## API

**POST /rooms** - Creates a room with one sensor and one purifier

```json
{
    "name": "Master Bedroom"
}
```

**GET /rooms** - Retrieves rooms and their configured devices

Identifiers are serialized as strings in responses because PostgreSQL `BIGINT`
values can exceed JavaScript's safe integer range.

```json
[
    {
        "id": "123",
        "name": "Master Bedroom",
        "sensor": {
            "id": "456",
            "room_id": "123"
        },
        "purifier": {
            "id": "789",
            "room_id": "123",
            "is_on": false,
            "desired_is_on": false,
            "pending_command_id": null
        }
    }
]
```

**GET /rooms/{room_id}** - Retrieves one room and its configured devices

**GET /rooms/{room_id}/readings** - Retrieves that room's readings newest-first

**POST /readings** - Stores a new PM2.5 reading

```json
{
    "pm25": 20.5,
    "sensor_id": 456
}
```

The response includes the stored reading and the current policy evaluation:

```json
{
    "reading": {
        "id": "48293482938423",
        "pm25": 20.5,
        "created_at": "2026-08-14T04:30:12.123456Z",
        "sensor_id": "456",
        "source_message_id": null
    },
    "evaluation": {
        "status": "ready",
        "desired_purifier_state": true,
        "reading_count": 1,
        "average_pm25": 20.5
    }
}
```

**GET /readings** - Retrieves all stored PM2.5 readings

```json
[
    {
        "id": "48293482938423",
        "pm25": 20.5,
        "created_at": "2026-08-14T04:30:12.123456Z",
        "sensor_id": "456",
        "source_message_id": null
    }
]
```

## Goal

The long-term goal for Breathe Clean is to collect air-quality measurements, determine when the air quality requires intervention, and provide effective intervention by controlling one or many nearby air purifiers. I am currently completing research about the most effective way to time this intervention in order to achieve a sustainably breathable home environment.
