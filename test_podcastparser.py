# -*- coding: utf-8 -*-
#
# test_podcastparser: Test Runner for the podcastparser (2012-12-29)
# Copyright (c) 2012, 2013, Thomas Perl <m@thp.io>
# Copyright (c) 2013, Stefan Kögl <stefan@skoegl.net>
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


import sys
import os
import glob
import json

from nose.tools import assert_equal

import podcastparser


def test_parse_feed():
    def parse_feed():
        URL = 'http://example.com/feed/'
        FILE = 'tests/example-feed.xml'
        return podcastparser.parse(URL, open(FILE))

    def podcast(result):
        assert_equal('Podcast Title', result['title'])
        assert_equal('Some description', result['description'])
        assert_equal('https://flattr.com/submit/auto?user_id=123&url='
                         'http%3A%2F%2Fexample.com%2F&language=de_DE&category'
                         '=audio&title=Podcast&description=A+Podcast&tags='
                         'podcast', result['payment_url'])
        assert_equal('http://example.com/image.png',
                         result['cover_url'])
        assert_equal('http://example.com', result['link'])
        assert_equal(4, len(result['episodes']))

    def episode1(result):
        episode = result.get('episodes')[0]
        assert_equal(8160, episode.get('total_time'))
        assert_equal('https://flattr.com/submit/auto?user_id=123&url='
                         'http%3A%2F%2Fexample.com%2Fepisode-1&language=de_DE'
                         '&category=audio&title=An+episode&description=An+'
                         'episode+description&tags=podcast',
                         episode.get('payment_url'))
        assert_equal('http://example.com/episode/1/', episode.get('link'))
        assert_equal(1376662770, episode.get('published'))
        assert_equal('Podcast Episode', episode.get('title'))
        assert_equal('example-episode-12345', episode.get('guid'))
        assert_equal('A description of the episode.',
                         episode.get('description'))
        assert_equal(1, len(episode.get('enclosures', [])))

        enclosure = episode.get('enclosures')[0]
        assert_equal('http://example.com/episode/1.ogg',
                         enclosure.get('url'))
        assert_equal('audio/ogg', enclosure.get('mime_type'))
        assert_equal(50914623, enclosure.get('file_size'))

    def episode2(result):
        episode = result.get('episodes')[1]
        assert_equal('http://example.com/podcast/episode/2/',
                         episode.get('guid'))

        # the GUID is used as the link
        assert_equal(episode.get('link'), episode.get('guid'))

        # the basename of the enclosure is used as a title
        assert_equal('episode-2', episode.get('title'))

    def episode3(result):
        episode = result.get('episodes')[2]
        assert_equal('http://example.com/episode/3/', episode.get('link'))

        # the link is used as the GUID
        assert_equal(episode.get('link'), episode.get('guid'))

    def episode4(result):
        episode = result.get('episodes')[3]
        # the enclosure URL is used as the GUID
        assert_equal('http://example.com/episode/episode-4.ogg',
                         episode.get('guid'))

    test_parts = [podcast, episode1, episode2, episode3, episode4]

    for test_part in test_parts:
        yield test_part, parse_feed()

def test_max_episodes():
    """ Parse example podcast with an episode limit """
    URL = 'http://example.com/feed/'
    FILE = 'tests/example-feed.xml'
    result = podcastparser.parse(URL, open(FILE), max_episodes=2)
    assert_equal(2, len(result['episodes']))

def test_rss_parsing():
    def test_parse_rss(rss_filename):
        basename, _ = os.path.splitext(rss_filename)
        json_filename = basename + '.json'

        expected = json.load(open(json_filename))
        parsed = podcastparser.parse('file://' + rss_filename, open(rss_filename))
        assert_equal(expected, parsed)

    for rss_filename in glob.glob(os.path.join('tests', 'data', '*.rss')):
        yield test_parse_rss, rss_filename
