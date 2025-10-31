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

# Initialize Toolbox client
toolbox = ToolboxSyncClient(MCP_TOOLBOX_URL)
tools = toolbox.load_toolset('nomad-ai-database-tools')



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
        tools[0],
        tools[1],
        tools[2],
        tools[3]
    ],
    generate_content_config=GenerateContentConfig(
        temperature=0.0, top_p=0.5
    )
)