test:
	nosetests --cover-erase --with-coverage --with-doctest \
        --cover-package=podcastparser

clean:
	find -name '*.pyc' -exec rm '{}' \;
	rm -f .coverage

.PHONY: test clean
