from forex.gdelt_sentiment import URL
def test_m11_is_bounded_aggregate_only():
 s=open('src/forex/gdelt_sentiment.py').read(); assert URL.startswith('https://') and 'TimelineTone' in s and 'article' not in s.lower() and 'place_order' not in s.lower()
