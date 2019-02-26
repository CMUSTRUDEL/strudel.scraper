
PACKAGE = strudel.scraper
TESTROOT = stscraper

.PHONY: test
test:
	python -m unittest test

.PHONY: publish
publish:
	test $$(git config user.name) || git config user.name "semantic-release (via TravisCI)"
	test $$(git config user.email) || git config user.email "semantic-release@travis"
	semantic-release publish

.PHONY: clean
clean:
	rm -rf $(PACKAGE).egg-info dist build docs/build
	find -name "*.pyo" -delete
	find -name "*.pyc" -delete
	find -name __pycache__ -delete

.PHONY: html
html:
	sphinx-build -M html "docs" "docs/build"

.PHONY: install
install:
	pip install -r requirements.txt

.PHONY: install_dev
install_dev:
	$(MAKE) install
	pip install requests
	pip install typing requests sphinx sphinx-autobuild
	pip install python-semantic-release==3.11.2
