import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from google import genai

from app.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_THINKING_LEVEL
from app.db.models import Conversation, Message, MessageType
from app.db.repo import create_message, get_messages
from app.db.session import Session


client = genai.Client(api_key=GEMINI_API_KEY)

# system prompts
PROMPTS = Path(__file__).with_name("assets") / "prompts"
BASE_PROMPT = (PROMPTS / "base_system_prompt.xml").read_text()
GROUP_PROMPT = (PROMPTS / "group_addition.xml").read_text()
USER_INFO_PROMPT = (PROMPTS / "user_info.xml").read_text()

# formatting ai input and output
TOOLS = [
    {
        "type": "function",
        "name": "send",
        "description": "Send one text message to the user.",
        "parameters": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
    {
        "type": "function",
        "name": "react",
        "description": "React to a message.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {"type": "integer"},
                "reaction": {"type": "string"},
            },
            "required": ["message_id", "reaction"],
        },
    },
    {
        "type": "function",
        "name": "do_nothing",
        "description": "Finish without sending a message or reaction.",
        "parameters": {"type": "object", "properties": {}},
    },
]

MESSAGE_TAGS = {
    MessageType.SYSTEM_MESSAGE: "system_message",
    MessageType.TOOL_RESPONSE: "tool_response",
    MessageType.USER_MESSAGE: "user_message",
    MessageType.USER_ACTION: "user_action",
    MessageType.USER_REACTION: "user_reaction",
    MessageType.KIWI_MESSAGE: "kiwi_message",
    MessageType.KIWI_REACTION: "kiwi_reaction",
}  # message tags for each message type

MESSAGE_ID_TYPES = {
    MessageType.USER_MESSAGE,
    MessageType.KIWI_MESSAGE,
}  # message types that get their own IDs

TIMESTAMP_ATTRIBUTES = {
    MessageType.SYSTEM_MESSAGE: "sent_at",
    MessageType.USER_MESSAGE: "sent_at",
    MessageType.USER_ACTION: "done_at",
    MessageType.USER_REACTION: "sent_at",
    MessageType.KIWI_MESSAGE: "sent_at",
    MessageType.KIWI_REACTION: "sent_at",
}  # map timestampts for each action to XML attributes

CONTEXT_ATTRIBUTES = {
    MessageType.USER_MESSAGE: ("reply_to",),
    MessageType.USER_REACTION: ("to_id",),
    MessageType.KIWI_REACTION: ("to_id",),
    MessageType.TOOL_RESPONSE: ("tools", "to_tool"),
}  # context attrbiutes for each type


# classes to use in parsing actions
@dataclass(frozen=True, slots=True)
class SendAction:
    message: str


@dataclass(frozen=True, slots=True)
class ReactAction:
    message_id: int
    reaction: str


KiwiAction = SendAction | ReactAction


class InvalidAIResponse(ValueError):
    pass


def create_system_prompt(
    *,
    mode: str,
    username: str
) -> str:
    """Create a system prompt for kiwi with user info and group addition if needed"""
    prompt = BASE_PROMPT

    if username:
        prompt += f"\n{USER_INFO_PROMPT.format(username)}"
    if mode == "group":
        prompt += f"\n{GROUP_PROMPT}"

    return prompt


def render_conversation(messages: list[Message]) -> str:
    """Convert a list of database messages into an XML conversation"""
    root = Element("conversation")

    for message in messages:
        node = SubElement(root, MESSAGE_TAGS[message.message_type])
        if (
            message.message_id is not None
            and message.message_type in MESSAGE_ID_TYPES
        ):
            node.set("id", str(message.message_id))

        timestamp_attribute = TIMESTAMP_ATTRIBUTES.get(message.message_type)
        if timestamp_attribute is not None:
            node.set(timestamp_attribute, message.sent_at.isoformat())

        for attribute in CONTEXT_ATTRIBUTES.get(message.message_type, ()):
            value = message.context.get(attribute)
            if value is None:
                continue
            node.set(
                attribute,
                (
                    value
                    if isinstance(value, str)
                    else json.dumps(value, ensure_ascii=False)
                ),
            )

        node.text = message.content

    return tostring(root, encoding="unicode")


def parse_actions(interaction: object) -> list[KiwiAction]:
    """Parse ai response into a list of actions"""
    actions: list[KiwiAction] = []
    found_call = False

    for step in getattr(interaction, "steps", None) or []:
        if getattr(step, "type", None) != "function_call":
            continue  # ignore steps that aren't fucntion calls

        found_call = True
        name = step.name
        arguments = step.arguments
        if not isinstance(arguments, Mapping):
            raise InvalidAIResponse(f"{name} returned invalid arguments")  # raise on invalid arguments

        if name == "send":
            message = arguments.get("message")
            if not isinstance(message, str) or not message:
                raise InvalidAIResponse("send requires a non-empty message")  # raise on emtpy message
            actions.append(SendAction(message=message))  # append sending

        elif name == "react":
            message_id = arguments.get("message_id")
            reaction = arguments.get("reaction")

            if not isinstance(message_id, int) or isinstance(message_id, bool):
                raise InvalidAIResponse("react requires an integer message_id")  # raise on incorrect message id
            if not isinstance(reaction, str) or not reaction:
                raise InvalidAIResponse("react requires a non-empty reaction")  # raise on empty reaction
            
            actions.append(
                ReactAction(message_id=message_id, reaction=reaction)
            )  # append reaction
        elif name != "do_nothing":
            raise InvalidAIResponse(f"unknown tool: {name}")  # raise on unknown tools

    if not found_call:
        raise InvalidAIResponse("Gemini returned no tool calls")  # raise on no tool calls

    return actions


async def ask(
    *,
    conversation_id: int,
    message_type: MessageType,
    content: str,
    message_id: int | None = None,
    sent_at: datetime | None = None,
    context: dict[str, object] | None = None,
) -> list[KiwiAction]:
    """Persist an incoming event and return kiwi's actions"""
    async with Session.begin() as session:
        # get conversation
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            raise ValueError(f"conversation {conversation_id} does not exist")

        # persist the new message in database
        await create_message(
            session=session,
            conversation_id=conversation_id,
            message_type=message_type,
            content=content,
            message_id=message_id,
            sent_at=sent_at,
            context=context,
        )
        messages = await get_messages(session, conversation_id)
        system_prompt = conversation.system_prompt

    # get AI's response
    interaction = await client.aio.interactions.create(
        model=GEMINI_MODEL,
        input=render_conversation(messages),
        system_instruction=system_prompt,
        tools=TOOLS,
        generation_config={
            "tool_choice": "any",
            "thinking_level": GEMINI_THINKING_LEVEL
        },
        store=False,
        
    )
    return parse_actions(interaction)  # return kiwi's actions parsed by func
