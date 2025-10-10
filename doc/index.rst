.. podcastparser documentation master file, created by
   sphinx-quickstart on Sat Apr 13 11:48:00 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

podcastparser
=============

*podcastparser* is a simple and fast podcast feed parser library in Python.
The two primary users of the library are the `gPodder Podcast Client`_ and
the `gpodder.net web service`_.

The following feed types are supported:

* Really Simple Syndication (`RSS 2.0`_)
* Atom Syndication Format (`RFC 4287`_)

The following specifications are supported:

* `Paged Feeds`_ (`RFC 5005`_)
* `Podlove Simple Chapters`_
* `Podcast Index Podcast Namespace`_

These formats only specify the possible markup elements and attributes. We
recommend that you also read the `Podcast Feed Best Practice`_ guide if you
want to optimize your feeds for best display in podcast clients.

Where times and durations are used, the values are expected to be formatted
either as seconds or as `RFC 2326`_ Normal Play Time (NPT).

.. _gPodder Podcast Client: http://gpodder.org/
.. _gpodder.net web service: http://gpodder.net/
.. _RSS 2.0: http://www.rssboard.org/rss-specification
.. _RFC 4287: https://tools.ietf.org/html/rfc4287
.. _Podcast Feed Best Practice: https://github.com/gpodder/podcast-feed-best-practice/blob/master/podcast-feed-best-practice.md
.. _Paged Feeds: http://podlove.org/paged-feeds/
.. _RFC 5005: https://tools.ietf.org/html/rfc5005
.. _RFC 2326: https://tools.ietf.org/html/rfc2326
.. _Podlove Simple Chapters: http://podlove.org/simple-chapters/
.. _Podcast Index Podcast Namespace: https://github.com/Podcastindex-org/podcast-namespace/blob/main/docs/1.0.md

Example
=======

Using the built-in ``urllib.request`` module from Python 3:

.. code-block:: python

    import podcastparser
    import urllib.request

    feedurl = 'http://example.com/feed.xml'

    parsed = podcastparser.parse(feedurl, urllib.request.urlopen(feedurl))

    # parsed is a dict
    import pprint
    pprint.pprint(parsed)

.. TODO: Show example dict for a parsed feed with all fields


Using `Requests`_:

.. code-block:: python

    import podcastparser
    import requests

    url = 'https://example.net/podcast.atom'

    with requests.get(url, stream=True) as response:
        response.raw.decode_content = True
        parsed = podcastparser.parse(url, response.raw)

    # parsed is a dict
    import pprint
    pprint.pprint(parsed)

.. _Requests: https://requests.readthedocs.io


Supported XML Elements and Attributes
=====================================

For both RSS and Atom feeds, only a subset of elements (those that are relevant
to podcast client applications) is parsed. This section describes which elements
and attributes are parsed and how the contents are interpreted/used.

RSS
---

**rss@xml:base**
    Base URL for all relative links in the RSS file.

**rss/channel**
    Podcast.

**rss/channel/title**
    Podcast title (whitespace is squashed).

**rss/channel/link**
    Podcast website.

**rss/channel/description**
    Podcast description (whitespace is squashed).

**rss/channel/itunes:summary**
    Podcast description (whitespace is squashed).

**rss/channel/image/url**
    Podcast cover art.

**rss/channel/itunes:image**
    Podcast cover art (alternative).

**rss/channel/itunes:type**
    Podcast type (whitespace is squashed).  One of 'episodic' or 'serial'.  

**rss/channel/itunes:keywords**
    Podcast keywords (whitespace is squashed).

**rss/channel/atom:link@rel=payment**
    Podcast payment URL (e.g. Flattr).

**rss/channel/generator**
    A string indicating the program used to generate the channel. (e.g. MightyInHouse Content System v2.3).

**rss/channel/language**
    Podcast language.

**rss/channel/itunes:author**
    The group responsible for creating the show.

**rss/channel/itunes:owner**
    The podcast owner contact information.
    The <itunes:owner> tag information is for administrative communication about the podcast and isn't displayed in Apple Podcasts

**rss/channel/itunes:category**
    The show category information.

**rss/channel/itunes:explicit**
    Indicates whether podcast contains explicit material.

**rss/channel/itunes:new-feed-url**
    The new podcast RSS Feed URL.
    
**rss/channel/podcast:locked**
    If the podcast is currently locked from being transferred.
    
**rss/channel/podcast:funding**
    Funding link for podcast.

**rss/redirect/newLocation**
    The new podcast RSS Feed URL.

**rss/channel/item**
    Episode.

**rss/channel/item/guid**
    Episode unique identifier (GUID), mandatory.

**rss/channel/item/title**
    Episode title (whitespace is squashed).

**rss/channel/item/link**
    Episode website.

**rss/channel/item/description**
    Episode description.
    If it contains html, it's returned as description_html.
    Otherwise it's returned as description (whitespace is squashed).
    See Mozilla's article `Why RSS Content Module is Popular`

**rss/channel/item/itunes:summary**
    Episode description (whitespace is squashed).

**rss/channel/item/itunes:subtitle**
    Episode subtitled / one-line description (whitespace is squashed).

**rss/channel/item/content:encoded**
    Episode description in HTML.
    Best source for description_html.

**rss/channel/item/itunes:duration**
    Episode duration.

**rss/channel/item/pubDate**
    Episode publication date.

**rss/channel/item/atom:link@rel=payment**
    Episode payment URL (e.g. Flattr).

**rss/channel/item/atom:link@rel=enclosure**
    File download URL (@href), size (@length) and mime type (@type).

