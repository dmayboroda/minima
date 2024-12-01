#!/bin/bash

echo "Select an option:"
echo "1) Fully Local Setup"
echo "2) ChatGPT Integration"
echo "3) MCP usage"
echo "4) Quit"

read -p "Enter your choice (1, 2, 3 or 4): " user_choice

case "$user_choice" in
    1)
        echo "Starting fully local setup..."
        docker compose -f docker-compose-ollama.yml --env-file .env up --build
        ;;
    2)
        echo "Starting with ChatGPT integration..."
        docker compose -f docker-compose-chatgpt.yml --env-file .env up --build
        ;;
    3)
        echo "Exiting the script. Goodbye!"
        docker compose -f docker-compose-mcp.yml --env-file .env up --build
        ;;
    4)
        echo "Exiting the script. Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid input. Please enter 1, 2, or 3."
        ;;
esac