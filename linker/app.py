import os
import logging
import asyncio
import random
import string
from fastapi import FastAPI
from requestor import request_data
from contextlib import asynccontextmanager

import json
import requests

from requests.exceptions import HTTPError
from google.oauth2.credentials import Credentials
from google.cloud.firestore import Client


def sign_in_with_email_and_password(email, password):
    request_url = "https://signinaction-xl7gclbspq-uc.a.run.app"
    headers = {"content-type": "application/json; charset=UTF-8"}
    data = json.dumps({"login": email, "password": password})
    req = requests.post(request_url, headers=headers, data=data)
    try:
        req.raise_for_status()
    except HTTPError as e:
        raise HTTPError(e, "error")
    return req.json()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USERS_COLLECTION_NAME = "users_otp"
COLLECTION_NAME = os.environ.get("FIRESTORE_COLLECTION_NAME")
TASKS_COLLECTION = os.environ.get("TASKS_COLLECTION")
USER_ID = os.environ.get("USER_ID")
PASSWORD = os.environ.get("PASSWORD")
FB_PROJECT = os.environ.get("FB_PROJECT")

app = FastAPI()
response = sign_in_with_email_and_password(USER_ID, PASSWORD)
creds = Credentials(response["idToken"], response["refreshToken"])
# noinspection PyTypeChecker
db = Client(FB_PROJECT, creds)


async def poll_firestore():
    logger.info(f"Polling Firestore collection: {COLLECTION_NAME}")
    random_otp = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    doc_ref = db.collection(USERS_COLLECTION_NAME).document(USER_ID)
    try:
        doc_ref.update({'otp': random_otp})
    except Exception as e:
        print("The error is: ", e)

    if doc_ref.get().exists:
        doc_ref.update({'otp': random_otp})
    else:
        doc_ref.create({'otp': random_otp})
    
    while True:
        print(f"OTP for this computer in Minima GPT: {random_otp}")
        try:
            docs = db.collection(COLLECTION_NAME).document(USER_ID).collection(TASKS_COLLECTION).stream()
            for doc in docs:
                data = doc.to_dict()
                if data['status'] == 'PENDING':
                    response = await request_data(data['request'])
                    if 'error' not in response:
                        logger.info(f"Updating Firestore document: {doc.id}")
                        doc_ref = db.collection(COLLECTION_NAME).document(USER_ID).collection(TASKS_COLLECTION).document(doc.id)
                        doc_ref.update({
                            'status': 'COMPLETED',
                            'links': response['result']['links'],
                            'result': response['result']['output']
                        })
                    else:
                        logger.error(f"Error in processing request: {response['error']}")
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error in polling Firestore collection: {e}")
            await asyncio.sleep(0.5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Firestore polling")
    poll_task = asyncio.create_task(poll_firestore())
    yield
    poll_task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        openapi_url="/linker/openapi.json",
        docs_url="/linker/docs",
        lifespan=lifespan
    )
    return app

app = create_app()