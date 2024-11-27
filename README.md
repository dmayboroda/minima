**Minima** is an open source fully local RAG.

Minima supports 2 modes right now. You can use fully local (minimal) installation or you can use custom GPT to query your local documents via chat GPT.

1. Create a .env file in the project’s root directory (where you’ll find env.sample). Place .env in the same folder and copy all environment variables from env.sample to .env.

2. Ensure your .env file includes the following variables:
<ul>
   <li> LOCAL_FILES_PATH </li>
   <li> EMBEDDING_MODEL_ID </li>
   <li> EMBEDDING_SIZE</li>
   <li> START_INDEXING </li>
<li> USER_ID </li> - required for chat GPT integration, just use your email
<li> PASSWORD </li> - required for chat GPT integration, just use any password
</ul>

3. For fully local installation use: docker compose -f docker-compose-ollama.yml --env-file .env up --build.

4. For chat GPT enabled installation use: docker compose --env-file .env up --build.

5. For fully local installation, connect to **ws://localhost:8003/llm/** to start a conversation with LLM.

6. For chat GPT enabled installation copy OTP from terminal where you launched docker and use [Minima GPT](https://chatgpt.com/g/g-r1MNTSb0Q-minima-local-computer-search)  
   
7. Ask anything, and you'll get answers based on local files in {LOCAL_FILES_PATH} folder.



Explanation of Variables:

**LOCAL_FILES_PATH**: Specify the root folder for indexing. Indexing is a recursive process, meaning all documents within subfolders of this root folder will also be indexed. Supported file types: .pdf, .xls, .docx, .txt, .md, .csv.

**EMBEDDING_MODEL_ID**: Specify the embedding model to use. Currently, only Sentence Transformer models are supported. Testing has been done with sentence-transformers/all-mpnet-base-v2, but other Sentence Transformer models can be used.

**EMBEDDING_SIZE**: Define the embedding dimension provided by the model, which is needed to configure Qdrant vector storage. Ensure this value matches the actual embedding size of the specified EMBEDDING_MODEL_ID.

**START_INDEXING**: Set this to ‘true’ on initial startup to begin indexing. Data can be queried while it indexes. Note that reindexing is not yet supported. To reindex, remove the qdrant_data folder (created automatically), set this flag to ‘true,’ and restart the containers. After indexing completes, you can keep the container running or restart without reindexing by setting this flag to ‘false’.

**USER_ID**: Just use your email here, this is needed to authenticate custom GPT to search in your data.

**PASSWORD**: Put any password here, this is used to create a firebase account for the email specified above.


Example of .env file for fully local usage:
```
LOCAL_FILES_PATH=/Users/davidmayboroda/Downloads/PDFs/
EMBEDDING_MODEL_ID=sentence-transformers/all-mpnet-base-v2
EMBEDDING_SIZE=768
START_INDEXING=false # true on the first run for indexing
```

Ollama chatting model - **qwen2:0.5b** (hard coded, but we will provide you with a model options in next updates)

Rerank model - **BAAI/bge-reranker-base** (used for both configurations: fully local and custom GPT)

To use a chat ui, please navigate to **http://localhost:3000**

Example of .env file for ChatGPT custom GPT usage:
```
LOCAL_FILES_PATH=/Users/davidmayboroda/Downloads/PDFs/
EMBEDDING_MODEL_ID=sentence-transformers/all-mpnet-base-v2
EMBEDDING_SIZE=768
START_INDEXING=false
USER_ID=user@gmail.com # your real email
PASSWORD=password # you can create here password that you want
```
Minima (https://github.com/dmayboroda/minima) is licensed under the Mozilla Public License v2.0 (MPLv2).
