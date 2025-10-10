# -*- coding: utf-8 -*-
#
# Podcastparser: A simple, fast and efficient podcast parser
# Copyright (c) 2012, 2013, 2014, 2018, 2020 Thomas Perl <m@thp.io>
# Copyright (c) 2016, 2017, 2018, 2019, 2020 Eric Le Lay <elelay@macports.org>
# Copyright (c) 2020 E.S. Rosenberg <es.rosenberg+openu@gmail.com>
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
__version__ = '0.6.11'
__website__ = 'http://gpodder.org/podcastparser/'
__license__ = 'ISC License'

from xml import sax

import re
import os
import time

from html.entities import entitydefs

from urllib import parse as urlparse
from email.utils import mktime_tz, parsedate_tz

import logging
logger = logging.getLogger(__name__)


class Target(object):
    WANT_TEXT = False

    def __init__(self, key=None, filter_func=lambda x: x.strip(), overwrite=True):
        self.key = key
        self.filter_func = filter_func
        self.overwrite = overwrite

    def start(self, handler, attrs):
        pass

    def end(self, handler, text):
        pass


class RSS(Target):
    def start(self, handler, attrs):
        if 'xml:base' in attrs.keys():
            handler.set_base(attrs.get('xml:base'))


class PodcastItem(Target):
    def end(self, handler, text):
        by_published = lambda entry: entry.get('published')
        order = 'type' not in handler.data or handler.data['type'] != 'serial'
        handler.data['episodes'].sort(key=by_published, reverse=order)
        if handler.max_episodes:
            episodes = handler.data['episodes'][:handler.max_episodes]
            handler.data['episodes'] = episodes


class PodcastAttr(Target):
    WANT_TEXT = True

    def end(self, handler, text):
        if not self.overwrite and handler.get_podcast_attr(self.key):
            return
        handler.set_podcast_attr(self.key, self.filter_func(text))

class PodcastAttrList(Target):
    WANT_TEXT = True

    def end(self, handler, text):
        if not self.overwrite and handler.get_podcast_attr(self.key):
            return
        handler.set_podcast_attr(self.key, self.filter_func(text).split(', '))


class PodcastAttrType(Target):
    WANT_TEXT = True

    def end(self, handler, text):
        if not self.overwrite and handler.get_podcast_attr(self.key):
            return
        value = self.filter_func(text)
        if value in ('episodic', 'serial'):
            handler.set_podcast_attr(self.key, value)


class PodcastAttrRelativeLink(PodcastAttr):
    def end(self, handler, text):
        text = urlparse.urljoin(handler.base, text.strip())
        super(PodcastAttrRelativeLink, self).end(handler, text)


class PodcastAttrFromHref(Target):
    ATTRIBUTE = 'href'
    
    def start(self, handler, attrs):
        if not self.overwrite and handler.get_podcast_attr(self.key):
            return
        value = attrs.get(self.ATTRIBUTE)
        if value:
            value = urlparse.urljoin(handler.base, value)
            handler.set_podcast_attr(self.key, self.filter_func(value))


class PodcastAttrFromUrl(PodcastAttrFromHref):
    ATTRIBUTE = 'url'
    

class EpisodeItem(Target):
    def start(self, handler, attrs):
        handler.add_episode()

    def end(self, handler, text):
        handler.validate_episode()


class EpisodeAttr(Target):
    WANT_TEXT = True

    def end(self, handler, text):
        if not self.overwrite and handler.get_episode_attr(self.key):
            return
        text = self.filter_func(text)
        if text != '' or handler.get_episode_attr(self.key) is None:
            handler.set_episode_attr(self.key, text)


class EpisodeAttrRelativeLink(EpisodeAttr):
    def end(self, handler, text):
        text = urlparse.urljoin(handler.base, text)
        super(EpisodeAttrRelativeLink, self).end(handler, text)


