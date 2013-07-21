test:
	nosetests --cover-erase --with-coverage \
	 --cover-package=podcastparser test.py

clean:
	find -name '*.pyc' -exec rm '{}' \;
	rm -f .coverage MANIFEST
	rm -rf dist __pycache__

.PHONY: test clean
