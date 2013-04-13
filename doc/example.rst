Example
=======

.. code-block:: python

    import podcastparser
    import urllib

    feedurl = 'http://example.com/feed.xml'

    parsed = podcastparser.parse(feedurl, urllib.urlopen(feedurl))

    # parsed is a dict
    import pprint
    pprint.pprint(parsed)
