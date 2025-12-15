import asyncio
from ingest.fetch_html import fetch_all
from ingest.url_discovery import discover_pdf_links

URL = "https://marinamotril.net/"


async def main():
    html = (await fetch_all([URL]))[0]
    print("HTML length:", len(html))
    pdfs = discover_pdf_links(html, base_url=URL, limit=10)
    print("PDFs encontrados:")
    for p in pdfs:
        print(" -", p)

asyncio.run(main())
