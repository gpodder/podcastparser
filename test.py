import podcastparser
import urllib.request

feedurl = 'https://feeds.simplecast.com/cYQVc__c'

parsed = podcastparser.parse(feedurl, urllib.request.urlopen(feedurl))

# parsed is a dict
import pprint
pprint.pprint(parsed)