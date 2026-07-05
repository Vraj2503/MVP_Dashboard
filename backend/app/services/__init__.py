"""Service layer for business logic.

Each module here owns one domain capability:
- gemini_client.py     : thin async wrapper around google-genai
- risk_engine.py       : risk score formula + tier mapping
- observability.py     : chat_logs persistence + Golden test harness
- nl2sql.py            : NL -> SQL -> validated result pipeline
- insight_generator.py : per-widget Gemini narratives (cached)
- whatif_engine.py     : deterministic what-if + Gemini narrative + solver
- alert_engine.py      : threshold/trend alert generation + AI severity ranking
- digest_generator.py  : bi-weekly "month at a glance" narrative digests
"""
