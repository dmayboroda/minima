FROM python:3.11-slim-buster

WORKDIR /usr/src/app
RUN pip install --upgrade pip

ARG EMBEDDING_MODEL_ID

RUN pip install huggingface_hub
RUN huggingface-cli download $EMBEDDING_MODEL_ID --repo-type model

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install einops datasets
COPY . .

ENV PORT 8000
ENV CURRENT_HOST 0.0.0.0
ENV WORKERS 1

CMD ["sh", "-c", "uvicorn app:app --loop asyncio --reload --workers ${WORKERS} --host $CURRENT_HOST --port $PORT --proxy-headers"]