# -*- coding: utf-8 -*-
#
# Podcastparser: A simple, fast and efficient podcast parser
# Copyright (c) 2012, 2013, Thomas Perl <m@thp.io>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.
#

""" Simplified, fast RSS parser """

# Will be parsed by setup.py to determine package metadata
__author__ = 'Thomas Perl <m@thp.io>'
__version__ = '0.1.1'
__website__ = 'https://github.com/gpodder/podcastparser'
__license__ = 'ISC License'

from xml import sax

import re
import os
import time

try:
    # Python 2
    import urlparse
except ImportError:
    # Python 3
    from urllib import parse as urlparse

try:
    # Python 2
    from rfc822 import mktime_tz, parsedate_tz
except ImportError:
    # Python 3
    from email.utils import mktime_tz, parsedate_tz

import logging
logger = logging.getLogger(__name__)


class Target:
    WANT_TEXT = False

    def __init__(self, key=None, filter_func=lambda x: x.strip()):
        self.key = key
        self.filter_func = filter_func

    def start(self, handler, attrs):
        pass

    def end(self, handler, text):
        pass


class RSS(Target):
    def start(self, handler, attrs):
        handler.set_base(attrs.get('xml:base'))


class PodcastItem(Target):
    def end(self, handler, text):
        by_published = lambda entry: entry.get('published')
        handler.data['episodes'].sort(key=by_published, reverse=True)
        if handler.max_episodes:
            episodes = handler.data['episodes'][:handler.max_episodes]
            handler.data['episodes'] = episodes


class PodcastAttr(Target):
    WANT_TEXT = True

    def end(self, handler, text):
        handler.set_podcast_attr(self.key, self.filter_func(text))


class PodcastAttrFromHref(Target):
    def start(self, handler, attrs):
        value = attrs.get('href')
        if value:
            handler.set_podcast_attr(self.key, self.filter_func(value))


class PodcastAttrFromPaymentHref(PodcastAttrFromHref):
    def start(self, handler, attrs):
        if attrs.get('rel') == 'payment':
            PodcastAttrFromHref.start(self, handler, attrs)


class EpisodeItem(Target):
    def start(self, handler, attrs):
        handler.add_episode()

    def end(self, handler, text):
        handler.validate_episode()


class EpisodeAttr(Target):
    WANT_TEXT = True

    def end(self, handler, text):
        handler.set_episode_attr(self.key, self.filter_func(text))


class EpisodeGuid(EpisodeAttr):
    def start(self, handler, attrs):
        if attrs.get('isPermaLink', 'true').lower() == 'true':
            handler.set_episode_attr('_guid_is_permalink', True)
        else:
            handler.set_episode_attr('_guid_is_permalink', False)

    def end(self, handler, text):
        def filter_func(guid):
            guid = guid.strip()
            if handler.base and handler.get_episode_attr('_guid_is_permalink'):
                return urlparse.urljoin(handler.base, guid)
            return guid

        self.filter_func = filter_func
        EpisodeAttr.end(self, handler, text)


class EpisodeAttrFromHref(Target):
    def start(self, handler, attrs):
        value = attrs.get('href')
        if value:
            handler.set_episode_attr(self.key, self.filter_func(value))


class EpisodeAttrFromPaymentHref(EpisodeAttrFromHref):
    def start(self, handler, attrs):
        if attrs.get('rel') == 'payment':
            EpisodeAttrFromHref.start(self, handler, attrs)


class Enclosure(Target):
    def __init__(self, file_size_attribute):
        Target.__init__(self)
        self.file_size_attribute = file_size_attribute

    def start(self, handler, attrs):
        url = attrs.get('url')
        if url is None:
            return

        url = parse_url(urlparse.urljoin(handler.url, url))
        file_size = parse_length(attrs.get(self.file_size_attribute))
        mime_type = parse_type(attrs.get('type'))

        handler.add_enclosure(url, file_size, mime_type)

class AtomLink(Target):
    def start(self, handler, attrs):
        rel = attrs.get('rel', 'alternate')
        url = parse_url(urlparse.urljoin(handler.url, attrs.get('href')))
        mime_type = parse_type(attrs.get('type'))
        file_size = parse_length(attrs.get('length', '0'))

        if rel == 'enclosure':
            handler.add_enclosure(url, file_size, mime_type)
        elif mime_type == 'text/html':
            if rel in ('self', 'alternate'):
                if not handler.get_episode_attr('link'):
                    handler.set_episode_attr('link', url)

class AtomContent(Target):
    WANT_TEXT = True

    def __init__(self):
        self._want_content = False

    def start(self, handler, attrs):
        mime_type = attrs.get('type', 'text')
        self._want_content = (mime_type in ('text', 'html'))

    def end(self, handler, text):
        if self._want_content:
            handler.set_episode_attr('description', squash_whitespace(text))

