"""Vision-watch agent configuration."""

import os


DATA_DIR = os.environ.get("HIPEAC_AGENTS_DATA_DIR", "./data/vision_watch")

AGENTMAIL_INBOX_VISION_WATCH = os.environ.get("AGENTMAIL_INBOX_VISION_WATCH")
HIPEAC_VISION_BOARD_EMAIL = os.environ.get("HIPEAC_VISION_BOARD_EMAIL")
HIPEAC_VISION_REPLY_TO = os.environ.get("HIPEAC_VISION_REPLY_TO")
HEALTH_ALERT_TO = os.environ.get("HIPEAC_AGENTS_HEALTH_ALERT_TO", "dev@hipeac.net")
HIPEAC_VISION_TIPS_MAILBOX = os.environ.get("HIPEAC_VISION_TIPS_MAILBOX", "tips@example.com")
