.PHONY: run test check
run:
	python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
test:
	python -m unittest discover -s tests -v
check:
	python -m compileall -q app tests
	node --check app/static/app.js