class EpisodeGuid(EpisodeAttr):
    def start(self, handler, attrs):
        if attrs.get('isPermaLink', 'true').lower() == 'true':
            handler.set_episode_attr('_guid_is_permalink', True)
        else:
            handler.set_episode_attr('_guid_is_permalink', False)

    def end(self, handler, text):
        def filter_func(guid):
            guid = guid.strip()
            if handler.get_episode_attr('_guid_is_permalink'):
                return urlparse.urljoin(handler.base, guid)
            return guid

        self.filter_func = filter_func
        EpisodeAttr.end(self, handler, text)


class EpisodeAttrFromHref(Target):
    ATTRIBUTE = 'href'

    def start(self, handler, attrs):
        value = attrs.get(self.ATTRIBUTE)
        if value:
            value = urlparse.urljoin(handler.base, value)
            handler.set_episode_attr(self.key, self.filter_func(value))


class EpisodeAttrFromUrl(EpisodeAttrFromHref):
    ATTRIBUTE = 'url'


class EpisodeAttrSeason(EpisodeAttr):
    def end(self, handler, text):
        try:
            episode_season = int(text)
        except ValueError:
            episode_season = 0
        handler.set_episode_attr(self.key, episode_season)


class EpisodeAttrNumber(EpisodeAttr):
    def end(self, handler, text):
        value = self.filter_func(text)
        try:
            episode_num = int(value)
        except ValueError:
            return
        if episode_num > 0:
            handler.set_episode_attr(self.key, episode_num)


class EpisodeAttrType(EpisodeAttr):
    def end(self, handler, text):
        value = self.filter_func(text).lower()
        if value in ('full', 'trailer', 'bonus'):
            handler.set_episode_attr(self.key, value)


class Enclosure(Target):
    def __init__(self, file_size_attribute):
        Target.__init__(self)
        self.file_size_attribute = file_size_attribute

    def start(self, handler, attrs):
        url = attrs.get('url')
        if url is None:
            return

        url = parse_url(urlparse.urljoin(handler.base, url.lstrip()))
        file_size = parse_length(attrs.get(self.file_size_attribute))
        mime_type = parse_type(attrs.get('type'))

        handler.add_enclosure(url, file_size, mime_type)


class AtomLink(Target):
    def start(self, handler, attrs):
        rel = attrs.get('rel', 'alternate')
        url = parse_url(urlparse.urljoin(handler.base, attrs.get('href')))
        mime_type = parse_type(attrs.get('type', 'text/html'))
        file_size = parse_length(attrs.get('length', '0'))

        if rel == 'enclosure':
            handler.add_enclosure(url, file_size, mime_type)
        elif rel == 'payment':
            handler.set_episode_attr('payment_url', url)
        elif mime_type == 'text/html':
            if rel in ('self', 'alternate'):
                if not handler.get_episode_attr('link'):
                    handler.set_episode_attr('link', url)


class PodcastAtomLink(AtomLink):
    def start(self, handler, attrs):
        rel = attrs.get('rel', 'alternate')
        url = parse_url(urlparse.urljoin(handler.base, attrs.get('href')))
        mime_type = parse_type(attrs.get('type'))

        # RFC 5005 (http://podlove.org/paged-feeds/)
        if rel == 'first':
            handler.set_podcast_attr('paged_feed_first', url)
        elif rel == 'next':
            handler.set_podcast_attr('paged_feed_next', url)
        elif rel == 'payment':
            handler.set_podcast_attr('payment_url', url)
        elif mime_type == 'text/html':
            if rel in ('self', 'alternate'):
                handler.set_podcast_attr('link', url)


class AtomContent(Target):
    WANT_TEXT = True

    def __init__(self):
        self._want_content = False

    def start(self, handler, attrs):
        self._mime_type = attrs.get('type', 'text')

    def end(self, handler, text):
        if self._mime_type == 'html':
            handler.set_episode_attr('description_html', text)
        elif self._mime_type == 'text':
            handler.set_episode_attr('description', squash_whitespace_not_nl(text))


