install:
	pip install -r requirements.txt

db:
	psql "$$DATABASE_URL" -f sql/schema.sql
	psql "$$DATABASE_URL" -f sql/seed_lens.sql

collect:
	python -m collectors.ats_jobs
	python -m collectors.cert_transparency
	python -m collectors.github_meta
	python -m collectors.news_rss
	python -m collectors.launch_feeds
	python -m core.fit

rank:
	python -m core.score

queue:
	python -m outreach.draft

report:
	python -m outreach.ledger
