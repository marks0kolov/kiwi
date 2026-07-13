from pathlib import Path

from google import genai

from config import GEMINI_API_KEY


client = genai.Client(api_key=GEMINI_API_KEY)

PROMPTS = Path(__file__).with_name("prompts")
BASE_PROMPT = (PROMPTS / "base_system_prompt.xml").read_text()
GROUP_PROMPT = (PROMPTS / "group_addition.xml").read_text()


async def ask(
    message_xml: str,
    previous_interaction_id: str | None = None,
    group: bool = False,
) -> tuple[str, str]:
    """Send XML messages to kiwi and return (reply, interaction_id)."""
    system_instruction = BASE_PROMPT + (GROUP_PROMPT if group else "")
    interaction = await client.aio.interactions.create(
        model="gemini-3.5-flash",
        input=message_xml,
        system_instruction=system_instruction,
        previous_interaction_id=previous_interaction_id,
    )
    return interaction.output_text, interaction.id
