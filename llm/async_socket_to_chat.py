import json
import logging
from fastapi import WebSocket
from async_queue import AsyncQueue
import starlette.websockets as ws
import control_flow_commands as cfc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat")

async def loop(
    websocket: WebSocket, 
    questions_queue: AsyncQueue,
    respone_queue: AsyncQueue
):

    await websocket.accept()
    while True:
        try:
            message = await websocket.receive_text()

            if message == cfc.CFC_CHAT_STARTED:
                logger.info(f"Start message {message}")
                questions_queue.enqueue(message)

            elif message == cfc.CFC_CHAT_STOPPED:
                logger.info(f"Stop message {message}")
                questions_queue.enqueue(message)
                respone_queue.enqueue(json.dumps({
                    "reporter": "input_message",
                    "type": "stop_message",
                    "message": message
                }))

            else:
                logger.info(f"Question: {message}")
                questions_queue.enqueue(message)
                respone_queue.enqueue(json.dumps({
                    "reporter": "input_message",
                    "type": "question",
                    "message": message
                }))
                
        except ws.WebSocketDisconnect as e:
            logger.info("Client disconnected")
            questions_queue.enqueue(cfc.CFC_CLIENT_DISCONNECTED)
            respone_queue.enqueue(cfc.CFC_CLIENT_DISCONNECTED)
            break