import uvicorn

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2ARESTFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, Part, TaskState, TextPart, TransportProtocol
from a2a.utils import get_message_text, new_task

from agent import build_agent


HOST = "localhost"
PORT = 8001

deep_agent = build_agent()


class DeepAgentsA2AExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task(context.message)

        await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        user_text = get_message_text(context.message, delimiter=" ")
        print(f"[server] user_text={user_text}")

        await updater.update_status(
            TaskState.working,
            updater.new_agent_message([Part(root=TextPart(text="Orchestrator started."))]),
        )

        inputs = {"messages": [{"role": "user", "content": user_text}]}

        async for event in deep_agent.astream_events(inputs, version="v2"):
            if event["event"] == "on_tool_start" and event["name"] == "task":
                tool_input = event["data"]["input"]
                subagent_name = tool_input["subagent_type"]
                print(f"[server] SUBAGENT CALLED: {subagent_name}")

                await updater.update_status(
                    TaskState.working,
                    updater.new_agent_message([Part(root=TextPart(text=f"SUBAGENT CALLED: {subagent_name}"))]),
                )

            if event["event"] == "on_tool_end" and event["name"] == "task":
                print("[server] SUBAGENT RETURNED")

                await updater.update_status(
                    TaskState.working,
                    updater.new_agent_message([Part(root=TextPart(text="SUBAGENT RETURNED"))]),
                )

            if event["event"] == "on_chat_model_end":
                msg = event["data"]["output"]
                final_text = msg.content
                if not final_text:
                    print("[server] FINAL=<empty>")
                    continue

                print(f"[server] FINAL={final_text}")

                await updater.update_status(
                    TaskState.working,
                    updater.new_agent_message([Part(root=TextPart(text=final_text))]),
                )

        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return


card = AgentCard(
    name="DeepAgents Orchestrator (A2A Streaming)",
    description="Streams DeepAgents subagent calls and final answer as A2A task updates.",
    url=f"http://{HOST}:{PORT}",
    version="0.1.0-demo",
    protocol_version="0.3.0",
    preferred_transport=TransportProtocol.http_json,
    additional_interfaces=[],
    capabilities=AgentCapabilities(streaming=True, push_notifications=False),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=[],
)

handler = DefaultRequestHandler(
    agent_executor=DeepAgentsA2AExecutor(),
    task_store=InMemoryTaskStore(),
)

app = A2ARESTFastAPIApplication(agent_card=card, http_handler=handler).build()

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
