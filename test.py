import sys
import doctest
import unittest
import podcastparser


class ParseFeedTest(unittest.TestCase):

    def test_feed(self):
        URL = 'http://example.com/feed/'
        FILE = 'tests/example-feed.xml'
        result = podcastparser.parse(URL, open(FILE))
        self.assertIsNotNone(result)


suite = unittest.TestSuite()
suite.addTest(doctest.DocTestSuite(podcastparser))
suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ParseFeedTest))

runner = unittest.TextTestRunner(verbosity=1)
result = runner.run(suite)

if not result.wasSuccessful():
    sys.exit(1)
