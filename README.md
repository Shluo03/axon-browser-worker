# Axon Browser Worker

Browser automation worker for WeCrew-AXON. Enables social media automation for platforms without API access (Xiaohongshu, Douyin, etc.) via AdsPower + Selenium.

## Architecture

```
AXON Backend → Temporal → Browser Worker → AdsPower → Platform
```

## Structure

```
src/
├── adspower/       # AdsPower API client
│   └── client.py   # Start/stop browser profiles
├── browser/        # Browser control
│   ├── session.py  # Lifecycle management
│   └── humanize.py # Human-like interactions
├── platforms/      # Platform implementations
│   ├── base.py     # Interface (mirrors SocialProvider)
│   └── xiaohongshu.py
└── llm/            # LLM assistance (exception handling only)
    └── agent.py    # DecisionAgent for unknown states
```

## Usage

```python
from src.browser import BrowserSession
from src.platforms import XiaohongshuPlatform

with BrowserSession("profile_id") as session:
    platform = XiaohongshuPlatform(session.driver)

    # Warmup
    stats = platform.warmup(duration_minutes=5)

    # Post
    result = platform.post({
        "title": "标题",
        "message": "内容",
        "tags": ["tag1", "tag2"]
    })
```

## Test

```bash
# Ensure AdsPower is running
python3 test_integration.py
```

## Next Steps

1. Add more platforms (Douyin, Weibo)
2. Integrate with AXON Temporal workflows
3. Add warmup scheduling
