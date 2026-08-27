.PHONY: install report demo test clean

install:
	pip install -r requirements.txt

# The real thing: downloads 2016-today from Yahoo Finance and builds the deck.
report:
	python3 -m report.build_report --start 2016-01-01

# Same deck from live data, ignoring the local price cache.
refresh:
	python3 -m report.build_report --start 2016-01-01 --refresh

# Synthetic data -- exercises the whole pipeline with no network access.
demo:
	python3 -m report.build_report --start 2016-01-01 --demo

test:
	python3 -m pytest tests -q

clean:
	rm -rf report/dist __pycache__ .pytest_cache
