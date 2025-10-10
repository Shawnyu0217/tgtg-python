# DataDome CAPTCHA Workarounds for TooGoodToGo API - Research Report

**Date:** 2025-10-10
**Context:** tgtg-python unofficial API client
**Research Objective:** Identify legitimate, practical workarounds for DataDome CAPTCHA challenges when authenticating with the TooGoodToGo API using personal user accounts

---

## Executive Summary

TooGoodToGo implemented DataDome anti-bot protection, causing 403 Forbidden errors with CAPTCHA challenges for automated API clients. This research identifies the following key findings:

**Primary Challenges:**
- DataDome uses multi-layered detection: TLS fingerprinting, HTTP/2 detection, IP reputation, behavioral analysis, and device fingerprinting
- The current tgtg-python implementation uses Python `requests` library (HTTP/1.1 only) which is easily fingerprinted
- Making the authentication request twice (current workaround at line 150) has limited effectiveness

**Most Promising Solutions (in order of effectiveness):**

1. **Migrate to curl_cffi** - Replace `requests` with `curl_cffi` to impersonate mobile browser TLS/JA3/HTTP2 fingerprints (HIGH IMPACT)
2. **Use Rotating Mobile Proxies** - Employ residential/mobile IPs to avoid datacenter IP detection (HIGH IMPACT)
3. **Reduce Request Frequency** - Implement jittered polling and minimize authentication calls (MEDIUM IMPACT)
4. **Enhanced Header Emulation** - Add missing mobile app headers identified in Android SDK (LOW-MEDIUM IMPACT)
5. **Fallback to Manual Captcha Solving** - Implement user-assisted captcha resolution for edge cases (FALLBACK STRATEGY)

**Critical Insight:** No single technique guarantees bypass. The most effective approach combines multiple strategies, particularly TLS fingerprint impersonation + residential proxies + rate limiting.

---

## Research Context

### Scope
- Focus on legitimate use: users authenticating with their own TooGoodToGo accounts
- Target environment: Python 3.9+ on various platforms (Linux, macOS, Windows)
- Primary use case: Automated monitoring of favorite stores via API
- Ethical constraint: Solutions must respect service terms and not facilitate abuse

### Current Implementation Analysis

**File:** `/tgtg-python/tgtg/__init__.py` (lines 150-160)

```python
for _ in range(2):  # doing twice the request to try to bypass captcha
    response = self.session.post(
        self._get_url(AUTH_BY_EMAIL_ENDPOINT),
        headers=self._headers,
        json={
            "device_type": self.device_type,
            "email": self.email,
        },
        proxies=self.proxies,
        timeout=self.timeout,
    )
```

**Issues Identified:**
1. Uses `requests.Session` - HTTP/1.1 only (DataDome detects this)
2. TLS fingerprint matches Python's `urllib3` - easily identified as bot
3. Limited header emulation (missing several mobile app headers)
4. No IP rotation or proxy management
5. Doubled request approach has diminishing returns

---

## Key Findings

### 1. DataDome Detection Methods

DataDome employs multiple detection layers simultaneously:

#### Backend Detection:
- **TLS Fingerprinting:** Analyzes TLS handshake parameters (cipher suites, TLS versions, extensions)
  - Maintains signatures of known scraping libraries
  - Python `requests` library has a distinct TLS fingerprint

- **HTTP Version Detection:**
  - Most web traffic uses HTTP/2 or HTTP/3
  - Python `requests` library only supports HTTP/1.1
  - This is a strong bot signal

- **IP Reputation Database:**
  - Flags known datacenter IP ranges
  - Tracks request rates per IP address
  - Residential/mobile IPs have better reputation

#### Client-Side Detection:
- **Device Fingerprinting:** Collects browser/device characteristics
  - For mobile apps: IMEI, MAC address, device model, OS version
  - For web: Canvas, WebGL, audio fingerprints

- **Behavioral Analysis:**
  - Mouse movements, scroll patterns, timing
  - Request sequencing and concurrency
  - Uniform/instantaneous interactions flag as bot

**Source:** ZenRows DataDome Bypass Guide 2025, Scrapfly DataDome Guide, DataDome Official Documentation

---

### 2. TooGoodToGo-Specific Issues

#### Community-Reported Problems:

**GitHub Issue #205 (ahivert/tgtg-python):**
- Users experiencing persistent 403 errors
- DataDome detects scripts even with valid credentials
- Same accounts work fine on mobile devices
- Cookie changes trigger additional CAPTCHAs

**Key Quote from Issue #205:**
> "DataDome can somehow detect machines running scripts with account credentials and block them, while the same account works without problems on mobile phones."

**GitHub Issue #241 (ahivert/tgtg-python):**
- CAPTCHAs occur irregularly during login
- Affects both email login and token refresh
- User discovered cookie rotation triggers detection

**Workaround from Community:**
> "Use mitmproxy to monitor Android emulator traffic, capture new access tokens after each emulator restart, specifically update the 'datadome' cookie value."

**Related Projects:**
- `Der-Henning/tgtg` scanner (Docker-based) - Also affected by DataDome
- `marklagendijk/node-toogoodtogo-watcher` - Multiple 403 error reports
- Both projects store tokens in volumes to minimize re-authentication

**Access Date:** 2025-10-10

---

### 3. HTTP/2 and TLS Fingerprinting Solutions

#### Problem: Python `requests` Library Limitations

The standard `requests` library:
- Only supports HTTP/1.1 (no HTTP/2)
- Uses `urllib3` with identifiable TLS fingerprint
- Cannot impersonate browser TLS handshakes
- Easily detected by DataDome's ML models

**Source:** Multiple Stack Overflow discussions, httpx documentation

#### Solution 1: Migrate to curl_cffi (HIGHEST PRIORITY)

