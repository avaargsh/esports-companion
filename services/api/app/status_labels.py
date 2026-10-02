PLAYER_VERIFICATION_STATUS_TEXT = {
    "PENDING": "待审核",
    "APPROVED": "审核通过",
    "REJECTED": "审核驳回",
    "CANCELLED": "资格已取消",
}

PLAYER_SKILL_STATUS_TEXT = {
    "PENDING": "待审核",
    "APPROVED": "审核通过",
    "REJECTED": "审核驳回",
    "REVOKED": "已撤销",
}

SERVICE_STATUS_TEXT = {
    "AVAILABLE": "可接单",
    "OFFLINE": "暂停接单",
    "SUSPENDED": "已停用",
}

COMMON_STATUS_TEXT = {
    "ACTIVE": "启用",
    "INACTIVE": "停用",
    "PENDING": "待处理",
    "PROCESSING": "处理中",
    "SUBMITTING": "提交中",
    "COMPLETED": "已完成",
    "FAILED": "失败",
    "REJECTED": "已拒绝",
    "SUCCESS": "成功",
    "CLOSED": "已关闭",
    "ABNORMAL": "异常",
}

ORDER_STATUS_TEXT = {
    "WAITING_PAYMENT": "待支付",
    "PAID": "已支付",
    "MATCHING": "待接单",
    "ACCEPTED": "已接单",
    "IN_SERVICE": "服务中",
    "FINISH_REQUESTED": "待确认完成",
    "COMPLETED": "已完成",
    "SETTLED": "已结算",
    "CANCELLED": "已取消",
    "REFUNDING": "退款处理中",
    "REFUNDED": "已退款",
    "DISPUTED": "争议处理中",
}

DISPUTE_STATUS_TEXT = {
    "OPEN": "待处理",
    "RESOLVING": "处理中",
    "RESOLVED": "已处理",
}

ACTION_STATUS_TEXT = {
    **COMMON_STATUS_TEXT,
    **ORDER_STATUS_TEXT,
    **DISPUTE_STATUS_TEXT,
    **PLAYER_VERIFICATION_STATUS_TEXT,
    **PLAYER_SKILL_STATUS_TEXT,
    **SERVICE_STATUS_TEXT,
}


def status_text(value: str | None, mapping: dict[str, str] | None = None) -> str:
    if not value:
        return ""
    source = mapping or ACTION_STATUS_TEXT
    return source.get(value, value)
