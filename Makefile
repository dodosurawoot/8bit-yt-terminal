.PHONY: install dev build clean

install:
	./venv/bin/pip install -e .
	./venv/bin/pip install pyinstaller

dev:
	./venv/bin/python -m yt_terminal.main

build:
	./venv/bin/pyinstaller --name "YT-Terminal" \
		--onefile \
		--console \
		--clean \
		--collect-data ytmusicapi \
		--add-data "yt_terminal/style.tcss:." \
		--add-data "yt_terminal/assets:assets" \
		yt_terminal/main.py

clean:
	rm -rf build/ dist/ *.spec
	rm -rf yt_terminal.egg-info/
	find . -type d -name "__pycache__" -exec rm -r {} +
