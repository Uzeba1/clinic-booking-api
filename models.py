from sqlalchemy import Column, String, DateTime, Boolean
from database import Base

class Slot(Base):
    __tablename__ = "slots"
    id = Column(String, primary_key=True, index=True)
    start_time = Column(DateTime, nullable=False)
    is_booked = Column(Boolean, default=False)

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(String, primary_key=True, index=True)
    slot_id = Column(String, nullable=False)
    patient_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    status = Column(String, default="confirmed")  # confirmed / cancelled
    idempotency_key = Column(String, unique=True, nullable=True)