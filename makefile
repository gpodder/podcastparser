PACKAGE := podcastparser

NOSEOPTIONS := --cover-erase --with-coverage --cover-package=$(PACKAGE) --with-doctest

PYTHON ?= python
FIND ?= find
NOSE = $(shell which nosetests)
NOSETESTS ?= $(PYTHON) $(NOSE)

help:
	@echo ""
	@echo "$(MAKE) test ......... Run unit tests"
	@echo "$(MAKE) clean ........ Clean build directory"
	@echo "$(MAKE) distclean .... $(MAKE) clean + remove 'dist/'"
	@echo ""

test:
	$(NOSETESTS) $(NOSEOPTIONS)

clean:
	$(FIND) . -name '*.pyc' -o -name __pycache__ -exec $(RM) -r '{}' +
	$(RM) -r build
	$(RM) .coverage MANIFEST

distclean: clean
	$(RM) -r dist

.PHONY: help test clean
.DEFAULT: help
