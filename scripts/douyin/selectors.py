from .adapter import DEFAULT_ADAPTER

_SELECTORS = DEFAULT_ADAPTER.selectors

# Compatibility exports for callers that used the old Douyin-only module.
LOGIN_TEXT_KEYWORDS = list(_SELECTORS.login_text_keywords)
LOGGED_IN_TEXT_HINTS = list(_SELECTORS.logged_in_text_hints)
SEARCH_RESULT_SELECTORS = list(_SELECTORS.search_result_selectors)
DETAIL_DESC_SELECTORS = list(_SELECTORS.detail_desc_selectors)
COMMENT_ITEM_SELECTORS = list(_SELECTORS.comment_item_selectors)
LIKE_BUTTON_SELECTORS = list(_SELECTORS.like_button_selectors)
