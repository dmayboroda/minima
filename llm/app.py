import logging
import asyncio
from fastapi import FastAPI
from fastapi import WebSocket
from llm_chain import LLMChain
from async_queue import AsyncQueue

import async_socket_to_chat
import async_question_to_answer
import async_answer_to_socket

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm")

@app.websocket("/llm/")
async def chat_client(websocket: WebSocket):

    question_queue = AsyncQueue()
    response_queue = AsyncQueue()

    answer_to_socket_promise = async_answer_to_socket.loop(response_queue, websocket)
    question_to_answer_promise = async_question_to_answer.loop(question_queue, response_queue)
    socket_to_chat_promise = async_socket_to_chat.loop(websocket, question_queue, response_queue)

    await asyncio.gather(
        answer_to_socket_promise,
        question_to_answer_promise,
        socket_to_chat_promise,
    )