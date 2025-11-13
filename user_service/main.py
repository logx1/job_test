import asyncio
import os
import threading
import pika
from fastapi import FastAPI
from redis.asyncio import Redis

RABBITMQ_URL = os.getenv("RABBITMQ_URL")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")

app = FastAPI()
redis = Redis(host=REDIS_HOST, port=6379, decode_responses=True)

# -------- RabbitMQ Consumer --------
def process_message(ch, method, properties, body):
    message = body.decode()
    print(f"[User Service] Received: {message}")
    asyncio.run(store_message_in_redis(message))

async def store_message_in_redis(message):
    await redis.set("last_message", message)

def consume():
    connection_params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()
    channel.queue_declare(queue="user_queue")
    channel.basic_consume(queue="user_queue", on_message_callback=process_message, auto_ack=True)
    print("[User Service] Waiting for messages...")
    channel.start_consuming()

def start_consumer_thread():
    thread = threading.Thread(target=consume, daemon=True)
    thread.start()

@app.on_event("startup")
async def startup_event():
    await asyncio.to_thread(start_consumer_thread)  # Start consumer in a separate thread

# -------- HTTP API --------
@app.get("/last")
async def get_last_message():
    msg = await redis.get("last_message")
    return {"last_message": msg}