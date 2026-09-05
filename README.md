# flight-scraper

Scheduled Python + Playwright scraper for round-trip flights departing **YQB** and **YUL**.
For each source (Google Flights, Kayak, Expedia, Skyscanner, Air Canada, Air Transat, WestJet, Porter, Flair),
route, date, and passenger configuration (1–2 adults, 1–2 children) it records the **cheapest**, **fastest**,
and **best** itinerary with final-stage price, cabin/checked luggage pricing, and a deep-link URL, then upserts
everything into **Supabase** for the website to read.

Project status: prompt chain in `.prompts/` (research → plan → implement). Code lands here after prompt 003 runs.
