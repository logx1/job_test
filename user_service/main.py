import os
import json
import pika
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from passlib.context import CryptContext

# --- Configuration ---
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://root:root@localhost/")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "app_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "app_password")
MYSQL_DB = os.getenv("MYSQL_DB", "app_db")
SQLALCHEMY_DATABASE_URL = f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"

# SQLAlchemy
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Models ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))

# --- Pydantic Schemas ---
class UserCreate(BaseModel):
    username: str
    password: str

class UserUpdate(BaseModel):
    username: str = None
    password: str = None

class UserSchema(BaseModel):
    id: int
    username: str
    
    class Config:
        from_attributes = True

# --- FastAPI App ---
app = FastAPI()
rabbitmq_connection = None
rabbitmq_channel = None

# --- RabbitMQ Connection ---
def get_rabbitmq_connection():
    global rabbitmq_connection, rabbitmq_channel
    if rabbitmq_connection is None or rabbitmq_connection.is_closed:
        params = pika.URLParameters(RABBITMQ_URL)
        rabbitmq_connection = pika.BlockingConnection(params)
        rabbitmq_channel = rabbitmq_connection.channel()
        rabbitmq_channel.queue_declare(queue="user_events", durable=True)

# --- RabbitMQ Publishing ---
def publish_user_event(action: str, user_data: dict):
    get_rabbitmq_connection()
    message_body = json.dumps({
        "action": action,
        "user": user_data
    })
    rabbitmq_channel.basic_publish(
        exchange="",
        routing_key="user_events",
        body=message_body,
        properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
    )

# --- Database Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Endpoints ---
@app.post("/users", response_model=UserSchema)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = pwd_context.hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    user_data = {
        "id": new_user.id,
        "username": new_user.username
    }
    publish_user_event("create", user_data)
    
    return new_user

@app.get("/users", response_model=list[UserSchema])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@app.get("/users/{user_id}", response_model=UserSchema)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@app.put("/users/{user_id}", response_model=UserSchema)
def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user.dict(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = pwd_context.hash(update_data.pop("password"))
    
    for key, value in update_data.items():
        setattr(db_user, key, value)
        
    db.commit()
    db.refresh(db_user)
    
    user_data = {
        "id": db_user.id,
        "username": db_user.username
    }
    publish_user_event("update", user_data)
    
    return db_user

@app.delete("/users/{user_id}", response_model=UserSchema)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_data = {
        "id": db_user.id,
        "username": db_user.username
    }
    
    db.delete(db_user)
    db.commit()
    
    publish_user_event("delete", user_data)
    
    return db_user

# --- Startup & Shutdown ---
@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    get_rabbitmq_connection()

@app.on_event("shutdown")
def shutdown_event():
    global rabbitmq_connection
    if rabbitmq_connection:
        rabbitmq_connection.close()