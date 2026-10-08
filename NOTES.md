== curl ==
# POST /api/runs  {"scenario":"basic","endpoint":"https://…","model":"gpt-4o","concurrency":20,"duration":60}
# GET  /api/runs/1/stream   (SSE)
# POST /api/runs/1/stop
# CLI: python cli.py run scenarios/basic.yml

== session plan ==
# Session 1: tokenizer + ratelimit + engine against mock OpenAI server → tests green
# Session 2: metrics + scenarios + cli → report/compare
# Session 3: web app + SSE + screenshots → README → CI/Docker/Pages → tag