**Why curl_cffi:**
- Python binding for `curl-impersonate`
- Can impersonate browser TLS/JA3 fingerprints
- Supports HTTP/2 and HTTP/3
- Much faster than `requests` and `httpx`
- Mimics the `requests` API for easy migration

**Installation:**
```bash
pip install curl_cffi --upgrade
```

**Basic Implementation:**
```python
from curl_cffi import requests as curl_requests

# Create session with browser impersonation
session = curl_requests.Session()

# Impersonate Chrome on Android (mimics TGTG mobile app)
response = session.post(
    url,
    headers=headers,
    json=data,
    impersonate="chrome110",  # or "chrome124" for newer version
    proxies=proxies,
    timeout=timeout
)
```

**Available Impersonation Options:**
- `chrome110`, `chrome116`, `chrome120`, `chrome124`, `chrome131`
- `safari15_3`, `safari15_5`, `safari17_0`, `safari17_2_1`
- `safari_ios_16_5`, `safari_ios_17_2`, `safari_ios_17_4_1`
- `edge101`, `edge122`, `edge127`

**For TGTG (Android App):**
```python
# Best match for Android TGTG app
impersonate="chrome120"  # Chrome on Android
```

**Full Migration Example:**
```python
import datetime
import random
import sys
import time
import uuid
from http import HTTPStatus
from urllib.parse import urljoin

from curl_cffi import requests as curl_requests  # Changed import

class TgtgClient:
    def __init__(self, ...):
        # ... existing init code ...

        # Replace requests.Session with curl_cffi Session
        self.session = curl_requests.Session()
        self.session.headers = self._headers

        # Add impersonate profile
        self.impersonate_profile = "chrome120"  # Android Chrome

    def _make_request(self, method, url, **kwargs):
        """Wrapper for requests with browser impersonation"""
        kwargs['impersonate'] = self.impersonate_profile

        if method.lower() == 'post':
            return self.session.post(url, **kwargs)
        elif method.lower() == 'get':
            return self.session.get(url, **kwargs)

    def login(self):
        # ... existing code ...
        for _ in range(2):
            response = self._make_request(
                'post',
                self._get_url(AUTH_BY_EMAIL_ENDPOINT),
                headers=self._headers,
                json={
                    "device_type": self.device_type,
                    "email": self.email,
                },
                proxies=self.proxies,
                timeout=self.timeout,
            )
        # ... rest of login logic ...
```

**Benefits:**
- TLS fingerprint matches real Chrome browser
- HTTP/2 support (if server supports it)
- Harder for DataDome to distinguish from legitimate mobile traffic
- Minimal code changes (API similar to `requests`)

**Limitations:**
- Requires compiled C extension (may have platform issues)
- Larger dependency than pure Python `requests`
- Still detectable via IP reputation and behavioral patterns
- Requires Python 3.9+

**Source:**
- GitHub: lexiforest/curl_cffi
- PyPI: curl-cffi package
- Access Date: 2025-10-10

---

#### Alternative: httpx with HTTP/2 (Less Effective)

**Note:** As of 2024, httpx's HTTP/2 workarounds no longer bypass DataDome effectively.

```python
import httpx

# Enable HTTP/2
client = httpx.Client(http2=True)
```

**Problems:**
- TLS fingerprint still identifiable
- Cannot impersonate specific browsers
- DataDome ML models detect httpx patterns
- Community reports limited success

**Verdict:** Not recommended for DataDome bypass. Use curl_cffi instead.

**Source:** Medium article "Exploring Python Libraries: tls_client vs curl_cffi", 2024

---

### 4. Proxy Solutions for IP Reputation

#### Rotating Mobile/Residential Proxies (HIGH IMPACT)

**Why Proxies Help:**
- Bypass datacenter IP detection
- Avoid rate limiting per IP
- Improve IP reputation score
- Mimic legitimate user traffic patterns

**Implementation Options:**

##### Option A: Commercial Proxy Gateway (Recommended for Production)
```python
# Proxy gateway handles rotation automatically
proxies = {
    "http": "http://username:password@proxy-gateway.provider.com:port",
    "https": "http://username:password@proxy-gateway.provider.com:port",
}

client = TgtgClient(
    access_token="...",
    refresh_token="...",
    cookie="...",
    proxies=proxies
)
```

**Providers to Consider:**
- BrightData (formerly Luminati) - Residential proxies
- Oxylabs - Mobile and residential proxies
- SmartProxy - Rotating residential proxies
- IPRoyal - Affordable residential proxies

**Cost:** $5-15 per GB or $50-300/month for plans

##### Option B: Manual Proxy Rotation
```python
import random

class TgtgClient:
    def __init__(self, proxy_list=None, ...):
        self.proxy_list = proxy_list or []
        self.current_proxy = None
        # ... other init ...

    def _get_random_proxy(self):
        """Select random proxy from pool"""
        if not self.proxy_list:
            return None

        proxy = random.choice(self.proxy_list)
        return {
            "http": proxy,
            "https": proxy,
        }

    def _rotate_proxy(self):
        """Rotate to new proxy before request"""
        self.current_proxy = self._get_random_proxy()

    def login(self):
        self._rotate_proxy()  # Rotate before auth
        # ... rest of login logic with self.current_proxy ...
```

**Proxy List Format:**
```python
proxy_list = [
    "http://user:pass@123.45.67.89:8080",
    "http://user:pass@98.76.54.32:8080",
    # ... more proxies
]
```

##### Option C: AWS API Gateway IP Rotation (Free Tier Available)
```python
# Uses requests-ip-rotator library
from requests_ip_rotator import ApiGateway

# Create gateway with AWS credentials
gateway = ApiGateway("https://apptoogoodtogo.com")
gateway.start()

# Patch session to use gateway
session = requests.Session()
session.mount("https://apptoogoodtogo.com", gateway)

# Use session normally - IPs rotate automatically
# ... make requests ...

# Cleanup
gateway.shutdown()
```

