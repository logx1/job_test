import os
import asyncio
import jwt
import pika
from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from passlib.context import CryptContext
from redis.asyncio import Redis

# --- Configuration ---
SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "app_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "app_password")
MYSQL_DB = os.getenv("MYSQL_DB", "app_db")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://root:root@localhost/")

SQLALCHEMY_DATABASE_URL = f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"

# --- Initialization ---
app = FastAPI()
redis = Redis(host=REDIS_HOST, port=6379, decode_responses=True)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Database ---
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Schemas ---
class LoginRequest(BaseModel):
    username: str
    password: str

# --- Endpoints ---
@app.post("/login")
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not pwd_context.verify(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = jwt.encode({"user": data.username}, SECRET_KEY, algorithm="HS256")
    await redis.set(f"token:{data.username}", token)
    return {"token": token}

@app.post("/logout")
async def logout(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("user")
        if await redis.delete(f"token:{username}"):
            return {"status": "logout successful"}
        raise HTTPException(status_code=400, detail="User not logged in or token expired")
    except (jwt.PyJWTError, IndexError):
        raise HTTPException(status_code=401, detail="Invalid token")

# --- Startup ---
@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)




def callback(ch, method, properties, body):
    print(f"[Receiver] Received: {body.decode()}")
    # Acknowledge the message
    ch.basic_ack(delivery_tag=method.delivery_tag)

def receive_messages():
    parameters = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue='user_events', durable=True)

    print("[Receiver] Waiting for messages. To exit, press CTRL+C")
    channel.basic_consume(queue='user_events', on_message_callback=callback)

    
    channel.start_consuming()

@app.on_event("startup")
def start_message_receiver():
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, receive_messages)