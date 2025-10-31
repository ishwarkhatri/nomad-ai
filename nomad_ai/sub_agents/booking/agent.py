# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Booking agent and sub-agents, handling the confirmation and payment of bookable events."""

import os
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.genai.types import GenerateContentConfig

from nomad_ai.shared_libraries import types
from nomad_ai.sub_agents.booking import prompt

from toolbox_core import ToolboxSyncClient

# Get MCP Toolbox endpoint from environment
MCP_TOOLBOX_URL = os.getenv(
    "MCP_TOOLBOX_URL",
    "https://toolbox-632735824953.us-central1.run.app"
)

# Lazy-load toolbox tools to avoid pickling issues during deployment
_tools_cache = None

def get_toolbox_tools():
    """Lazy-load toolbox tools to avoid serialization issues."""
    global _tools_cache
    if _tools_cache is None:
        toolbox = ToolboxSyncClient(MCP_TOOLBOX_URL)
        _tools_cache = toolbox.load_toolset('nomad-ai-database-tools')
    return _tools_cache

# Create wrapper functions for database tools that can be serialized
def save_itinerary_to_database(
    user_id: str,
    trip_name: str,
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    itinerary_data: str,
    booking_status: str = "booked"
):
    """
    Save a completed travel itinerary to the database after booking confirmation.
    
    Args:
        user_id: Unique identifier for the user/traveler
        trip_name: Name or title of the trip (e.g., "Seattle Weekend Getaway")
        origin: Starting location/city
        destination: Destination location/city
        start_date: Trip start date in YYYY-MM-DD format
        end_date: Trip end date in YYYY-MM-DD format
        itinerary_data: Complete itinerary as JSON string
        booking_status: Booking status (pending, booked, cancelled, completed). Defaults to 'booked'.
    
    Returns:
        itinerary_id on success
    """
    tools = get_toolbox_tools()
    save_func = tools[3]  # save-itinerary-to-database
    return save_func(
        user_id=user_id,
        trip_name=trip_name,
        origin=origin,
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        itinerary_data=itinerary_data,
        booking_status=booking_status
    )

def get_user_itineraries(user_id: str, limit: int = 10):
    """
    Retrieve all itineraries for a specific user.
    
    Args:
        user_id: Unique identifier for the user/traveler
        limit: Maximum number of itineraries to return. Defaults to 10.
    
    Returns:
        List of itinerary summaries
    """
    tools = get_toolbox_tools()
    get_func = tools[1]  # get-user-itineraries
    return get_func(user_id=user_id, limit=limit)

def get_itinerary_details(itinerary_id: int):
    """
    Retrieve complete details of a specific itinerary including the full JSON data.
    
    Args:
        itinerary_id: The unique ID of the itinerary to retrieve
    
    Returns:
        Complete itinerary details
    """
    tools = get_toolbox_tools()
    get_details_func = tools[0]  # get-itinerary-details
    return get_details_func(itinerary_id=itinerary_id)

def save_booking(
    booking_id: str,
    itinerary_id: int,
    booking_reference: str,
    booking_type: str,
    booking_details: str,
    payment_status: str,
    payment_method: str,
    amount_usd: int,
    confirmation_number: str,
    created_at: str
):
    """
    Save individual booking records (flight, hotel, activity, etc.) linked to an itinerary.
    
    Args:
        booking_id: Unique identifier for the booking
        itinerary_id: The ID of the related itinerary
        booking_reference: External booking reference number or vendor ID
        booking_type: Type of booking (e.g., "flight", "hotel", "car_rental", "activity")
        booking_details: Complete booking details as a JSON string
        payment_status: Payment status (pending, paid, refunded, failed)
        payment_method: Payment method used (credit_card, debit_card, wallet, etc.)
        amount_usd: Total booking amount in USD
        confirmation_number: Confirmation or PNR number returned by provider
        created_at: Timestamp when the booking was created (ISO 8601 format)
    
    Returns:
        booking_id on success
    """
    tools = get_toolbox_tools()
    save_booking_func = tools[2]  # save-booking
    return save_booking_func(
        booking_id=booking_id,
        itinerary_id=itinerary_id,
        booking_reference=booking_reference,
        booking_type=booking_type,
        booking_details=booking_details,
        payment_status=payment_status,
        payment_method=payment_method,
        amount_usd=amount_usd,
        confirmation_number=confirmation_number,
        created_at=created_at
    )



create_reservation = Agent(
    model="gemini-2.5-flash",
    name="create_reservation",
    description="""Create a reservation for the selected item.""",
    instruction=prompt.CONFIRM_RESERVATION_INSTR,
)


payment_choice = Agent(
    model="gemini-2.5-flash",
    name="payment_choice",
    description="""Show the users available payment choices.""",
    instruction=prompt.PAYMENT_CHOICE_INSTR,
)

process_payment = Agent(
    model="gemini-2.5-flash",
    name="process_payment",
    description="""Given a selected payment choice, processes the payment, completing the transaction.""",
    instruction=prompt.PROCESS_PAYMENT_INSTR,
)

save_itinerary_agent = Agent(
    model="gemini-2.5-flash",
    name="save_itinerary_agent",
    description="""Validates and structures the itinerary data in the correct Pydantic format before saving to database.""",
    instruction=prompt.SAVE_ITINERARY_INSTR,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_schema=types.Itinerary,
    output_key="itinerary",
    generate_content_config=types.json_response_config,
)

booking_agent = Agent(
    model="gemini-2.5-flash",
    name="booking_agent",
    description="Given an itinerary, complete the bookings of items by handling payment choices and processing.",
    instruction=prompt.BOOKING_AGENT_INSTR,
    tools=[
        AgentTool(agent=create_reservation),
        AgentTool(agent=payment_choice),
        AgentTool(agent=process_payment),
        AgentTool(agent=save_itinerary_agent),
        save_itinerary_to_database,
        get_user_itineraries,
        get_itinerary_details,
        save_booking,
    ],
    generate_content_config=GenerateContentConfig(
        temperature=0.0, top_p=0.5
    )
)