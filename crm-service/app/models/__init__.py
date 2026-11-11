# Import every model so SQLAlchemy can resolve string-based relationships
# (e.g. Customer.orders -> "Order") no matter which model is imported first.
from app.models.customer import Customer  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.segment import Segment  # noqa: F401
from app.models.campaign import Campaign  # noqa: F401
from app.models.communication import Communication  # noqa: F401
