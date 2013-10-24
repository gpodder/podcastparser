import sys
import doctest
import unittest
import podcastparser


class ParseFeedTest(unittest.TestCase):

    def test_feed(self):
        """ Parse example podcast and verify its results """
        URL = 'http://example.com/feed/'
        FILE = 'tests/example-feed.xml'
        result = podcastparser.parse(URL, open(FILE))
        self.assertTrue(bool(result))

        self.assertEqual('Podcast Title', result.get('title'))
        self.assertEqual('Some description', result.get('description'))
        self.assertEqual('https://flattr.com/submit/auto?user_id=123&url='
                         'http%3A%2F%2Fexample.com%2F&language=de_DE&category'
                         '=audio&title=Podcast&description=A+Podcast&tags='
                         'podcast', result.get('payment_url'))
        self.assertEqual('http://example.com/image.png',
                         result.get('cover_url'))
        self.assertEqual('http://example.com', result.get('link'))

        self.assertEqual(2, len(result.get('episodes', [])))

        # Episode 1
        episode = result.get('episodes')[0]
        self.assertEqual(8160, episode.get('total_time'))
        self.assertEqual('https://flattr.com/submit/auto?user_id=123&url='
                         'http%3A%2F%2Fexample.com%2Fepisode-1&language=de_DE'
                         '&category=audio&title=An+episode&description=An+'
                         'episode+description&tags=podcast',
                         episode.get('payment_url'))
        self.assertEqual('http://example.com/episode/1/', episode.get('link'))
        self.assertEqual(1376662770, episode.get('published'))
        self.assertEqual('Podcast Episode', episode.get('title'))
        self.assertEqual('example-episode-12345', episode.get('guid'))
        self.assertEqual('A description of the episode.',
                         episode.get('description'))
        self.assertEqual(1, len(episode.get('enclosures', [])))

        enclosure = episode.get('enclosures')[0]
        self.assertEqual('http://example.com/episode/1.ogg',
                         enclosure.get('url'))
        self.assertEqual('audio/ogg', enclosure.get('mime_type'))
        self.assertEqual(50914623, enclosure.get('file_size'))


        # Episode 2
        episode = result.get('episodes')[1]
        self.assertEqual('http://example.com/podcast/episode/2/', episode.get('guid'))


suite = unittest.TestSuite()
suite.addTest(doctest.DocTestSuite(podcastparser))
suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ParseFeedTest))

runner = unittest.TextTestRunner(verbosity=1)
result = runner.run(suite)

if not result.wasSuccessful():
    sys.exit(1)
