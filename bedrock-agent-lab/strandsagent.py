import boto3
from datetime import datetime
import pytz
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator, current_time

# 1. Connect to Amazon Bedrock using the AWS profile that successfully authenticated
session = boto3.Session(
    profile_name="bedrock-dev",
    region_name="us-east-1",
)

#2. Configure Amazon Nova Lite model for use with the Strands Agent
model = BedrockModel(
    boto_session=session,
    model_id="us.amazon.nova-lite-v1:0",
    temperature=0.2,
    max_tokens=500,
)

#3. Define your own custom tools

@tool
def get_india_time() -> str:
    """Get the current time in India (IST - Indian Standard Time, UTC+5:30)."""
    utc_now = datetime.now(pytz.UTC)
    india_tz = pytz.timezone('Asia/Kolkata')
    india_time = utc_now.astimezone(india_tz)
    return india_time.strftime("%Y-%m-%d %H:%M:%S IST")

@tool
def count_keywords(text: str, keyword: str) -> int:
    """Count the number of occurrences of a keyword in a given text."""
    return text.lower().count(keyword.lower())

#4. Create the agent with built-in tools and your custom tools
agent = Agent(
    model=model,
    tools=[calculator, current_time, get_india_time, count_keywords],
    system_prompt=(
        "You are a helpful Ai assistant",
        "Use the tools when they are relevant to the user's request",
        "Explain your answers in a concise and clear manner"

    ),
)

#5. Run the agent
if __name__ == "__main__":
    prompt = """
1. What time is it in India right now?
2. Calculate 100 divided by 4.
3. Count the occurrences of 'agent' in:
   'An agent can use tools, and an agent can complete tasks.'
"""

result = agent(prompt)
print("\n=== AGENT RESPONSE ===")
print(result)

