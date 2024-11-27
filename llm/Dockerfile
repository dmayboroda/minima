FROM python:3.9.6-slim-buster

WORKDIR /usr/src/app

RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install huggingface_hub
RUN huggingface-cli download BAAI/bge-reranker-base --repo-type model
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT 8000
ENV CURRENT_HOST 0.0.0.0
ENV WORKERS 1

CMD ["sh", "-c", "uvicorn app:app --loop asyncio --reload --workers ${WORKERS} --host $CURRENT_HOST --port $PORT --proxy-headers"]