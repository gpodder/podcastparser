import sys
import doctest
import unittest
import podcastparser


class ParseFeedTest(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        """ Parse example podcast and verify its results """
        URL = 'http://example.com/feed/'
        FILE = 'tests/example-feed.xml'
        self.result = podcastparser.parse(URL, open(FILE))

    def test_podcast(self):
        self.assertEqual('Podcast Title', self.result.get('title'))
        self.assertEqual('Some description', self.result.get('description'))
        self.assertEqual('https://flattr.com/submit/auto?user_id=123&url='
                         'http%3A%2F%2Fexample.com%2F&language=de_DE&category'
                         '=audio&title=Podcast&description=A+Podcast&tags='
                         'podcast', self.result.get('payment_url'))
        self.assertEqual('http://example.com/image.png',
                         self.result.get('cover_url'))
        self.assertEqual('http://example.com', self.result.get('link'))

        self.assertEqual(4, len(self.result.get('episodes', [])))

    def test_episode1(self):
        episode = self.result.get('episodes')[0]
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

    def test_episode2(self):
        episode = self.result.get('episodes')[1]
        self.assertEqual('http://example.com/podcast/episode/2/',
                         episode.get('guid'))

        # the GUID is used as the link
        self.assertEqual(episode.get('link'), episode.get('guid'))

        # the basename of the enclosure is used as a title
        self.assertEqual('episode-2', episode.get('title'))

    def test_episode3(self):
        episode = self.result.get('episodes')[2]
        self.assertEqual('http://example.com/episode/3/', episode.get('link'))

        # the link is used as the GUID
        self.assertEqual(episode.get('link'), episode.get('guid'))

    def test_episode4(self):
        episode = self.result.get('episodes')[3]
        # the enclosure URL is used as the GUID
        self.assertEqual('http://example.com/episode/episode-4.ogg',
                         episode.get('guid'))


class MaxEpisodesTest(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        """ Parse example podcast with an episode limit """
        URL = 'http://example.com/feed/'
        FILE = 'tests/example-feed.xml'
        self.result = podcastparser.parse(URL, open(FILE), max_episodes=2)

    def test_max_episodes(self):
        self.assertEqual(2, len(self.result.get('episodes', [])))


suite = unittest.TestSuite()
suite.addTest(doctest.DocTestSuite(podcastparser))
suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ParseFeedTest))
suite.addTest(unittest.TestLoader().loadTestsFromTestCase(MaxEpisodesTest))

runner = unittest.TextTestRunner(verbosity=1)
result = runner.run(suite)

if not result.wasSuccessful():
    sys.exit(1)
