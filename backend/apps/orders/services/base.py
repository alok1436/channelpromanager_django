from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OrderSyncResult:
    orders_created: int = 0
    orders_updated: int = 0
    items_created: int = 0
    items_updated: int = 0

    def as_dict(self):
        return asdict(self)


class BaseOrderService(ABC):
    def __init__(self, channel):
        self.channel = channel

    @abstractmethod
    def download_orders(self, *, updated_after=None):
        raise NotImplementedError
