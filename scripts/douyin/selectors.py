LOGIN_TEXT_KEYWORDS = ["登录", "立即登录", "扫码登录", "手机号登录"]
LOGGED_IN_TEXT_HINTS = ["消息", "朋友", "关注", "推荐", "创作者服务中心", "投稿", "私信", "客户端"]

SEARCH_RESULT_SELECTORS = [
    'a[href*="/video/"]',
    'a[href*="/note/"]',
    '[data-e2e="search-result-item"] a',
]

DETAIL_DESC_SELECTORS = [
    '[data-e2e="video-desc"]',
    'h1 span span span span span',
    'div[class*="title"] span',
]

COMMENT_ITEM_SELECTORS = [
    '[data-e2e="comment-item"]',
    '[class*="comment"] [class*="item"]',
    'div[class*="comment"] li',
]

LIKE_BUTTON_SELECTORS = [
    '[data-e2e="video-player-digg"]',
    '[data-e2e="feed-digg-icon"]',
    '[class*="video-player-digg"]',
    'button[data-e2e*="like"]',
    '[class*="like"] button',
    'div[role="button"][aria-label*="赞"]',
]