class RSSItemDescription(Target):
    """
    RSS 2.0 almost encourages to put html content in item/description
    but content:encoded is the better source of html content and itunes:summary
    is known to contain the short textual description of the item.
    So use a heuristic to attribute text to either description or description_html,
    without overriding existing values.
    """
    WANT_TEXT = True

    def __init__(self):
        self._want_content = False

    def end(self, handler, text):
        if is_html(text):
            if not handler.get_episode_attr('description_html'):
                handler.set_episode_attr('description_html', text.strip())
        elif not handler.get_episode_attr('description'):
            # don't overwrite itunes:summary?
            handler.set_episode_attr('description', squash_whitespace_not_nl(text))


class PodloveChapters(Target):
    SUPPORTED_VERSIONS = ('1.1', '1.2')

    def start(self, handler, attrs):
        version = attrs.get('version', '1.1')
        if version not in PodloveChapters.SUPPORTED_VERSIONS:
            logger.warning('Possible incompatible chapters version: %s', version)


class PodloveChapter(Target):
    def start(self, handler, attrs):
        # Both the start and title attributes are mandatory
        if attrs.get('start') is None or attrs.get('title') is None:
            logger.warning('Invalid chapter (missing start and/or and title)')
            return

        chapter = {
            'start': parse_time(attrs.get('start')),
            'title': attrs.get('title'),
        }

        for optional in ('href', 'image'):
            value = attrs.get(optional)
            if value:
                chapter[optional] = value

        handler.get_episode_attr('chapters').append(chapter)
        
        
class EpisodePersonAttr(Target):
    WANT_TEXT = True
         
    def start(self, handler, attrs):
        if not handler.get_episode_attr("persons"):
            handler.add_episode_persons()
        person = {
            "name": None,
            "role": "host",
            "group": "cast",
            "href": None,
            "img": None,
        }
        for optional in ("group", "role", "href", "img"):
            value = attrs.get(optional)
            if value:
                if optional in ("role", "group"):
                    value = value.lower()
                person[optional] = value
        handler.append_episode_person(person)
    
    def end(self, handler, text):
        handler.get_episode_attr("persons")[-1]["name"] = text


class ItunesOwnerAttr(Target):
    WANT_TEXT = True

    def end(self, handler, text):
        if not self.overwrite and handler.get_episode_attr(self.key):
            return
        handler.append_itunes_owner(self.key, self.filter_func(text))


class ItunesCategoryAttr(Target):
    def start(self, handler, attrs):
        # Let's use an empty string as a fallback for first-level categories
        # in case there is a valid sub-category.
        value = attrs.get('text', '')
        handler.append_itunes_category(self.key, self.filter_func(value))


class ItunesSubCategoryAttr(Target):
    def start(self, handler, attrs):
        value = attrs.get('text')
        if not value:
            return
        handler.append_itunes_subcategory(self.key, self.filter_func(value))


class ItunesOwnerItem(Target):
    def start(self, handler, attrs):
        handler.add_itunes_owner()


class PodcastAttrExplicit(Target):
    WANT_TEXT = True
    _VALUES_MAPPER = {
        'yes': True,
        'explicit': True,
        'true': True,
        'no': False,
        'clean': False,
        'false': False,
    }

    def end(self, handler, text):
        value = self.filter_func(text).lower()
        if value in self._VALUES_MAPPER:
            handler.set_podcast_attr(self.key, self._VALUES_MAPPER[value])


