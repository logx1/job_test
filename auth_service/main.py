from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import jwt, asyncio, os
import pika
from redis.asyncio import Redis

app = FastAPI()

SECRET_KEY = "supersecret"
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

redis = Redis(host=REDIS_HOST, port=6379, decode_responses=True)

class LoginRequest(BaseModel):
    username: str
    password: str


@app.on_event("startup")
async def startup():
    # Initialize RabbitMQ connection and channel
    def init_rabbitmq():
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue="user_queue")
        return connection, channel

    app.rabbit_conn, app.channel = await asyncio.to_thread(init_rabbitmq)


@app.on_event("shutdown")
async def shutdown():
    # Close RabbitMQ connection on shutdown
    def close_rabbitmq():
        app.channel.close()
        app.rabbit_conn.close()

    await asyncio.to_thread(close_rabbitmq)


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

    # Publish message to RabbitMQ
    def publish_message():
        app.channel.basic_publish(
            exchange="",
            routing_key="user_queue",
            body=message,
        )

    await asyncio.to_thread(publish_message)
    return {"status": "sent", "message": message}