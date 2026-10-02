from dataclasses import dataclass
from .config import settings

@dataclass
class RiskDecision:
    allowed: bool
    reason: str

def validate_order(notional_krw: int, daily_loss_krw: int = 0) -> RiskDecision:
    if notional_krw <= 0:
        return RiskDecision(False, "order value must be positive")
    if notional_krw > settings.max_order_krw:
        return RiskDecision(False, "MAX_ORDER_KRW exceeded")
    if daily_loss_krw >= settings.max_daily_loss_krw:
        return RiskDecision(False, "daily loss limit reached")
    return RiskDecision(True, "ok")