class EpisodeAttrExplicit(PodcastAttrExplicit):
    def end(self, handler, text):
        value = self.filter_func(text).lower()
        if value in self._VALUES_MAPPER:
            handler.set_episode_attr(self.key, self._VALUES_MAPPER[value])


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

        # Podlove Simple Chapters, http://podlove.org/simple-chapters
        'http://podlove.org/simple-chapters': 'psc',
        'http://podlove.org/simple-chapters/': 'psc',

        # Purl RSS Content module
        'http://purl.org/rss/1.0/modules/content/': 'content',
        
        # Podcast Index podcast namespace
        # https://github.com/Podcastindex-org/podcast-namespace/blob/main/docs/1.0.md
        'https://github.com/Podcastindex-org/podcast-namespace/blob/main/docs/1.0.md': 'podcast',
        'https://github.com/podcastindex-org/podcast-namespace/blob/main/docs/1.0.md': 'podcast',
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
                logger.warning('No namespace defined for "%s:%s"', namespace,
                            name)
                return '%s:%s' % (namespace, name)

        if namespace_uri is not None:
            prefix = self.NAMESPACES.get(namespace_uri)
            if prefix is None and namespace:
                # Proper use of namespaces, but unknown namespace
                # logger.warning('Unknown namespace: %s', namespace_uri)
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
    return re.sub(r'\s+', ' ', text.strip())


def squash_whitespace_not_nl(text):
    """ Like squash_whitespace, but don't squash linefeeds and carriage returns

    >>> squash_whitespace_not_nl(' linefeeds\\ncarriage\\r  returns')
    'linefeeds\\ncarriage\\r returns'
    """
    return re.sub(r'[^\S\r\n]+', ' ', text.strip())


