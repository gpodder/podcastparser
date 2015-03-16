PACKAGE := podcastparser

PYTHON ?= python
FIND ?= find
NOSETESTS ?= $(PYTHON) -m nose

help:
	@echo ""
	@echo "$(MAKE) test ......... Run unit tests"
	@echo "$(MAKE) clean ........ Clean build directory"
	@echo "$(MAKE) distclean .... $(MAKE) clean + remove 'dist/'"
	@echo ""

test:
	$(NOSETESTS)

clean:
	$(FIND) . -name '*.pyc' -o -name __pycache__ -exec $(RM) -r '{}' +
	$(RM) -r build
	$(RM) .coverage MANIFEST

distclean: clean
	$(RM) -r dist

.PHONY: help test clean
.DEFAULT: help
