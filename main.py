import os
from fastapi import FastAPI, Depends, HTTPException, Header, status, Query
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv

from database import engine, Base, get_db
import models

load_dotenv()
Base.metadata.create_all(bind=engine)

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

app = FastAPI(
    title="Clinic Booking API",
    version="1.0",
    swagger_ui_parameters={"persistAuthorization": True}
)

# API Key configuration
API_KEY = os.getenv("API_KEY", "my-secret-koya-key-123")

def verify_api_key(x_api_key: str = Depends(api_key_header)):
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid or missing API key"}
        )
    return x_api_key

# Pydantic Schemas
class SlotModel(BaseModel):
    id: str
    start_time: datetime

class ResetRequest(BaseModel):
    slots: List[SlotModel]

class BookingRequest(BaseModel):
    slot_id: str
    patient_name: str
    email: str
    idempotency_key: Optional[str] = None

# Level 1: Reset all slots
@app.post("/reset", dependencies=[Depends(verify_api_key)])
def reset_slots(payload: ResetRequest, db: Session = Depends(get_db)):
    # Clear existing bookings and slots
    db.query(models.Booking).delete()
    db.query(models.Slot).delete()
    db.commit()

    for s in payload.slots:
        new_slot = models.Slot(id=s.id, start_time=s.start_time, is_booked=False)
        db.add(new_slot)
    db.commit()
    return {"message": "Slots reset successfully", "count": len(payload.slots)}

# Level 1: List slots
@app.get("/slots", dependencies=[Depends(verify_api_key)])
def list_slots(db: Session = Depends(get_db)):
    slots = db.query(models.Slot).all()
    return slots

# Levels 1-5: Book a slot with concurrency & idempotency handling
@app.post("/bookings", dependencies=[Depends(verify_api_key)])
def create_booking(payload: BookingRequest, db: Session = Depends(get_db)):
    # Check idempotency key if provided (Level 4)
    if payload.idempotency_key:
        existing_booking = db.query(models.Booking).filter(
            models.Booking.idempotency_key == payload.idempotency_key
        ).first()
        if existing_booking:
            return existing_booking

    # Check if slot exists
    slot = db.query(models.Slot).filter(models.Slot.id == payload.slot_id).first()
    if not slot:
        raise HTTPException(status_code=400, detail={"error": "Slot not found"})
    
    if slot.is_booked:
        raise HTTPException(status_code=400, detail={"error": "Slot is already booked"})

    # Mark slot as booked
    slot.is_booked = True
    
    # Create booking record
    import uuid
    booking_id = str(uuid.uuid4())
    new_booking = models.Booking(
        id=booking_id,
        slot_id=payload.slot_id,
        patient_name=payload.patient_name,
        email=payload.email,
        status="confirmed",
        idempotency_key=payload.idempotency_key
    )
    
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return new_booking

# Level 4: List a person's bookings by email
@app.get("/bookings", dependencies=[Depends(verify_api_key)])
def list_bookings(email: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(models.Booking)
    if email:
        query = query.filter(models.Booking.email == email)
    return query.all()

# Level 1: Get a booking by ID
@app.get("/bookings/{id}", dependencies=[Depends(verify_api_key)])
def get_booking(id: str, db: Session = Depends(get_db)):
    booking = db.query(models.Booking).filter(models.Booking.id == id).first()
    if not booking:
        raise HTTPException(status_code=404, detail={"error": "Booking not found"})
    return booking

# Level 3: Cancel a booking
@app.delete("/bookings/{id}", dependencies=[Depends(verify_api_key)])
def cancel_booking(id: str, db: Session = Depends(get_db)):
    booking = db.query(models.Booking).filter(models.Booking.id == id).first()
    if not booking:
        raise HTTPException(status_code=404, detail={"error": "Booking not found"})
    
    if booking.status == "cancelled":
        return {"message": "Booking is already cancelled"}

    # Free up the slot
    slot = db.query(models.Slot).filter(models.Slot.id == booking.slot_id).first()
    if slot:
        slot.is_booked = False

    booking.status = "cancelled"
    db.commit()
    return {"message": "Booking cancelled successfully"}