def parse_time(value):
    """Parse a time string into seconds

    See RFC2326, 3.6 "Normal Play Time" (HH:MM:SS.FRACT)

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
    61
    >>> parse_time('01:02:03.500')
    3723
    >>> parse_time(' ')
    0
    """
    value = value.strip()

    if value == '':
        return 0

    hours = minutes = seconds = fraction = 0
    parsed = False

    m = re.match(r'(\d+)[:](\d\d?)[:](\d\d?)([.]\d+)?$', value)
    if not parsed and m:
        hours, minutes, seconds, fraction = m.groups()
        fraction = float(fraction or 0.0)
        parsed = True

    m = re.match(r'(\d+)[:](\d\d?)([.]\d+)?$', value)
    if not parsed and m:
        minutes, seconds, fraction = m.groups()
        fraction = float(fraction or 0.0)
        parsed = True

    m = re.match(r'(\d+)([.]\d+)?$', value)
    if not parsed and m:
        seconds, fraction = m.groups()
        fraction = float(fraction or 0.0)
        parsed = True

    if not parsed:
        try:
            seconds = int(value)
        except ValueError:
            logger.warning('Could not parse time value: "%s"', value)
            return 0

    return (int(hours) * 60 + int(minutes)) * 60 + int(seconds)


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

    >>> parse_pubdate('2003-12-13T00:00:00+02:00')
    1071266400

    >>> parse_pubdate('2003-12-13T18:30:02Z')
    1071340202

    >>> parse_pubdate('Mon, 02 May 1960 09:05:01 +0100')
    -305049299

    >>> parse_pubdate('')
    0

    >>> parse_pubdate('unknown')
    0
    """
    if not text:
        return 0

    parsed = parsedate_tz(text)
    if parsed is not None:
        try:
            pubtimeseconds = int(mktime_tz(parsed))
            return pubtimeseconds
        except(OverflowError, ValueError):
            logger.warning('bad pubdate %s is before epoch or after end of time (2038)', parsed)
            return 0

    try:
        parsed = time.strptime(text[:19], '%Y-%m-%dT%H:%M:%S')
        if parsed is not None:
            m = re.match(r'^(?:Z|([+-])([0-9]{2})[:]([0-9]{2}))$', text[19:])
            if m:
                parsed = list(iter(parsed))
                if m.group(1):
                    offset = 3600 * int(m.group(2)) + 60 * int(m.group(3))
                    if m.group(1) == '-':
                        offset = 0 - offset
                else:
                    offset = 0
                parsed.append(offset)
                return int(mktime_tz(tuple(parsed)))
            else:
                return int(time.mktime(parsed))
    except Exception:
        pass

    logger.error('Cannot parse date: %s', repr(text))
    return 0


# If you modify the mapping, don't forget to also update the documentation
# section "Supported XML Elements and Attributes" in doc/index.rst
MAPPING = {
    'rss': RSS(),
    'rss/channel': PodcastItem(),
    'rss/channel/title': PodcastAttr('title', squash_whitespace),
    'rss/channel/link': PodcastAttrRelativeLink('link'),
    'rss/channel/description': PodcastAttr('description', squash_whitespace_not_nl),
    'rss/channel/itunes:summary': PodcastAttr('description', squash_whitespace_not_nl, overwrite=False),
    'rss/channel/podcast:funding': PodcastAttrFromUrl('funding_url'),
    'rss/channel/podcast:locked': PodcastAttrExplicit('import_prohibited'),
    'rss/channel/image/url': PodcastAttrRelativeLink('cover_url'),
    'rss/channel/itunes:image': PodcastAttrFromHref('cover_url'),
    'rss/channel/itunes:type': PodcastAttrType('type', squash_whitespace),
    'rss/channel/atom:link': PodcastAtomLink(),
    'rss/channel/generator': PodcastAttr('generator', squash_whitespace),
    'rss/channel/language': PodcastAttr('language', squash_whitespace),

    'rss/channel/itunes:category': ItunesCategoryAttr('itunes_categories'),
    'rss/channel/itunes:category/itunes:category': ItunesSubCategoryAttr('itunes_categories'),
    'rss/channel/itunes:category/itunes:category/itunes:category': ItunesSubCategoryAttr('itunes_categories'),

    'rss/channel/itunes:author': PodcastAttr('itunes_author', squash_whitespace),
    'rss/channel/itunes:owner': ItunesOwnerItem('itunes_owner', squash_whitespace),
    'rss/channel/itunes:explicit': PodcastAttrExplicit('explicit', squash_whitespace),
    'rss/channel/itunes:new-feed-url': PodcastAttr('new_url', squash_whitespace),
    'rss/channel/itunes:keywords': PodcastAttrList('itunes_keywords', squash_whitespace),
    'rss/redirect/newLocation': PodcastAttr('new_url', squash_whitespace),

    'rss/channel/itunes:owner/itunes:email': ItunesOwnerAttr('email', squash_whitespace),
    'rss/channel/itunes:owner/itunes:name': ItunesOwnerAttr('name', squash_whitespace),

    'rss/channel/item': EpisodeItem(),
    'rss/channel/item/guid': EpisodeGuid('guid'),
    'rss/channel/item/title': EpisodeAttr('title', squash_whitespace),
    'rss/channel/item/link': EpisodeAttrRelativeLink('link'),
    'rss/channel/item/description': RSSItemDescription(),
    'rss/channel/item/itunes:summary': EpisodeAttr('description', squash_whitespace_not_nl),
    'rss/channel/item/media:description': EpisodeAttr('description', squash_whitespace_not_nl),
    'rss/channel/item/itunes:subtitle': EpisodeAttr('subtitle', squash_whitespace),
    'rss/channel/item/content:encoded': EpisodeAttr('description_html'),
    'rss/channel/item/itunes:duration': EpisodeAttr('total_time', parse_time),
    'rss/channel/item/pubDate': EpisodeAttr('published', parse_pubdate),
    'rss/channel/item/atom:link': AtomLink(),
    'rss/channel/item/itunes:explicit': EpisodeAttrExplicit('explicit', squash_whitespace),
    'rss/channel/item/itunes:author': EpisodeAttr('itunes_author', squash_whitespace),
    'rss/channel/item/itunes:season': EpisodeAttrSeason('season', squash_whitespace),
    'rss/channel/item/itunes:episode': EpisodeAttrNumber('number', squash_whitespace),
    'rss/channel/item/itunes:episodeType': EpisodeAttrType('type', squash_whitespace),

    'rss/channel/item/itunes:image': EpisodeAttrFromHref('episode_art_url'),
    'rss/channel/item/media:thumbnail': EpisodeAttrFromUrl('episode_art_url'),
    'rss/channel/item/media:group/media:thumbnail': EpisodeAttrFromUrl('episode_art_url'),

    'rss/channel/item/media:content': Enclosure('fileSize'),
    'rss/channel/item/media:group/media:content': Enclosure('fileSize'),
    'rss/channel/item/enclosure': Enclosure('length'),
    'rss/channel/item/psc:chapters': PodloveChapters(),
    'rss/channel/item/psc:chapters/psc:chapter': PodloveChapter(),
    'rss/channel/item/podcast:transcript': EpisodeAttrFromUrl("transcript_url"),
    'rss/channel/item/podcast:chapters': EpisodeAttrFromUrl("chapters_json_url"),
    'rss/channel/item/podcast:person': EpisodePersonAttr(),

    # Basic support for Atom feeds
    'atom:feed': PodcastItem(),
    'atom:feed/atom:title': PodcastAttr('title', squash_whitespace),
    'atom:feed/atom:subtitle': PodcastAttr('description', squash_whitespace_not_nl),
    'atom:feed/atom:icon': PodcastAttrRelativeLink('cover_url'),
    'atom:feed/atom:link': PodcastAtomLink(),
    'atom:feed/atom:entry': EpisodeItem(),
    'atom:feed/atom:entry/atom:id': EpisodeAttr('guid'),
    'atom:feed/atom:entry/atom:title': EpisodeAttr('title', squash_whitespace),
    'atom:feed/atom:entry/atom:link': AtomLink(),
    'atom:feed/atom:entry/atom:content': AtomContent(),
    'atom:feed/atom:entry/content:encoded': EpisodeAttr('description_html'),
    'atom:feed/atom:entry/atom:published': EpisodeAttr('published', parse_pubdate),
    'atom:feed/atom:entry/atom:updated': EpisodeAttr('published', parse_pubdate, overwrite=False),
    'atom:feed/atom:entry/media:group/media:description': EpisodeAttr('description', squash_whitespace_not_nl),

    'atom:feed/atom:entry/media:thumbnail': EpisodeAttrFromUrl('episode_art_url'),
    'atom:feed/atom:entry/media:group/media:thumbnail': EpisodeAttrFromUrl('episode_art_url'),

    'atom:feed/atom:entry/psc:chapters': PodloveChapters(),
    'atom:feed/atom:entry/psc:chapters/psc:chapter': PodloveChapter(),
}

# Derive valid root elements from the supported MAPPINGs
VALID_ROOTS = set(path.split('/')[0] for path in MAPPING.keys())


class FeedParseError(sax.SAXParseException, ValueError):
    """
    Exception raised when asked to parse an invalid feed

    This exception allows users of this library to catch exceptions
    without having to import the XML parsing library themselves.
    """
    pass


class PodcastHandler(sax.handler.ContentHandler):
    def __init__(self, url, max_episodes):
        self.url = url
        self.max_episodes = max_episodes
        self.base = url
        self.text = None
        self.episodes = []
        self.data = {
            'title': file_basename_no_extension(url),
            'episodes': self.episodes,
        }
        self.path_stack = []
        self.namespace = None

    def set_base(self, base):
        self.base = base

    def set_podcast_attr(self, key, value):
        self.data[key] = value

    def get_podcast_attr(self, key, default=None):
        return self.data.get(key, default)

    def set_episode_attr(self, key, value):
        self.episodes[-1][key] = value

    def get_episode_attr(self, key, default=None):
        return self.episodes[-1].get(key, default)
        
    def add_episode_persons(self):
        self.episodes[-1]['persons'] = []
        
    def append_episode_person(self, value):
        self.episodes[-1]['persons'].append(value)

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
            'chapters': [],
        })

    def validate_episode(self):
        entry = self.episodes[-1]

        if len(entry['chapters']) == 0:
            del entry['chapters']

        # Ensures `description` does not contain HTML
        if is_html(entry['description']):
            if 'description_html' not in entry:
                entry['description_html'] = entry['description']
            entry['description'] = ''

        # Sets `description` to stripped `description_html` when empty
        if 'description_html' in entry and not entry['description']:
            entry['description'] = remove_html_tags(entry['description_html'])

        if 'guid' not in entry:
            if entry.get('link'):
                # Link element can serve as GUID
                entry['guid'] = entry['link']
            else:
                if len(set(enclosure['url'] for enclosure in entry['enclosures'])) != 1:
                    # Multi-enclosure feeds MUST have a GUID or the same URL for all enclosures
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

    def add_itunes_owner(self):
        self.data['itunes_owner'] = {}

    def append_itunes_owner(self, key, value):
        self.data['itunes_owner'][key] = value

    def add_itunes_categories(self):
        self.data['itunes_categories'] = []

    def append_itunes_category(self, key, value):
        self.data.setdefault('itunes_categories', []).append([value])

    def append_itunes_subcategory(self, key, value):
        entry = self.data['itunes_categories'][-1]
        entry.append(value)

    def startElement(self, name, attrs):
        self.namespace = Namespace(attrs, self.namespace)
        name = self.namespace.map(name)
        if not self.path_stack and name not in VALID_ROOTS:
            raise FeedParseError(
                msg='Unsupported feed type: {}'.format(name),
                exception=None,
                locator=self._locator,
            )
        self.path_stack.append(name)

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
    try:
        sax.parse(stream, handler)
    except sax.SAXParseException as e:
        raise FeedParseError(e.getMessage(), e.getException(), e._locator)
    return handler.data


def normalize_feed_url(url):
    """
    Normalize and convert a URL. If the URL cannot be converted
    (invalid or unknown scheme), None is returned.

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
    if '://' not in url:
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


