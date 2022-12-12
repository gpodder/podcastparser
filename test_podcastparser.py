# -*- coding: utf-8 -*-
#
# test_podcastparser: Test Runner for the podcastparser (2012-12-29)
# Copyright (c) 2012, 2013, 2014, 2018, Thomas Perl <m@thp.io>
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


import os
import glob
import json
import io


import pytest
import podcastparser


class TestPodcastparser:
    # test RSS parsing
    @pytest.mark.parametrize("rss_filename", glob.glob(os.path.join('tests', 'data', '*.rss')))
    def test_parse_rss(self, rss_filename):
        basename, _ = os.path.splitext(rss_filename)
        json_filename = basename + '.json'

        # read parameters to podcastparser.parse() from a separate file
        param_filename = basename + '.param.json'
        params = {}
        if os.path.exists(param_filename):
            params = json.load(open(param_filename))

        expected = json.load(open(json_filename))
        normalized_rss_filename = rss_filename
        if os.sep == '\\':
            normalized_rss_filename = normalized_rss_filename.replace(os.sep, '/')
        parsed = podcastparser.parse('file://' + normalized_rss_filename,
                                     open(rss_filename), **params)

        assert expected == parsed

    # test invalid roots
    feeds = [
        '<html><body/></html>',
        '<foo xmlns="http://example.com/foo.xml"><bar/></foo>',
        '<baz:foo xmlns:baz="http://example.com/baz.xml"><baz:bar/></baz:foo>',
    ]
    @pytest.mark.parametrize("feed", feeds)
    def test_fail_parse(self, feed):
        with pytest.raises(podcastparser.FeedParseError):
            podcastparser.parse('file://example.com/feed.xml', io.StringIO(feed))