**rss/channel/item/itunes:image**
    Episode art URL.

**rss/channel/item/media:thumbnail**
    Episode art URL.

**rss/channel/item/media:group/media:thumbnail**
    Episode art URL.

**rss/channel/item/media:content**
    File download URL (@url), size (@fileSize) and mime type (@type).

**rss/channel/item/media:group/media:content**
    File download URL (@url), size (@fileSize) and mime type (@type).

**rss/channel/item/enclosure**
    File download URL (@url), size (@length) and mime type (@type).

**rss/channel/item/psc:chapters**
    Podlove Simple Chapters, version 1.1 and 1.2.

**rss/channel/item/psc:chapters/psc:chapter**
    Chapter entry (@start, @title, @href and @image).

**rss/channel/item/itunes:explicit**
    Indicates whether episode contains explicit material.

**rss/channel/item/itunes:author**
    The group responsible for creating the episode.

**rss/channel/item/itunes:season**
    The season number of the episode.

**rss/channel/item/itunes:episode**
    An episode number.

**rss/channel/item/itunes:episodeType**
    The episode type.
    This flag is used if an episode is a trailer or bonus content.
    
**rss/channel/item/podcast:chapters**
    The url to a JSON file describing the chapters.
    Only the url is added to the data as fetching an external URL would
    be unsafe.
    
**rss/channel/item/podcast:person**
    A person involved in the episode, e.g. host, or guest.
    
**rss/channel/item/podcast:transcript**
    The url for the transcript file associated with this episode.
    


.. _Why RSS Content Module is Popular: https://developer.mozilla.org/en-US/docs/Web/RSS/Article/Why_RSS_Content_Module_is_Popular_-_Including_HTML_Contents

Atom
----

For Atom feeds, *podcastparser* will handle the following elements and
attributes:

**atom:feed**
    Podcast.

**atom:feed/atom:title**
    Podcast title (whitespace is squashed).

**atom:feed/atom:subtitle**
    Podcast description (whitespace is squashed).

**atom:feed/atom:icon**
    Podcast cover art.

**atom:feed/atom:link@href**
    Podcast website.

**atom:feed/atom:entry**
    Episode.

**atom:feed/atom:entry/atom:id**
    Episode unique identifier (GUID), mandatory.

**atom:feed/atom:entry/atom:title**
    Episode title (whitespace is squashed).

**atom:feed/atom:entry/atom:link@rel=enclosure**
    File download URL (@href), size (@length) and mime type (@type).

**atom:feed/atom:entry/atom:link@rel=(self|alternate)**
    Episode website.

**atom:feed/atom:entry/atom:link@rel=payment**
    Episode payment URL (e.g. Flattr).

**atom:feed/atom:entry/atom:content**
    Episode description (in HTML or plaintext).

**atom:feed/atom:entry/atom:published**
    Episode publication date.

**atom:feed/atom:entry/media:thumbnail**
    Episode art URL.

**atom:feed/atom:entry/media:group/media:thumbnail**
    Episode art URL.

**atom:feed/atom:entry/psc:chapters**
    Podlove Simple Chapters, version 1.1 and 1.2.

**atom:feed/atom:entry/psc:chapters/psc:chapter**
    Chapter entry (@start, @title, @href and @image).

The ``podcastparser`` module
============================

.. automodule:: podcastparser
   :members:

Unsupported Namespaces
======================

This is a list of podcast-related XML namespaces that are not yet
supported by podcastparser, but might be in the future.

Chapter Marks
-------------

- `rawvoice RSS`_: Rating, Frequency, Poster, WebM, MP4, Metamark (kind of chapter-like markers)
- `IGOR`_: Chapter Marks

.. _rawvoice RSS: http://www.rawvoice.com/rawvoiceRssModule/
.. _IGOR: http://emonk.net/IGOR

Others
------

- `libSYN RSS Extensions`_: contactPhone, contactEmail, contactTwitter, contactWebsite, wallpaper, pdf, background
- `Comment API`_: Comments to a given item (readable via RSS)
- `MVCB`_: Error Reports To Field (usually a mailto: link)
- `Syndication Module`_: Update period, frequency and base (for skipping updates)
- `Creative Commons RSS`_: Creative commons license for the content
- `Pheedo`_: Original link to website and original link to enclosure (without going through pheedo redirect)
- `WGS84`_: Geo-Coordinates per item
- `Conversations Network`_: Intro duration in milliseconds (for skipping the intro), ratings
- `purl DC Elements`_: dc:creator (author / creator of the podcast, possibly with e-mail address)
- `Tristana`_: tristana:self (canonical URL to feed)
- `Blip`_: Show name, show page, picture, username, language, rating, thumbnail_src, license

.. _libSYN RSS Extensions: http://libsyn.com/rss-extension
.. _Comment API: http://www.wellformedweb.org/CommentAPI/
.. _MVCB: http://webns.net/mvcb/
.. _Syndication Module: http://web.resource.org/rss/1.0/modules/syndication/
.. _Creative Commons RSS: http://backend.userland.com/creativeCommonsRssModule
.. _Pheedo: http://www.pheedo.com/namespace/pheedo
.. _WGS84: http://www.w3.org/2003/01/geo/wgs84_pos#
.. _Conversations Network: http://conversationsnetwork.org/rssNamespace-1.0/
.. _purl DC Elements: http://purl.org/dc/elements/1.1/
.. _Tristana: http://www.tristana.org
.. _Blip: http://blip.tv/dtd/blip/1.0


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

