"""Demonstration of Travel AI Conceirge using Agent Development Kit"""

from google.adk.agents import Agent

from nomad_ai import prompt

from nomad_ai.sub_agents.inspiration.agent import inspiration_agent
from nomad_ai.sub_agents.pre_trip.agent import pre_trip_agent
from nomad_ai.sub_agents.planning.agent import planning_agent
from nomad_ai.sub_agents.booking.agent import booking_agent

from nomad_ai.tools.memory import _load_precreated_itinerary


root_agent = Agent(
    model="gemini-2.5-flash",
    name="root_agent",
    description="A Travel Conceirge using the services of multiple sub-agents",
    instruction=prompt.ROOT_AGENT_INSTR,
    sub_agents=[
        inspiration_agent,
        planning_agent,
        booking_agent,
        pre_trip_agent,
    ],
    before_agent_callback=_load_precreated_itinerary,
)