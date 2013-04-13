test:
	nosetests --cover-erase --with-coverage --with-doctest \
        --cover-package=podcastparser

clean:
	find -name '*.pyc' -exec rm '{}' \;
	rm -f .coverage MANIFEST
	rm -rf dist __pycache__

.PHONY: test clean
