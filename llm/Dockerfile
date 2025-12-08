FROM python:3.11-slim-buster

WORKDIR /usr/src/app

ARG RERANKER_MODEL

RUN pip install --upgrade pip
COPY requirements.txt .
# Install latest huggingface-hub with CLI support
RUN pip install --upgrade "huggingface_hub[cli]"
# Only download reranker if RERANKER_MODEL is set (for Ollama mode)
RUN if [ -n "$RERANKER_MODEL" ]; then \
        hf download $RERANKER_MODEL; \
    else \
        echo "Skipping reranker download (not needed for custom LLM mode)"; \
    fi
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT 8000
ENV CURRENT_HOST 0.0.0.0
ENV WORKERS 1

CMD ["sh", "-c", "uvicorn app:app --loop asyncio --reload --workers ${WORKERS} --host $CURRENT_HOST --port $PORT --proxy-headers"]