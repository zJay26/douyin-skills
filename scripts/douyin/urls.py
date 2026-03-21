from urllib.parse import quote

HOME_URL = "https://www.douyin.com/"
JINGXUAN_URL = "https://www.douyin.com/jingxuan"
CREATOR_URL = "https://creator.douyin.com/creator-micro/home"
SEARCH_BASE = "https://www.douyin.com/search/"
TRENDING_URL = "https://www.douyin.com/hot"


def search_url(keyword: str) -> str:
    return f"{SEARCH_BASE}{quote(keyword)}?type=video"


def jingxuan_url() -> str:
    return JINGXUAN_URL


def video_url(video_id: str) -> str:
    return f"https://www.douyin.com/video/{video_id}"


def note_url(note_id: str) -> str:
    return f"https://www.douyin.com/note/{note_id}"


def trending_url() -> str:
    return TRENDING_URL
