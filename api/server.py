"""
FastAPI server exposing the Branding Extraction Agent via REST API.
"""

import re
import json
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from branding_agent.agent import root_agent

load_dotenv()

# ---------------------------------------------------------------------------
# ADK Runner & Session setup
# ---------------------------------------------------------------------------
APP_NAME = "branding_extraction_app"
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Branding Extraction Agent API started | model: {root_agent.model}")
    yield
    print("Shutting down...")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Branding Extraction Agent API",
    description="AI-powered API to extract branding elements (colors, fonts, buttons, logos) from any website.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ExtractionRequest(BaseModel):
    url: str
    user_id: Optional[str] = None


class ExtractionResponse(BaseModel):
    success: bool
    url: str
    branding: Optional[dict] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers if the LLM adds them."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Utility"])
async def health_check():
    """Returns service health status."""
    return {"status": "healthy", "agent": root_agent.name}


@app.post("/extract", response_model=ExtractionResponse, tags=["Branding"])
async def extract_branding(request: ExtractionRequest):
    """
    Extract branding elements from a website URL.

    - **url**: Full website URL to crawl (e.g. `https://stripe.com`)
    - **user_id**: Optional identifier for session tracking
    """
    user_id = request.user_id or f"user_{uuid.uuid4().hex[:8]}"

    try:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
        )

        message = types.Content(
            role="user",
            parts=[types.Part(text=f"Extract branding elements from this website: {request.url}")]
        )

        final_response_text = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=message,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response_text = event.content.parts[0].text

        if not final_response_text:
            raise HTTPException(status_code=500, detail="Agent returned an empty response.")

        clean_text = _strip_markdown_fences(final_response_text)

        try:
            branding_data = json.loads(clean_text)
            return ExtractionResponse(
                success=True,
                url=request.url,
                branding=branding_data,
                raw_response=final_response_text,
            )
        except json.JSONDecodeError:
            # Return raw text if structured parse fails
            return ExtractionResponse(
                success=True,
                url=request.url,
                branding=None,
                raw_response=final_response_text,
            )

    except HTTPException:
        raise
    except Exception as e:
        return ExtractionResponse(
            success=False,
            url=request.url,
            error=str(e),
        )