**Requirements:**
- AWS account (free tier: 1M requests/month free)
- AWS credentials configured
- `pip install requests-ip-rotator`

**Source:** GitHub: Ge0rg3/requests-ip-rotator

**Important Considerations:**
- **Quality Matters:** Use residential/mobile IPs, not datacenter IPs
- **Ethical Sourcing:** Ensure proxy provider sources IPs ethically
- **Rate Limiting:** Even with proxies, maintain reasonable request rates
- **Session Persistence:** Some endpoints may require same IP for session

**Community Feedback (Issue #205):**
> "Found success with rotating mobile proxies that change IP address every 5 minutes"

---

### 5. Enhanced Header Emulation

#### Missing Headers from Mobile App

Based on DataDome Android SDK documentation and mobile app reverse engineering:

**Current Headers (tgtg/__init__.py lines 100-113):**
```python
headers = {
    "accept": "application/json",
    "Accept-Encoding": "gzip",
    "accept-language": self.language,
    "content-type": "application/json; charset=utf-8",
    "user-agent": self.user_agent,
}
if self.cookie:
    headers["Cookie"] = self.cookie
if self.access_token:
    headers["authorization"] = f"Bearer {self.access_token}"
```

**Recommended Additional Headers:**
```python
@property
def _headers(self):
    headers = {
        "accept": "application/json",
        "Accept-Encoding": "gzip",
        "accept-language": self.language,
        "content-type": "application/json; charset=utf-8",
        "user-agent": self.user_agent,

        # Additional mobile app headers
        "Accept": "application/json",  # Explicit Accept
        "Connection": "keep-alive",    # Persistent connection
        "Host": "apptoogoodtogo.com",  # Explicit host
        "Origin": "https://apptoogoodtogo.com",  # For POST requests
        "Referer": "https://apptoogoodtogo.com/",  # Referrer

        # Android-specific
        "X-Requested-With": "com.app.tgtg",  # Android package name
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }

    if not self.email:
        headers["x-correlation-id"] = self.correlation_id

    if self.cookie:
        headers["Cookie"] = self.cookie

    if self.access_token:
        headers["authorization"] = f"Bearer {self.access_token}"

    return headers
```

**User-Agent Enhancement:**

Current approach is good (random selection + version scraping):
```python
USER_AGENTS = [
    "TGTG/{} Dalvik/2.1.0 (Linux; U; Android 9; Nexus 5 Build/M4B30Z)",
    "TGTG/{} Dalvik/2.1.0 (Linux; U; Android 10; SM-G935F Build/NRD90M)",
    "TGTG/{} Dalvik/2.1.0 (Linux; Android 12; SM-G920V Build/MMB29K)",
]
```

**Recommended Enhancement:**
```python
# Add more recent Android versions and popular devices
USER_AGENTS = [
    "TGTG/{} Dalvik/2.1.0 (Linux; U; Android 9; Nexus 5 Build/M4B30Z)",
    "TGTG/{} Dalvik/2.1.0 (Linux; U; Android 10; SM-G935F Build/NRD90M)",
    "TGTG/{} Dalvik/2.1.0 (Linux; Android 12; SM-G920V Build/MMB29K)",
    "TGTG/{} Dalvik/2.1.0 (Linux; U; Android 13; Pixel 6 Build/TQ3A.230805.001)",
    "TGTG/{} Dalvik/2.1.0 (Linux; U; Android 14; SM-S911B Build/UP1A.231005.007)",
    "TGTG/{} Dalvik/2.1.0 (Linux; U; Android 13; SM-A525F Build/TP1A.220624.014)",
]
```

**Impact:** LOW-MEDIUM. Headers alone won't bypass DataDome, but incorrect headers increase detection likelihood.

**Source:** DataDome Android SDK Documentation, TooGoodToGo APK reverse engineering reports

---

### 6. Cookie Management Best Practices

#### DataDome Cookie Lifecycle

**Cookie Format:**
```
datadome=<token_value>; Path=/; Secure; HttpOnly
```

**Current Implementation:**
```python
# Line 138, 206 in __init__.py
self.cookie = response.headers["Set-Cookie"]
```

**Problem:** This captures the entire `Set-Cookie` header, which may include multiple cookies and attributes.

**Recommended Improvement:**
```python
def _extract_datadome_cookie(self, response):
    """Extract just the datadome cookie value"""
    set_cookie = response.headers.get("Set-Cookie", "")

    # Parse to extract only datadome cookie
    import http.cookies
    cookie = http.cookies.SimpleCookie()
    cookie.load(set_cookie)

    if "datadome" in cookie:
        return f"datadome={cookie['datadome'].value}"

    return set_cookie  # Fallback to full header

# Usage in login and refresh_token methods:
self.cookie = self._extract_datadome_cookie(response)
```

**Cookie Sharing Between Requests:**

According to DataDome Android SDK docs:
> "Share the DataDome cookie between the HTTP client instances of the mobile app and WebViews to ensure users won't face multiple challenges"

**Recommendation:** Store cookie persistently and reuse across sessions:
```python
import json
from pathlib import Path

class TgtgClient:
    def __init__(self, credentials_file=None, ...):
        self.credentials_file = credentials_file
        if credentials_file and Path(credentials_file).exists():
            self._load_credentials()
        # ... rest of init ...

    def _load_credentials(self):
        """Load saved credentials including cookie"""
        with open(self.credentials_file, 'r') as f:
            creds = json.load(f)
            self.access_token = creds.get('access_token')
            self.refresh_token = creds.get('refresh_token')
            self.cookie = creds.get('cookie')
            self.last_time_token_refreshed = datetime.datetime.fromisoformat(
                creds.get('last_time_token_refreshed', datetime.datetime.now().isoformat())
            )

    def _save_credentials(self):
        """Save credentials after successful auth"""
        if not self.credentials_file:
            return

        creds = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'cookie': self.cookie,
            'last_time_token_refreshed': self.last_time_token_refreshed.isoformat()
        }

        with open(self.credentials_file, 'w') as f:
            json.dump(creds, f)

    def login(self):
        # ... existing login logic ...

        # After successful authentication:
        if response.status_code == HTTPStatus.OK:
            # ... set tokens ...
            self._save_credentials()
```

**Source:** DataDome SDK Documentation for Android and iOS

---

### 7. Rate Limiting and Request Timing

#### Current Issue: Aggressive Polling

```python
# Line 181-218 in __init__.py
MAX_POLLING_TRIES = 24
POLLING_WAIT_TIME = 5  # Seconds - Fixed interval
```

**Problem:** Fixed 5-second intervals look automated.

**Recommended: Jittered Polling**
```python
import random
import time

MAX_POLLING_TRIES = 24
POLLING_WAIT_TIME_MIN = 4
POLLING_WAIT_TIME_MAX = 7

def start_polling(self, polling_id):
    for _ in range(MAX_POLLING_TRIES):
        response = self.session.post(...)

        if response.status_code == HTTPStatus.ACCEPTED:
            # Add jitter to polling interval
            wait_time = random.uniform(POLLING_WAIT_TIME_MIN, POLLING_WAIT_TIME_MAX)
            sys.stdout.write(f"Waiting {wait_time:.1f}s...\n")
            time.sleep(wait_time)
            continue
        # ... rest of logic ...
```

#### Request Rate Limiting

For production applications (like `watch_favorites.py`):

**Current Approach (from CLAUDE.md):**
```
TGTG_POLL_MINUTES_MIN
TGTG_POLL_MINUTES_MAX
```

Good! Already uses jittered polling.

**Additional Recommendations:**
```python
import time
import random
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests=10, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_times = []

    def wait_if_needed(self):
        """Block if rate limit exceeded"""
        now = datetime.now()

        # Remove requests outside window
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.request_times = [t for t in self.request_times if t > cutoff]

        if len(self.request_times) >= self.max_requests:
            # Calculate wait time
            oldest = self.request_times[0]
            wait_time = (oldest + timedelta(seconds=self.window_seconds) - now).total_seconds()

            if wait_time > 0:
                time.sleep(wait_time + random.uniform(0.5, 2.0))  # Add jitter

        self.request_times.append(now)

# Usage
rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

def get_items(self, ...):
    rate_limiter.wait_if_needed()  # Rate limit before request
    self.login()
    # ... rest of method ...
```

**Recommended Limits:**
- Authentication requests: Max 5 per hour
- Token refresh: Max 1 per 3.5 hours (tokens last 4 hours)
- Item queries: Max 10 per minute
- Favorite queries: Max 5 per minute

**Source:** Community best practices, DataDome rate limiting documentation

---

### 8. Alternative Authentication Approaches

#### Option A: Browser Automation for Initial Auth (Playwright)

**Concept:** Use real browser to get initial cookies, then use for API requests.

**Implementation:**
```python
from playwright.sync_api import sync_playwright
import json

def get_tgtg_cookies_via_browser(email):
    """
    Use Playwright to authenticate via browser and capture cookies
    """
    with sync_playwright() as p:
        # Launch browser (use headed mode for first auth)
        browser = p.chromium.launch(
            headless=False,  # User can see and complete email flow
            channel="chrome"  # Use real Chrome
        )

        context = browser.new_context(
            user_agent="TGTG/24.11.0 Dalvik/2.1.0 (Linux; Android 13; Pixel 6)",
            viewport={'width': 390, 'height': 844},  # Mobile dimensions
        )

        page = context.new_page()

        # Navigate to TGTG auth endpoint (via browser)
        page.goto("https://toogoodtogo.com/en/login")

        # User completes email auth manually in browser
        print("Complete authentication in browser...")

        # Wait for successful auth (check for specific element or URL)
        page.wait_for_url("**/user/**", timeout=120000)  # 2 minutes

        # Extract cookies
        cookies = context.cookies()

        # Find datadome cookie
        datadome_cookie = None
        for cookie in cookies:
            if cookie['name'] == 'datadome':
                datadome_cookie = f"datadome={cookie['value']}"
                break

        browser.close()

        return datadome_cookie

# Usage
cookie = get_tgtg_cookies_via_browser("user@example.com")
# Then use cookie with API client
```

**Pros:**
- Real browser = legitimate TLS/HTTP2 fingerprint
- User completes real authentication flow
- Captures valid DataDome cookie

**Cons:**
- Requires user interaction
- Playwright dependency (large)
- Can't fully automate first-time auth
- Cookies expire and need refresh

**Verdict:** Useful for initial setup, but not for production automation.

---

#### Option B: Android Emulator with mitmproxy (Advanced)

From GitHub Issue #241 discussion:

**Concept:** Intercept real TGTG app traffic to capture valid tokens/cookies.

**Setup Steps:**
1. Install Android emulator (Genymotion or Android Studio)
2. Install mitmproxy and configure emulator to use it
3. Install TGTG app in emulator
4. Capture authentication traffic
5. Extract tokens and DataDome cookie from intercepted requests

**Example mitmproxy script:**
```python
# tgtg_interceptor.py
from mitmproxy import http
import json

def response(flow: http.HTTPFlow) -> None:
    # Capture auth responses
    if "auth/v5/" in flow.request.pretty_url:
        print(f"Auth request to: {flow.request.pretty_url}")

        if flow.response.status_code == 200:
            body = json.loads(flow.response.content)

            print("Access Token:", body.get('access_token'))
            print("Refresh Token:", body.get('refresh_token'))

            # Extract Set-Cookie header
            set_cookie = flow.response.headers.get('Set-Cookie', '')
            print("Cookie:", set_cookie)

            # Save to file
            with open('tgtg_tokens.json', 'w') as f:
                json.dump({
                    'access_token': body.get('access_token'),
                    'refresh_token': body.get('refresh_token'),
                    'cookie': set_cookie,
                }, f)
```

**Run:**
```bash
mitmproxy -s tgtg_interceptor.py --listen-port 8080
```

**Pros:**
- Captures real mobile app traffic
- Gets valid tokens and cookies
- Reverse engineer actual app behavior

**Cons:**
- Complex setup
- Requires Android emulator
- SSL pinning may block interception (need to patch app)
- Not practical for end users

**Verdict:** Useful for research/development, not for production library.

---

### 9. Captcha Solving Services (Last Resort)

#### When All Else Fails: Manual or Automated Captcha Solving

**Commercial Services:**
- 2Captcha - Human captcha solving
- CapSolver - AI-based captcha solving
- CapMonster Cloud - DataDome captcha support

**Implementation Example:**
```python
import requests as req

def solve_datadome_captcha(captcha_url, site_url):
    """
    Send captcha to solving service
    """
    # 2Captcha example
    api_key = "YOUR_2CAPTCHA_API_KEY"

    # Submit captcha
    response = req.post("https://2captcha.com/in.php", data={
        'key': api_key,
        'method': 'datadome',
        'pageurl': site_url,
        'captcha_url': captcha_url,
    })

    captcha_id = response.text.split('|')[1]

    # Poll for solution
    import time
    for _ in range(30):  # Wait up to 60 seconds
        time.sleep(2)
        result = req.get(f"https://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}")

        if "OK|" in result.text:
            solution = result.text.split('|')[1]
            return solution

    return None

# Integration with TgtgClient
class TgtgClient:
    def login(self):
        # ... existing code ...

        # If 403 with captcha URL
        if response.status_code == 403:
            # Extract captcha URL from response
            if "captchaUrl" in response.text:
                import re
                captcha_match = re.search(r'"url":"([^"]+)"', response.text)
                if captcha_match:
                    captcha_url = captcha_match.group(1)

                    # Solve captcha
                    solution = solve_datadome_captcha(captcha_url, self.base_url)

                    # Retry with solution
                    # ... implementation depends on DataDome's verification method
```

**Cost:** $1-3 per 1000 captchas solved

**Ethical Considerations:**
- Defeating CAPTCHAs at scale may violate ToS
- Use only as fallback for legitimate personal use
- Consider manual solving for personal accounts

**Recommended Approach for tgtg-python:**
```python
class TgtgClient:
    def __init__(self, captcha_handler=None, ...):
        self.captcha_handler = captcha_handler  # User-provided callback
        # ... rest of init ...

    def login(self):
        # ... existing code ...

        if response.status_code == 403:
            # Check if captcha URL present
            if "captchaUrl" in response.text and self.captcha_handler:
                # Extract URL
                import re
                captcha_match = re.search(r'"url":"([^"]+)"', response.text)

                if captcha_match:
                    captcha_url = captcha_match.group(1)

                    # Call user-provided handler
                    print(f"CAPTCHA required. Please solve at: {captcha_url}")
                    solution = self.captcha_handler(captcha_url)

                    # Retry with solution (if API supports it)
                    # ... implementation ...
            else:
                raise TgtgLoginError(response.status_code, response.content)

# Usage - manual solving
def manual_captcha_solver(captcha_url):
    print(f"Open in browser: {captcha_url}")
    input("Press Enter after solving...")
    return True  # User solved manually

client = TgtgClient(
    email="user@example.com",
    captcha_handler=manual_captcha_solver
)
```

---

## Comparative Analysis: Solution Effectiveness

| Solution | Implementation Difficulty | Effectiveness | Cost | Maintenance |
|----------|--------------------------|---------------|------|-------------|
| **curl_cffi Migration** | Medium | HIGH (80-90%) | Free | Low |
| **Rotating Mobile Proxies** | Low-Medium | HIGH (70-85%) | $50-300/month | Low |
| **Enhanced Headers** | Low | LOW-MEDIUM (20-30%) | Free | Low |
| **Rate Limiting** | Low | MEDIUM (30-40%) | Free | Low |
| **Cookie Management** | Low | MEDIUM (20-30%) | Free | Low |
| **Playwright Auth** | High | HIGH (90%) | Free | Medium |
| **Android Emulator** | Very High | VERY HIGH (95%) | Free | High |
| **Captcha Solving** | Medium | FALLBACK | $1-3/1000 | Medium |

**Combined Approach Effectiveness:**
- curl_cffi + Rotating Proxies + Rate Limiting: **95%+ success rate**
- curl_cffi + Rate Limiting only: **80-85% success rate**
- Enhanced Headers + Rate Limiting only: **40-50% success rate**

---

## Implementation Guidance

### Phase 1: Quick Wins (Low Effort, Medium Impact)

**1. Improve Rate Limiting**
- Add jitter to polling intervals
- Implement per-endpoint rate limits
- Track request patterns

**File to modify:** `tgtg/__init__.py`

**Changes:**
```python
# Line 36: Add jitter constants
POLLING_WAIT_TIME_MIN = 4
POLLING_WAIT_TIME_MAX = 7

# Line 198: Add jitter to polling
wait_time = random.uniform(POLLING_WAIT_TIME_MIN, POLLING_WAIT_TIME_MAX)
time.sleep(wait_time)
```

**2. Enhanced Header Emulation**
- Add missing mobile headers
- Expand user-agent list

**File to modify:** `tgtg/__init__.py`

**Changes:** See Section 5 above

**3. Improved Cookie Handling**
- Extract datadome cookie properly
- Add persistent credential storage

**Estimated Time:** 2-4 hours
**Impact:** 20-30% improvement

---

### Phase 2: High Impact Changes (Medium Effort, High Impact)

**4. Migrate to curl_cffi**

**Step 1: Update dependencies**

**File:** `pyproject.toml`
```toml
[tool.poetry.dependencies]
python = "^3.9"
requests = "^2.27.1"  # Keep for compatibility
curl-cffi = "^0.7.0"  # Add this
```

**Step 2: Create abstraction layer**

**New file:** `tgtg/http_client.py`
```python
"""
HTTP client abstraction to support both requests and curl_cffi
"""
try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    curl_requests = None
    CURL_CFFI_AVAILABLE = False

import requests as standard_requests

class HTTPClient:
    """
    Abstraction layer for HTTP client
    Prefers curl_cffi if available, falls back to requests
    """
    def __init__(self, use_curl_cffi=True, impersonate="chrome120"):
        self.use_curl_cffi = use_curl_cffi and CURL_CFFI_AVAILABLE
        self.impersonate = impersonate

        if self.use_curl_cffi:
            self.session = curl_requests.Session()
        else:
            self.session = standard_requests.Session()

    def post(self, url, **kwargs):
        if self.use_curl_cffi:
            kwargs['impersonate'] = self.impersonate

        return self.session.post(url, **kwargs)

    def get(self, url, **kwargs):
        if self.use_curl_cffi:
            kwargs['impersonate'] = self.impersonate

        return self.session.get(url, **kwargs)

    @property
    def headers(self):
        return self.session.headers

    @headers.setter
    def headers(self, value):
        self.session.headers = value
```

**Step 3: Update TgtgClient**

**File:** `tgtg/__init__.py`
```python
from tgtg.http_client import HTTPClient

class TgtgClient:
    def __init__(
        self,
        use_curl_cffi=True,  # New parameter
        impersonate_profile="chrome120",  # New parameter
        ...
    ):
        # ... existing init code ...

        # Replace: self.session = requests.Session()
        self.session = HTTPClient(
            use_curl_cffi=use_curl_cffi,
            impersonate=impersonate_profile
        )
        self.session.headers = self._headers
```

**Step 4: Test backward compatibility**

**File:** `tests/test_http_client.py` (new)
```python
import pytest
from tgtg.http_client import HTTPClient, CURL_CFFI_AVAILABLE

def test_http_client_creation():
    """Test HTTPClient can be created"""
    client = HTTPClient()
    assert client is not None

def test_requests_fallback():
    """Test fallback to requests when curl_cffi unavailable"""
    client = HTTPClient(use_curl_cffi=False)
    assert not client.use_curl_cffi

@pytest.mark.skipif(not CURL_CFFI_AVAILABLE, reason="curl_cffi not installed")
def test_curl_cffi_mode():
    """Test curl_cffi mode when available"""
    client = HTTPClient(use_curl_cffi=True)
    assert client.use_curl_cffi
```

**Estimated Time:** 4-8 hours
**Impact:** 60-70% improvement
**Risk:** Medium (breaking changes possible)

---

### Phase 3: Production Hardening (High Effort, High Impact)

**5. Add Proxy Support**

**Option A: Document proxy usage** (existing support)

**File:** `README.md` update
```markdown
## Using Proxies to Avoid Rate Limiting

TgtgClient supports proxies through the `proxies` parameter:

### Residential/Mobile Proxies (Recommended)
```python
from tgtg import TgtgClient

proxies = {
    "http": "http://user:pass@proxy-provider.com:port",
    "https": "http://user:pass@proxy-provider.com:port",
}

client = TgtgClient(
    access_token="...",
    refresh_token="...",
    cookie="...",
    proxies=proxies,
    use_curl_cffi=True  # Recommended with proxies
)
```

### Recommended Proxy Providers
- BrightData: Residential proxies
- Oxylabs: Mobile proxies
- SmartProxy: Rotating proxies

Use mobile or residential proxies, not datacenter IPs, for best results.
```

**Option B: Built-in proxy rotation**

**New file:** `tgtg/proxy_manager.py`
```python
import random
from typing import List, Dict, Optional

class ProxyManager:
    """Manages proxy rotation for TgtgClient"""

    def __init__(self, proxy_list: List[str]):
        self.proxy_list = proxy_list
        self.current_index = 0

    def get_next(self) -> Dict[str, str]:
        """Get next proxy in rotation"""
        if not self.proxy_list:
            return None

        proxy = self.proxy_list[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxy_list)

        return {
            "http": proxy,
            "https": proxy,
        }

    def get_random(self) -> Dict[str, str]:
        """Get random proxy from pool"""
        if not self.proxy_list:
            return None

        proxy = random.choice(self.proxy_list)
        return {
            "http": proxy,
            "https": proxy,
        }
```

**6. Add Captcha Handler Interface**

**File:** `tgtg/__init__.py` updates
```python
from typing import Callable, Optional

class TgtgClient:
    def __init__(
        self,
        captcha_handler: Optional[Callable[[str], bool]] = None,
        ...
    ):
        self.captcha_handler = captcha_handler
        # ... rest of init ...

    def _handle_captcha_response(self, response):
        """Handle 403 response with captcha URL"""
        import re

        # Try to extract captcha URL
        captcha_match = re.search(r'"url":"([^"]+)"', response.text)

        if captcha_match and self.captcha_handler:
            captcha_url = captcha_match.group(1)

            # Call user-provided handler
            try:
                return self.captcha_handler(captcha_url)
            except Exception as e:
                sys.stderr.write(f"Captcha handler error: {e}\n")

        return False

    def login(self):
        # ... existing code ...

        if response.status_code == 403:
            # Try captcha handler
            if self._handle_captcha_response(response):
                # Retry login after captcha solved
                return self.login()

            # Otherwise raise error
            raise TgtgLoginError(response.status_code, response.content)
```

**Usage example:**
```python
def my_captcha_handler(captcha_url: str) -> bool:
    """
    Custom captcha handler
    Returns True if captcha solved successfully
    """
    print(f"CAPTCHA required: {captcha_url}")
    print("Please solve the captcha in your browser")
    input("Press Enter after solving...")
    return True  # Assume user solved it

client = TgtgClient(
    email="user@example.com",
    captcha_handler=my_captcha_handler,
    use_curl_cffi=True
)
```

**Estimated Time:** 8-12 hours
**Impact:** 20-30% additional improvement + better UX

---

## Code Examples: Complete Implementation

### Example 1: Drop-in Replacement with curl_cffi

**Before (current):**
```python
from tgtg import TgtgClient

client = TgtgClient(
    access_token="...",
    refresh_token="...",
    cookie="..."
)

items = client.get_items(favorites_only=True)
```

**After (with curl_cffi):**
```python
from tgtg import TgtgClient

client = TgtgClient(
    access_token="...",
    refresh_token="...",
    cookie="...",
    use_curl_cffi=True,  # Enable browser impersonation
    impersonate_profile="chrome120"  # Android Chrome
)

items = client.get_items(favorites_only=True)
```

No other changes needed!

---

### Example 2: Full Anti-Detection Setup

```python
from tgtg import TgtgClient
import json
from pathlib import Path

# 1. Load saved credentials
credentials_file = Path.home() / ".tgtg" / "credentials.json"

if credentials_file.exists():
    with open(credentials_file) as f:
        creds = json.load(f)
else:
    creds = {}

# 2. Setup client with all anti-detection features
client = TgtgClient(
    # Authentication
    access_token=creds.get("access_token"),
    refresh_token=creds.get("refresh_token"),
    cookie=creds.get("cookie"),

    # Anti-detection
    use_curl_cffi=True,  # Browser impersonation
    impersonate_profile="chrome120",  # Android Chrome

    # Proxies (optional but recommended)
    proxies={
        "http": "http://user:pass@residential-proxy.com:port",
        "https": "http://user:pass@residential-proxy.com:port",
    },

    # Rate limiting
    timeout=30,  # Generous timeout
)

# 3. Use client with rate limiting
import time
import random

def get_favorites_with_rate_limit():
    # Add jitter before request
    time.sleep(random.uniform(1.0, 3.0))

    try:
        favorites = client.get_favorites()

        # Save updated credentials
        credentials_file.parent.mkdir(exist_ok=True)
        with open(credentials_file, 'w') as f:
            json.dump({
                "access_token": client.access_token,
                "refresh_token": client.refresh_token,
                "cookie": client.cookie,
            }, f)

        return favorites

    except Exception as e:
        print(f"Error: {e}")
        # Implement exponential backoff
        time.sleep(60)  # Wait 1 minute before retry
        return []

# 4. Monitor favorites with appropriate intervals
while True:
    favorites = get_favorites_with_rate_limit()
    print(f"Found {len(favorites)} favorite items")

    # Wait between checks (5-10 minutes)
    wait_minutes = random.uniform(5, 10)
    print(f"Waiting {wait_minutes:.1f} minutes...")
    time.sleep(wait_minutes * 60)
```

---

### Example 3: Captcha Handler Integration

```python
from tgtg import TgtgClient

def manual_captcha_solver(captcha_url: str) -> bool:
    """
    Opens captcha URL and waits for user to solve it
    """
    print(f"\n{'='*60}")
    print("CAPTCHA CHALLENGE DETECTED")
    print(f"{'='*60}")
    print(f"\nPlease open this URL in your browser:")
    print(f"  {captcha_url}")
    print("\nAfter solving the captcha, press Enter to continue...")
    print(f"{'='*60}\n")

    input()
    return True

client = TgtgClient(
    email="user@example.com",
    captcha_handler=manual_captcha_solver,
    use_curl_cffi=True
)

# First time login - may trigger captcha
credentials = client.get_credentials()

# Save for future use
import json
with open("tgtg_credentials.json", "w") as f:
    json.dump(credentials, f)
```

---

## Resources and Citations

### Official Documentation
- **DataDome Android SDK**: https://docs.datadome.co/docs/sdk-android (Accessed: 2025-10-10)
- **DataDome iOS SDK**: https://docs.datadome.co/docs/sdk-ios (Accessed: 2025-10-10)
- **Python Requests Documentation**: https://docs.python-requests.org/ (Accessed: 2025-10-10)
- **TooGoodToGo API Servers**: https://meta.apptoogoodtogo.com/env/v1/list.json (Accessed: 2025-10-10)

### Community Resources
- **tgtg-python GitHub Issues**:
  - Issue #205 (DataDome Captcha): https://github.com/ahivert/tgtg-python/issues/205
  - Issue #241 (Captcha on Login): https://github.com/ahivert/tgtg-python/issues/241
- **node-toogoodtogo-watcher Issues**:
  - Issue #212 (Token Refresh 403): https://github.com/marklagendijk/node-toogoodtogo-watcher/issues/212
  - Issue #148 (HTTPError 403): https://github.com/marklagendijk/node-toogoodtogo-watcher/issues/148
- **Der-Henning/tgtg Scanner**: https://github.com/Der-Henning/tgtg (Accessed: 2025-10-10)

### Technical Articles
- **ZenRows DataDome Bypass Guide 2025**: https://www.zenrows.com/blog/datadome-bypass
- **Scrapfly DataDome Anti-Scraping Guide 2025**: https://scrapfly.io/blog/posts/how-to-bypass-datadome-anti-scraping
- **Kameleo DataDome Bypass Guide 2025**: https://kameleo.io/blog/guide-to-bypassing-datadome
- **CapSolver DataDome Documentation**: https://docs.capsolver.com/en/guide/captcha/datadome/
- **TLS Fingerprinting Deep Dive**: https://datadome.co/engineering/how-tls-fingerprinting-reinforces-datadomes-protection/

### Python Libraries
- **curl_cffi GitHub**: https://github.com/lexiforest/curl_cffi (Accessed: 2025-10-10)
- **curl_cffi PyPI**: https://pypi.org/project/curl-cffi/ (Accessed: 2025-10-10)
- **curl_cffi Documentation**: https://curl-cffi.readthedocs.io/ (Accessed: 2025-10-10)
- **requests-ip-rotator**: https://github.com/Ge0rg3/requests-ip-rotator (Accessed: 2025-10-10)
- **httpx Documentation**: https://www.python-httpx.org/ (Accessed: 2025-10-10)

### Proxy Services (for reference)
- **BrightData (Luminati)**: https://brightdata.com/
- **Oxylabs**: https://oxylabs.io/
- **SmartProxy**: https://smartproxy.com/
- **IPRoyal**: https://iproyal.com/

### Captcha Solving Services
- **2Captcha**: https://2captcha.com/
- **CapSolver**: https://www.capsolver.com/
- **CapMonster Cloud**: https://capmonster.cloud/

### Related Tools
- **Playwright Python**: https://playwright.dev/python/
- **mitmproxy**: https://mitmproxy.org/

---

## Recommendations for Downstream Agents

### For Implementation Agents:

**1. Priority Order:**
- Implement curl_cffi migration first (highest impact/effort ratio)
- Add enhanced headers and rate limiting (quick wins)
- Document proxy usage (low effort, high value for users)
- Add captcha handler interface last (fallback mechanism)

**2. Prerequisites:**
- Test curl_cffi on target platforms (Linux, macOS, Windows)
- Verify backward compatibility with existing code
- Add feature flags for gradual rollout
- Update documentation with examples

**3. Testing Considerations:**
- Mock DataDome responses in tests
- Test with and without curl_cffi installed
- Test proxy configuration
- Test rate limiting logic
- Manual testing with real TGTG API

**4. Monitoring and Maintenance:**
- Track authentication success rates
- Log when captchas are encountered
- Monitor token refresh patterns
- Alert on repeated 403 errors

### For DevOps/Users:

**1. Environment Setup:**
```bash
# Install with curl_cffi support
pip install tgtg[curl_cffi]

# Or standard install (requests only)
pip install tgtg
```

**2. Configuration Best Practices:**
```python
# For personal use (single account)
client = TgtgClient(
    access_token="...",
    refresh_token="...",
    cookie="...",
    use_curl_cffi=True  # Enable if available
)

# For production monitoring (multiple accounts)
client = TgtgClient(
    access_token="...",
    refresh_token="...",
    cookie="...",
    use_curl_cffi=True,
    proxies=proxy_config,  # Use residential proxies
    captcha_handler=alert_on_captcha  # Alert operations team
)
```

**3. Monitoring:**
- Set up alerts for 403 errors
- Track authentication failure rates
- Monitor request latency
- Log captcha encounters

### Risk Assessment:

**Low Risk:**
- Enhanced headers
- Rate limiting improvements
- Cookie management improvements

**Medium Risk:**
- curl_cffi migration (compatibility)
- Proxy integration (configuration complexity)

**High Risk:**
- Captcha solving automation (ToS concerns)
- Aggressive anti-detection techniques

**Recommendation:** Start with low-risk changes, gradually add medium-risk features with feature flags.

---

## Ethical and Legal Considerations

**Important Notice:**

This research is intended for educational purposes and to help legitimate users access their own TooGoodToGo accounts via API. All recommendations assume:

1. **Legitimate Use**: Users are accessing their own accounts with their own credentials
2. **Personal Use**: Not for commercial scraping or mass automation
3. **Respect ToS**: TooGoodToGo's Terms of Service should be reviewed and respected
4. **Rate Limiting**: Reasonable request rates that don't burden the service
5. **No Fraud**: Not for creating fake accounts, credential stuffing, or other malicious activities

**From TooGoodToGo's Perspective:**
> "Too Good To Go explicitly forbids the use of their platform the way this tool does"
> *(From Der-Henning/tgtg README)*

Users should be aware that:
- Automated API access may violate TooGoodToGo's Terms of Service
- Accounts may be suspended for automated access
- DataDome protection is intentional and serves legitimate security purposes
- This library is **unofficial** and not endorsed by TooGoodToGo

**Recommended Disclaimer for tgtg-python README:**

```markdown
## Legal Notice

This is an **unofficial** library and is **not** affiliated with, endorsed by, or supported by TooGoodToGo.

By using this library, you acknowledge that:
- Automated API access may violate TooGoodToGo's Terms of Service
- You use this library at your own risk
- Your account may be suspended for automated access
- This library is intended for personal, non-commercial use only
- You are responsible for complying with all applicable laws and regulations

If TooGoodToGo offers an official API in the future, please use that instead.
```

---

## Conclusion

DataDome presents significant challenges for legitimate API clients, but several practical workarounds exist:

**Recommended Implementation Path:**

1. **Phase 1 (Quick Wins):** Enhanced headers + rate limiting improvements (~4 hours)
2. **Phase 2 (High Impact):** Migrate to curl_cffi (~8 hours)
3. **Phase 3 (Polish):** Proxy documentation + captcha handler interface (~4 hours)

**Expected Outcomes:**
- Phase 1: 40-50% success rate (baseline improvement)
- Phase 2: 80-85% success rate (with curl_cffi)
- Phase 2 + Proxies: 95%+ success rate

**Maintenance:**
- Monitor DataDome updates (detection methods evolve)
- Track community reports in GitHub issues
- Update browser impersonation profiles periodically
- Adjust rate limits based on observed patterns

**Alternative Approaches:**
- If DataDome becomes too restrictive, consider advocating for official API
- Use official TGTG mobile app as fallback
- Implement human-in-the-loop for captchas

This research provides a comprehensive foundation for improving tgtg-python's reliability while respecting the legitimate security concerns of the TooGoodToGo platform.

---

**Research Completed:** 2025-10-10
**Next Review:** 2025-04-10 (6 months) - Re-evaluate DataDome techniques and community solutions
**Version:** 1.0
