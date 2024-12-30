import json
import logging
from llm_chain import LLMChain
from async_queue import AsyncQueue
import control_flow_commands as cfc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat")

async def loop(
        questions_queue: AsyncQueue,
        response_queue: AsyncQueue,
):

    llm_chain = LLMChain()

    while True:
        data = await questions_queue.dequeue()
        data = data.replace("\n", "")

        if data == cfc.CFC_CLIENT_DISCONNECTED:
            response_queue.enqueue(
                json.dumps({
                    "reporter": "output_message",
                    "type": "disconnect_message",
                })
            )
            break

        if data == cfc.CFC_CHAT_STARTED:
            response_queue.enqueue(
                json.dumps({
                    "reporter": "output_message",
                    "type": "start_message",
                })
            )
            
        elif data == cfc.CFC_CHAT_STOPPED:
            response_queue.enqueue(
                json.dumps({
                    "reporter": "output_message",
                    "type": "stop_message",
                })
            )
            
        elif data:
            result = llm_chain.invoke(data)
            response_queue.enqueue(
                json.dumps({
                    "reporter": "output_message",
                    "type": "answer",
                    "message": result["answer"],
                    "links": list(result["links"])
                })
            )