from datetime import datetime
import os
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# 1. Database Configuration (SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///./clinic.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 2. SQLAlchemy Appointment Model
class AppointmentModel(Base):
  __tablename__ = "appointments"

  id = Column(Integer, primary_key=True, index=True)
  patient_name = Column(String, index=True)
  doctor = Column(String)
  date = Column(String)
  time = Column(String)
  created_at = Column(DateTime, default=datetime.utcnow)


# Create database tables automatically on startup
Base.metadata.create_all(bind=engine)

# 3. FastAPI App Initialization
app = FastAPI(
    title="Clinic Booking API",
    description="Koya AI Automation Developer Cohort 4 Project",
    version="1.0.0",
)

# 4. Mount Static Directory & Serve Root HTML
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def read_root():
  return FileResponse("static/index.html")


# 5. Dependency to get DB session
def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()


# 6. Pydantic Schemas for Validation
class AppointmentCreate(BaseModel):
  patient_name: str
  doctor: str
  date: str
  time: str


class AppointmentResponse(AppointmentCreate):
  id: int

  class Config:
    from_attributes = True


# 7. API Key Security Header Verification
API_KEY = os.getenv("API_KEY", "koya-cohort4-gumysecretkey-2026")


def verify_api_key(x_api_key: str = Header(...)):
  if x_api_key != API_KEY:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key header (X-API-Key)",
    )
  return x_api_key


# 8. API Endpoints
@app.post(
    "/api/appointments", response_model=AppointmentResponse, status_code=201
)
def create_appointment(
    appointment: AppointmentCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
  db_appointment = AppointmentModel(
      patient_name=appointment.patient_name,
      doctor=appointment.doctor,
      date=appointment.date,
      time=appointment.time,
  )
  db.add(db_appointment)
  db.commit()
  db.refresh(db_appointment)
  return db_appointment


@app.get("/api/appointments", response_model=list[AppointmentResponse])
def get_appointments(
    db: Session = Depends(get_db), api_key: str = Depends(verify_api_key)
):
  appointments = db.query(AppointmentModel).all()
  return appointments