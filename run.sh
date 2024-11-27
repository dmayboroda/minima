#!/bin/bash

echo "Run fully local or ChatGPT integration? (Y - fully local, N - ChatGPT integration)"
read -p "Enter Y or N: " user_choice

user_choice=$(echo "$user_choice" | tr '[:lower:]' '[:upper:]')

if [ "$user_choice" == "Y" ]; then
    echo "Starting fully local setup..."
    docker compose -f docker-compose-ollama.yml --env-file .env up --build
elif [ "$user_choice" == "N" ]; then
    echo "Starting with ChatGPT integration..."
    docker compose --env-file .env up --build
else
    echo "Invalid input. Please enter Y or N."
fi