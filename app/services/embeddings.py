from google import genai
import asyncio
from google.genai.errors import ClientError

from app.core.config import settings

client = genai.Client(
    api_key=settings.gemini_api_key,
)

EMBEDDING_MODEL = "gemini-embedding-001"


async def generate_embedding(text: str, retries: int = 3) -> list[float]:
    for attempt in range(retries):
        try:
            response = await client.aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config={"output_dimensionality": 1536},
            )
            if not response.embeddings:
                raise RuntimeError("Embedding API returned no embeddings")
            return response.embeddings[0].values

        except ClientError as e:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            await asyncio.sleep(wait)

    raise RuntimeError("Unreachable")
