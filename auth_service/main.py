from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import jwt, asyncio, os
import aio_pika
from redis.asyncio import Redis

app = FastAPI()

SECRET_KEY = "supersecret"
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

redis = Redis(host=REDIS_HOST, port=6379, decode_responses=True)

class LoginRequest(BaseModel):
    username: str
    password: str


@app.on_event("startup")
async def startup():
    app.rabbit_conn = await aio_pika.connect_robust(RABBITMQ_URL)
    app.channel = await app.rabbit_conn.channel()
    await app.channel.declare_queue("user_queue")


@app.post("/login")
async def login(data: LoginRequest):
    if data.username == "admin" and data.password == "1234":
        token = jwt.encode({"user": data.username}, SECRET_KEY, algorithm="HS256")
        await redis.set(f"token:{data.username}", token)
        return {"token": token}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/send")
async def send_message(username: str):
    token = await redis.get(f"token:{username}")
    if not token:
        raise HTTPException(status_code=401, detail="User not logged in")

    message = f"Hello from {username}"
    await app.channel.default_exchange.publish(
        aio_pika.Message(body=message.encode()), routing_key="user_queue"
    )
    return {"status": "sent", "message": message}
