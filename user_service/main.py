import asyncio
import os
import aio_pika
from fastapi import FastAPI
from redis.asyncio import Redis

RABBITMQ_URL = os.getenv("RABBITMQ_URL")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

app = FastAPI()
redis = Redis(host=REDIS_HOST, port=6379, decode_responses=True)

# -------- RabbitMQ Consumer --------
async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        body = message.body.decode()
        print(f"[User Service] Received: {body}")
        await redis.set("last_message", body)

async def consume():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    queue = await channel.declare_queue("user_queue")
    await queue.consume(process_message)
    print("[User Service] Waiting for messages...")
    await asyncio.Future()  # keep running

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(consume())  # Start consumer in background

# -------- HTTP API --------
@app.get("/last")
async def get_last_message():
    msg = await redis.get("last_message")
    return {"last_message": msg}