class Namespace():
    # Mapping of XML namespaces to prefixes as used in MAPPING below
    NAMESPACES = {
        # iTunes Podcasting, http://www.apple.com/itunes/podcasts/specs.html
        'http://www.itunes.com/dtds/podcast-1.0.dtd': 'itunes',
        'http://www.itunes.com/DTDs/Podcast-1.0.dtd': 'itunes',

        # Atom Syndication Format, http://tools.ietf.org/html/rfc4287
        'http://www.w3.org/2005/Atom': 'atom',
        'http://www.w3.org/2005/Atom/': 'atom',

        # Media RSS, http://www.rssboard.org/media-rss
        'http://search.yahoo.com/mrss/': 'media',

        # From http://www.rssboard.org/media-rss#namespace-declaration:
        #   "Note: There is a trailing slash in the namespace, although
        #    there has been confusion around this in earlier versions."
        'http://search.yahoo.com/mrss': 'media',
    }

    def __init__(self, attrs, parent=None):
        self.namespaces = self.parse_namespaces(attrs)
        self.parent = parent

    @staticmethod
    def parse_namespaces(attrs):
        """Parse namespace definitions from XML attributes

        >>> expected = {'': 'example'}
        >>> Namespace.parse_namespaces({'xmlns': 'example'}) == expected
        True

        >>> expected = {'foo': 'http://example.com/bar'}
        >>> Namespace.parse_namespaces({'xmlns:foo':
        ...     'http://example.com/bar'}) == expected
        True

        >>> expected = {'': 'foo', 'a': 'bar', 'b': 'bla'}
        >>> Namespace.parse_namespaces({'xmlns': 'foo',
        ...     'xmlns:a': 'bar', 'xmlns:b': 'bla'}) == expected
        True
        """
        result = {}

        for key in attrs.keys():
            if key == 'xmlns':
                result[''] = attrs[key]
            elif key.startswith('xmlns:'):
                result[key[6:]] = attrs[key]

        return result

    def lookup(self, prefix):
        """Look up a namespace URI based on the prefix"""
        current = self
        while current is not None:
            result = current.namespaces.get(prefix, None)
            if result is not None:
                return result
            current = current.parent

        return None

    def map(self, name):
        """Apply namespace prefixes for a given tag

        >>> namespace = Namespace({'xmlns:it':
        ...    'http://www.itunes.com/dtds/podcast-1.0.dtd'}, None)
        >>> namespace.map('it:duration')
        'itunes:duration'
        >>> parent = Namespace({'xmlns:m': 'http://search.yahoo.com/mrss/',
        ...                     'xmlns:x': 'http://example.com/'}, None)
        >>> child = Namespace({}, parent)
        >>> child.map('m:content')
        'media:content'
        >>> child.map('x:y') # Unknown namespace URI
        '!x:y'
        >>> child.map('atom:link') # Undefined prefix
        'atom:link'
        """
        if ':' not in name:
            # <duration xmlns="http://..."/>
            namespace = ''
            namespace_uri = self.lookup(namespace)
        else:
            # <itunes:duration/>
            namespace, name = name.split(':', 1)
            namespace_uri = self.lookup(namespace)
            if namespace_uri is None:
                # Use of "itunes:duration" without xmlns:itunes="..."
                logger.warn('No namespace defined for "%s:%s"', namespace,
                            name)
                return '%s:%s' % (namespace, name)

        if namespace_uri is not None:
            prefix = self.NAMESPACES.get(namespace_uri)
            if prefix is None and namespace:
                # Proper use of namespaces, but unknown namespace
                logger.warn('Unknown namespace: %s', namespace_uri)
                # We prefix the tag name here to make sure that it does not
                # match any other tag below if we can't recognize the namespace
                name = '!%s:%s' % (namespace, name)
            else:
                name = '%s:%s' % (prefix, name)

        return name


def file_basename_no_extension(filename):
    """ Returns filename without extension

    >>> file_basename_no_extension('/home/me/file.txt')
    'file'

    >>> file_basename_no_extension('file')
    'file'
    """
    base = os.path.basename(filename)
    name, extension = os.path.splitext(base)
    return name


def squash_whitespace(text):
    """ Combine multiple whitespaces into one, trim trailing/leading spaces

    >>> squash_whitespace(' some\t   text  with a    lot of   spaces ')
    'some text with a lot of spaces'
    """
    return re.sub('\s+', ' ', text.strip())


