"""
Google ADK Branding Extraction Agent.
Uses OpenAI via LiteLLM to analyze and structure website branding elements.
"""

import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from branding_agent.tools.branding_extractor import crawl_and_extract_branding

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

AGENT_INSTRUCTION = """
You are an expert branding analyst. Your job is to extract and structure branding
elements from websites by using the crawl_and_extract_branding tool.

When given a website URL:
1. Call crawl_and_extract_branding with the URL
2. Analyze the raw extracted data
3. Return ONLY a valid JSON object (no markdown, no explanation) with this exact structure:

{
  "url": "<website url>",
  "site_name": "<page title or site name>",
  "brand_colors": {
    "primary": "<most prominent brand color in hex or rgb>",
    "secondary": "<second brand color>",
    "accent": "<accent or highlight color, null if not found>",
    "background": "<main page background color>",
    "text": "<primary body text color>",
    "all_colors": ["<list of all identified brand colors>"]
  },
  "typography": {
    "heading_font": "<font family for headings, null if not found>",
    "body_font": "<font family for body text, null if not found>",
    "font_sizes": {
      "h1": "<size or null>",
      "h2": "<size or null>",
      "body": "<size or null>"
    },
    "font_weights": {
      "heading": "<weight or null>",
      "body": "<weight or null>"
    },
    "line_height": "<body line-height or null>"
  },
  "buttons": {
    "primary_button": {
      "background_color": "<color or null>",
      "text_color": "<color or null>",
      "border_radius": "<value or null>",
      "padding": "<value or null>",
      "border": "<value or null>",
      "font_size": "<value or null>"
    },
    "secondary_button": {
      "background_color": "<color or null>",
      "text_color": "<color or null>",
      "border_radius": "<value or null>",
      "padding": "<value or null>",
      "border": "<value or null>",
      "font_size": "<value or null>"
    }
  },
  "logos": [
    {
      "type": "<image or svg>",
      "src": "<absolute URL or null>",
      "alt": "<alt text or null>"
    }
  ],
  "backgrounds": {
    "header": "<header background color or null>",
    "body": "<body background color or null>",
    "footer": "<footer background color or null>",
    "navbar": "<navbar background color or null>"
  },
  "design_tokens": {
    "<css-variable-name>": "<value>"
  }
}

Rules:
- Use null (not "null" string) for missing values
- Colors should be in their original format (hex, rgb, rgba)
- Output ONLY the JSON object, nothing else
"""

root_agent = LlmAgent(
    name="branding_extraction_agent",
    model=LiteLlm(model=f"openai/{MODEL}"),
    instruction=AGENT_INSTRUCTION,
    tools=[crawl_and_extract_branding],
)
