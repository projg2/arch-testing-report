.PHONY: build
build: generate_report.py template.html.jinja2
	python generate_report.py template.html.jinja2 -o report.html