def parse_time(value):
    """Parse a time string into seconds

    >>> parse_time('0')
    0
    >>> parse_time('128')
    128
    >>> parse_time('00:00')
    0
    >>> parse_time('00:00:00')
    0
    >>> parse_time('00:20')
    20
    >>> parse_time('00:00:20')
    20
    >>> parse_time('01:00:00')
    3600
    >>> parse_time(' 03:02:01')
    10921
    >>> parse_time('61:08')
    3668
    >>> parse_time('25:03:30 ')
    90210
    >>> parse_time('25:3:30')
    90210
    >>> parse_time('61.08')
    3668
    >>> parse_time(' ')
    0
    """
    value = value.strip()

    if value == '':
        return 0

    m = re.match(r'(\d+)[:.](\d\d?)[:.](\d\d?)', value)
    if m:
        hours, minutes, seconds = m.groups()
        return (int(hours) * 60 + int(minutes)) * 60 + int(seconds)

    m = re.match(r'(\d+)[:.](\d\d?)', value)
    if m:
        minutes, seconds = m.groups()
        return int(minutes) * 60 + int(seconds)

    return int(value)


def parse_url(text):
    return normalize_feed_url(text.strip())


def parse_length(text):
    """ Parses a file length

    >>> parse_length(None)
    -1

    >>> parse_length('0')
    -1

    >>> parse_length('unknown')
    -1

    >>> parse_length('100')
    100
    """

    if text is None:
        return -1

    try:
        return int(text.strip()) or -1
    except ValueError:
        return -1


def parse_type(text):
    """ "normalize" a mime type

    >>> parse_type('text/plain')
    'text/plain'

    >>> parse_type('text')
    'application/octet-stream'

    >>> parse_type('')
    'application/octet-stream'

    >>> parse_type(None)
    'application/octet-stream'
    """

    if not text or '/' not in text:
        # Maemo bug 10036
        return 'application/octet-stream'

    return text


def parse_pubdate(text):
    """Parse a date string into a Unix timestamp

    >>> parse_pubdate('Fri, 21 Nov 1997 09:55:06 -0600')
    880127706

    >>> parse_pubdate('')
    0

    >>> parse_pubdate('unknown')
    0
    """
    if not text:
        return 0

    parsed = parsedate_tz(text)
    if parsed is not None:
        return int(mktime_tz(parsed))

    # TODO: Fully RFC 3339-compliant parsing (w/ timezone)
    try:
        parsed = time.strptime(text[:19], '%Y-%m-%dT%H:%M:%S')
        if parsed is not None:
            return int(time.mktime(parsed))
    except Exception:
        pass

    logger.error('Cannot parse date: %s', repr(text))
    return 0


MAPPING = {
    'rss': RSS(),
    'rss/channel': PodcastItem(),
    'rss/channel/title': PodcastAttr('title', squash_whitespace),
    'rss/channel/link': PodcastAttr('link'),
    'rss/channel/description': PodcastAttr('description', squash_whitespace),
    'rss/channel/image/url': PodcastAttr('cover_url'),
    'rss/channel/itunes:image': PodcastAttrFromHref('cover_url'),
    'rss/channel/atom:link': PodcastAttrFromPaymentHref('payment_url'),

    'rss/channel/item': EpisodeItem(),
    'rss/channel/item/guid': EpisodeGuid('guid'),
    'rss/channel/item/title': EpisodeAttr('title', squash_whitespace),
    'rss/channel/item/link': EpisodeAttr('link'),
    'rss/channel/item/description': EpisodeAttr('description',
                                                squash_whitespace),
    # Alternatives for description: itunes:summary, itunes:subtitle,
    # content:encoded
    'rss/channel/item/itunes:duration': EpisodeAttr('total_time', parse_time),
    'rss/channel/item/pubDate': EpisodeAttr('published', parse_pubdate),
    'rss/channel/item/atom:link': EpisodeAttrFromPaymentHref('payment_url'),

    'rss/channel/item/media:content': Enclosure('fileSize'),
    'rss/channel/item/enclosure': Enclosure('length'),

    # Basic support for Atom feeds
    'atom:feed': PodcastItem(),
    'atom:feed/atom:title': PodcastAttr('title', squash_whitespace),
    'atom:feed/atom:subtitle': PodcastAttr('description', squash_whitespace),
    'atom:feed/atom:icon': PodcastAttr('cover_url'),
    'atom:feed/atom:link': PodcastAttrFromHref('link'),
    'atom:feed/atom:entry': EpisodeItem(),
    'atom:feed/atom:entry/atom:id': EpisodeAttr('guid'),
    'atom:feed/atom:entry/atom:title': EpisodeAttr('title', squash_whitespace),
    'atom:feed/atom:entry/atom:link': AtomLink(),
    'atom:feed/atom:entry/atom:content': AtomContent(),
    'atom:feed/atom:entry/atom:published': EpisodeAttr('published', parse_pubdate),
}


