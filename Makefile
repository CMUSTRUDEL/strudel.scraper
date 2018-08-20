
.PHONY: test
test:
	python -m doctest oscar.py; python -m unittest test

.PHONY: publish
publish:
	$(MAKE) clean
	$(MAKE) test
	python setup.py sdist bdist_wheel
	twine upload dist/*

.PHONY: clean
clean:
	rm -rf strudel.scraper.egg-info dist build docs/build
	find -name "*.pyo" -delete
	find -name "*.pyc" -delete
	find -name __pycache__ -delete

.PHONY: html
html:
	sphinx-build -M html "docs" "docs/build"

.PHONY: install_dev
install_dev:
	pip install --user -r requirements.txt
	pip install --user  sphinx sphinx-autobuild
