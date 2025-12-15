import asyncio
from ingest.fetch_docs import fetch_all_docs

PDF = "https://marinasmediterraneo.es/wp-content/uploads/2025/07/Tarifas_MEste.pdf"

async def main():
    doc = (await fetch_all_docs([PDF]))[0]
    print("kind:", doc.kind)
    print("content_type:", doc.content_type)
    print("text sample:")
    print((doc.content or "")[:800])

asyncio.run(main())
