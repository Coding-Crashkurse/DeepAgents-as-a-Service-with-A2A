import argparse
import asyncio
import uuid

import httpx

from a2a.client.card_resolver import A2ACardResolver
from a2a.client.client import ClientConfig
from a2a.client.client_factory import ClientFactory
from a2a.types import Message, Part, Role, TextPart
from a2a.utils import get_message_text


BASE_URL = "http://localhost:8001"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=None) as http:
        card = await A2ACardResolver(http, BASE_URL).get_agent_card()

        client = await ClientFactory.connect(
            card,
            client_config=ClientConfig(
                supported_transports=[card.preferred_transport],
                httpx_client=http,
                streaming=True,
                polling=False,
            ),
        )

        try:
            msg = Message(
                role=Role.user,
                message_id=str(uuid.uuid4()),
                parts=[Part(root=TextPart(text=args.text))],
            )

            async for task, update in client.send_message(msg):
                if update is None:
                    print(f"state={task.status.state.value}")
                    continue

                text = get_message_text(update.status.message, delimiter=" ") if update.status.message else ""
                print(f"state={task.status.state.value} text={text}")

        finally:
            await client.close()


if __name__ == "__main__":
    asyncio.run(main())
