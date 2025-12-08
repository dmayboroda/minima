#!/bin/bash

echo "Select an option:"
echo "1) Fully Local Setup (Ollama)"
echo "2) Custom LLM (OpenAI-compatible API)"
echo "3) ChatGPT Integration"
echo "4) MCP usage"
echo "5) Quit"

read -p "Enter your choice (1, 2, 3, 4 or 5): " user_choice

case "$user_choice" in
    1)
        echo "Starting fully local setup with Ollama..."
        docker compose -f docker-compose-ollama.yml --env-file .env up --build
        ;;
    2)
        echo "Starting with custom LLM (OpenAI-compatible API)..."
        echo "Make sure your .env file has LLM_BASE_URL and LLM_MODEL set."
        docker compose -f docker-compose-custom-llm.yml --env-file .env up --build
        ;;
    3)
        echo "Starting with ChatGPT integration..."
        docker compose -f docker-compose-chatgpt.yml --env-file .env up --build
        ;;
    4)
        echo "Starting MCP server..."
        docker compose -f docker-compose-mcp.yml --env-file .env up --build
        ;;
    5)
        echo "Exiting the script. Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid input. Please enter 1, 2, 3, 4, or 5."
        ;;
esac