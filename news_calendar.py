import json
import os
from datetime import datetime, time as dt_time, timedelta
import requests
from config import NEWS_BUFFER_MINUTES, MANUAL_NEWS_TIMES

class NewsCalendar:
    """
    News Calendar for avoiding high-impact news events.
    Supports fetching from ForexFactory or fallback to manual times.
    """

    def __init__(self, cache_file="news_cache.json", buffer_minutes=30):
        self.cache_file = cache_file
        self.buffer_minutes = buffer_minutes
        self.news_events = []
        self.last_refresh = None

    def force_refresh(self):
        """Force refresh news data."""
        print("🔄 Refreshing news calendar...")
        try:
            # For now, use manual news times as fallback
            # TODO: Implement ForexFactory scraping
            self._load_manual_news()
            self._save_cache()
            self.last_refresh = datetime.utcnow()
            print("✅ News calendar refreshed")
        except Exception as e:
            print(f"❌ Failed to refresh news: {e}")

    def _load_manual_news(self):
        """Load manual news times from config."""
        self.news_events = []
        today = datetime.utcnow().date()

        for start_str, end_str in MANUAL_NEWS_TIMES:
            start_time = dt_time.fromisoformat(start_str)
            end_time = dt_time.fromisoformat(end_str)

            event = {
                'date': today.isoformat(),
                'time': start_str,
                'title': 'Economic Data Release',
                'impact': 'high',
                'start_utc': datetime.combine(today, start_time),
                'end_utc': datetime.combine(today, end_time)
            }
            self.news_events.append(event)

    def print_todays_events(self):
        """Print today's news events."""
        if not self.news_events:
            print("📅 No news events loaded")
            return

        print("📅 Today's News Events:")
        for event in self.news_events:
            start = event['start_utc'].strftime('%H:%M')
            end = event['end_utc'].strftime('%H:%M')
            print(f"   {start}-{end} UTC: {event['title']} ({event['impact']})")

    def is_high_impact_news_time(self):
        """
        Check if current time is within buffer of high-impact news.
        Returns (is_news_time, reason)
        """
        if not self.news_events:
            return False, "No news data"

        now = datetime.utcnow()
        buffer_delta = timedelta(minutes=self.buffer_minutes)

        for event in self.news_events:
            if event['impact'] != 'high':
                continue

            start_buffer = event['start_utc'] - buffer_delta
            end_buffer = event['end_utc'] + buffer_delta

            if start_buffer <= now <= end_buffer:
                reason = f"{event['title']} ({event['start_utc'].strftime('%H:%M')}-{event['end_utc'].strftime('%H:%M')} UTC)"
                return True, reason

        return False, "No high-impact news"

    def _save_cache(self):
        """Save news events to cache file."""
        try:
            data = {
                'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None,
                'events': self.news_events
            }
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, default=str, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save cache: {e}")

    def _load_cache(self):
        """Load news events from cache file."""
        if not os.path.exists(self.cache_file):
            return False

        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)

            self.last_refresh = datetime.fromisoformat(data['last_refresh']) if data.get('last_refresh') else None
            self.news_events = data.get('events', [])

            # Convert string dates back to datetime objects
            for event in self.news_events:
                event['start_utc'] = datetime.fromisoformat(event['start_utc'])
                event['end_utc'] = datetime.fromisoformat(event['end_utc'])

            return True
        except Exception as e:
            print(f"⚠️  Failed to load cache: {e}")
            return False
