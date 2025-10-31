"""Demonstration of Travel AI Conceirge using Agent Development Kit"""

from google.adk.agents import Agent

from nomad_ai_in_trip import prompt

from nomad_ai_in_trip.sub_agents.in_trip.agent import in_trip_agent


from nomad_ai_in_trip.tools.memory import _load_precreated_itinerary


root_agent = Agent(
    model="gemini-2.5-flash",
    name="root_agent",
    description="A Travel Conceirge using the services of multiple sub-agents",
    instruction=prompt.ROOT_AGENT_INSTR,
    sub_agents=[
        in_trip_agent
    ],
    before_agent_callback=_load_precreated_itinerary,
)