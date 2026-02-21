POLL_INTERVAL_SECONDS: int = 30
REQUEST_TIMEOUT_SECONDS: int = 10
MAX_RETRIES: int = 5
RETRY_BASE_DELAY_SECONDS: int = 2   # delay = base * 2^n, capped at MAX_RETRY_DELAY_SECONDS
MAX_RETRY_DELAY_SECONDS: int = 300  # 5 minutes

# add statuspage.io pages
STATUS_PAGES: list[dict[str, str]] = [
    {
        "name": "OpenAI",
        "api_base": "https://status.openai.com/api/v2",
    },
    # {
    #     "name": "Anthropic",
    #     "api_base": "https://status.anthropic.com/api/v2",
    # },
]