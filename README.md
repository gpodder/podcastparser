podcastparser: Simple, fast and efficient podcast parser
========================================================

The podcast parser project is a library from the gPodder project to provide an
easy and reliable way of parsing RSS- and Atom-based podcast feeds in Python.

See docs in [./doc](./doc) or at [Read the Docs](https://podcastparser.readthedocs.io/en/latest/).

## Automated Tests

To run the unit tests you need [`pytest`](https://docs.pytest.org/).  If you have `pytest` installed, use the `pytest` command in the repository's root directory to run the tests.

## Automated Release to Pypi

To release, update the version number in podcastparser.py, commit and push.

Then create an (annotated) tag and push it.

The GitHub action will publish on pypi.
