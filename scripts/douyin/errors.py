class DouyinError(Exception):
    pass


class CDPError(DouyinError):
    pass


class ElementNotFoundError(DouyinError):
    def __init__(self, selector: str) -> None:
        super().__init__(f"未找到元素: {selector}")
        self.selector = selector
