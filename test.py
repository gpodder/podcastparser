import sys
import doctest
import unittest
import podcastparser

suite = unittest.TestSuite()
suite.addTest(doctest.DocTestSuite(podcastparser))

runner = unittest.TextTestRunner(verbosity=1)
result = runner.run(suite)

if not result.wasSuccessful():
    sys.exit(1)
