import hashlib, time, requests

UA = {"User-Agent": "byosync-signal-engine/0.1 (research; contact: hello@markoholics.com)"}

def dedupe(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()

def get(url, **kw):
    """Polite GET. One second between calls, never parallel. Public endpoints only."""
    time.sleep(1.0)
    r = requests.get(url, headers=UA, timeout=30, **kw)
    r.raise_for_status()
    return r
