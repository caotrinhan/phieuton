from datetime import datetime
from zoneinfo import ZoneInfo


VIETNAM_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def local_now() -> datetime:
    return datetime.now(VIETNAM_TIMEZONE).replace(tzinfo=None)