class PodcastHandler(sax.handler.ContentHandler):
    def __init__(self, url, max_episodes):
        self.url = url
        self.max_episodes = max_episodes
        self.base = None
        self.text = None
        self.episodes = []
        self.data = {
            'title': file_basename_no_extension(url),
            'episodes': self.episodes
        }
        self.path_stack = []
        self.namespace = None

    def set_base(self, base):
        self.base = base

    def set_podcast_attr(self, key, value):
        self.data[key] = value

    def set_episode_attr(self, key, value):
        self.episodes[-1][key] = value

    def get_episode_attr(self, key, default=None):
        return self.episodes[-1].get(key, default)

    def add_episode(self):
        self.episodes.append({
            # title
            'description': '',
            # url
            'published': 0,
            # guid
            'link': '',
            'total_time': 0,
            'payment_url': None,
            'enclosures': [],
            '_guid_is_permalink': False,
        })

    def validate_episode(self):
        entry = self.episodes[-1]

        if 'guid' not in entry:
            if entry.get('link'):
                # Link element can serve as GUID
                entry['guid'] = entry['link']
            else:
                if len(entry['enclosures']) != 1:
                    # Multi-enclosure feeds MUST have a GUID
                    self.episodes.pop()
                    return

                # Maemo bug 12073
                entry['guid'] = entry['enclosures'][0]['url']

        if 'title' not in entry:
            if len(entry['enclosures']) != 1:
                self.episodes.pop()
                return

            entry['title'] = file_basename_no_extension(
                entry['enclosures'][0]['url'])

        if not entry.get('link') and entry.get('_guid_is_permalink'):
            entry['link'] = entry['guid']

        del entry['_guid_is_permalink']

    def add_enclosure(self, url, file_size, mime_type):
        self.episodes[-1]['enclosures'].append({
            'url': url,
            'file_size': file_size,
            'mime_type': mime_type,
        })

    def startElement(self, name, attrs):
        self.namespace = Namespace(attrs, self.namespace)
        self.path_stack.append(self.namespace.map(name))

        target = MAPPING.get('/'.join(self.path_stack))
        if target is not None:
            target.start(self, attrs)
            if target.WANT_TEXT:
                self.text = []

    def characters(self, chars):
        if self.text is not None:
            self.text.append(chars)

    def endElement(self, name):
        target = MAPPING.get('/'.join(self.path_stack))
        if target is not None:
            content = ''.join(self.text) if self.text is not None else ''
            target.end(self, content)
            self.text = None

        if self.namespace is not None:
            self.namespace = self.namespace.parent
        self.path_stack.pop()


def parse(url, stream, max_episodes=0):
    """Parse a podcast feed from the given URL and stream

    :param url: the URL of the feed. Will be used to resolve relative links
    :param stream: file-like object containing the feed content
    :param max_episodes: maximum number of episodes to return. 0 (default)
                         means no limit
    :returns: a dict with the parsed contents of the feed
    """
    handler = PodcastHandler(url, max_episodes)
    sax.parse(stream, handler)
    return handler.data


def normalize_feed_url(url):
    """
    Converts any URL to http:// or ftp:// so that it can be
    used with "wget". If the URL cannot be converted (invalid
    or unknown scheme), "None" is returned.

    This will also normalize feed:// and itpc:// to http://.

    >>> normalize_feed_url('itpc://example.org/podcast.rss')
    'http://example.org/podcast.rss'

    If no URL scheme is defined (e.g. "curry.com"), we will
    simply assume the user intends to add a http:// feed.

    >>> normalize_feed_url('curry.com')
    'http://curry.com/'

    It will also take care of converting the domain name to
    all-lowercase (because domains are not case sensitive):

    >>> normalize_feed_url('http://Example.COM/')
    'http://example.com/'

    Some other minimalistic changes are also taken care of,
    e.g. a ? with an empty query is removed:

    >>> normalize_feed_url('http://example.org/test?')
    'http://example.org/test'

    Leading and trailing whitespace is removed

    >>> normalize_feed_url(' http://example.com/podcast.rss ')
    'http://example.com/podcast.rss'

    Incomplete (too short) URLs are not accepted

    >>> normalize_feed_url('http://') is None
    True

    Unknown protocols are not accepted

    >>> normalize_feed_url('gopher://gopher.hprc.utoronto.ca/file.txt') is None
    True
    """
    url = url.strip()
    if not url or len(url) < 8:
        return None

    # Assume HTTP for URLs without scheme
    if not '://' in url:
        url = 'http://' + url

    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)

    # Schemes and domain names are case insensitive
    scheme, netloc = scheme.lower(), netloc.lower()

    # Normalize empty paths to "/"
    if path == '':
        path = '/'

    # feed://, itpc:// and itms:// are really http://
    if scheme in ('feed', 'itpc', 'itms'):
        scheme = 'http'

    if scheme not in ('http', 'https', 'ftp', 'file'):
        return None

    # urlunsplit might return "a slighty different, but equivalent URL"
    return urlparse.urlunsplit((scheme, netloc, path, query, fragment))
