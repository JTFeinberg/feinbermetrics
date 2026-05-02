.PHONY: refresh fetch export push

refresh: fetch export push
	@echo "Done. Schedule data refreshed and deployed."

fetch:
	@echo "Fetching schedule data from FanGraphs..."
	.venv/bin/python fetch_schedules.py

export:
	@echo "Exporting to CSV..."
	.venv/bin/python export_csv.py

push:
	@echo "Pushing to GitHub..."
	git add schedules.csv
	git commit -m "Refresh schedule data $$(date +%Y-%m-%d)"
	git push origin main
