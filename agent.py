import os

from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.graph.state import CompiledStateGraph


def build_agent() -> CompiledStateGraph:
    load_dotenv()

    model_name = os.getenv("DEEPAGENTS_MODEL", "openai:gpt-4o-mini")
    model = init_chat_model(model_name)

    football_subagent = {
        "name": "football-agent",
        "description": "American Football expert (rules, tactics, positions, playcalling).",
        "system_prompt": (
            "You are an American Football coach and analyst.\n"
            "Explain concepts clearly (e.g., 4-3 vs 3-4, coverages, gap responsibilities).\n"
            "Use concise bullet points and examples when helpful.\n"
            "No web browsing. Focus on timeless fundamentals."
        ),
        "tools": [],
    }

    cat_subagent = {
        "name": "cat-expert-agent",
        "description": "Cat expert (behavior, biology, care, training, common issues).",
        "system_prompt": (
            "You are a cat behavior and biology expert.\n"
            "Explain behavior clearly and provide practical, safe guidance.\n"
            "No diagnoses. If health-related, mention when a vet visit is appropriate.\n"
            "No web browsing."
        ),
        "tools": [],
    }

    agent = create_deep_agent(
        model=model,
        tools=[],
        system_prompt=(
            "You are a coordinator agent.\n"
            'If the question is about American Football, delegate to subagent "football-agent".\n'
            'If the question is about cats, delegate to subagent "cat-expert-agent".\n'
            "If it contains both topics, delegate to both and then merge the answers.\n"
            "Keep the final response clear and structured.\n"
            "Prefer delegating when a subagent is relevant."
        ),
        subagents=[football_subagent, cat_subagent],
    )

    return agent