HTML_TEST = re.compile(r'<[a-z][a-z0-9]*(?:\s.*?>|\/?>)', re.IGNORECASE | re.DOTALL)


def is_html(text):
    """Heuristically tell if text is HTML

    By looking for an open tag (more or less:)
    >>> is_html('<h1>HELLO</h1>')
    True
    >>> is_html('a < b < c')
    False
    """
    return bool(HTML_TEST.search(text))


def remove_html_tags(html):
    """
    Remove HTML tags from a string and replace numeric and
    named entities with the corresponding character, so the
    HTML text can be displayed in a simple text view.
    """
    if html is None:
        return None

    # If we would want more speed, we could make these global
    re_strip_tags = re.compile(r'<[^>]*>')
    re_unicode_entities = re.compile(r'&#(\d{2,4});')
    re_html_entities = re.compile(r'&(.{2,8});')
    re_newline_tags = re.compile(r'(<br[^>]*>|<[/]?ul[^>]*>|</li>)', re.I)
    re_listing_tags = re.compile(r'<li[^>]*>', re.I)

    result = html

    # Convert common HTML elements to their text equivalent
    result = re_newline_tags.sub(r'\n', result)
    result = re_listing_tags.sub(r'\n * ', result)
    result = re.sub(r'<[Pp]>', r'\n\n', result)

    # Remove all HTML/XML tags from the string
    result = re_strip_tags.sub('', result)

    # Convert numeric XML entities to their unicode character
    result = re_unicode_entities.sub(lambda x: chr(int(x.group(1))), result)

    # Convert named HTML entities to their unicode character
    result = re_html_entities.sub(lambda x: entitydefs.get(x.group(1), ''), result)

    # Convert more than two newlines to two newlines
    result = re.sub(r'([\r\n]{2})([\r\n])+', r'\1', result)

    return result.strip()
