**Minima** is an open source fully local RAG.

1.	Create a .env file in the project’s root directory (where you’ll find env.sample). Place .env in the same folder and copy all environment variables from env.sample to .env.
2.	Ensure your .env file includes the following variables:
<ul>
   <li> LOCAL_FILES_PATH </li>
   <li> EMBEDDING_MODEL_ID </li>
   <li> EMBEDDING_SIZE</li>
   <li> START_INDEXING </li>
</ul>

3. docker compose --env-file .env up --build.

4. Connect to **ws://localhost:8003/llm/** to start a conversation with LLM.
   
6. Ask anything, and you'll get answers based on local files in {LOCAL_FILES_PATH} folder.

Explanation of Variables:

**LOCAL_FILES_PATH**: Specify the root folder for indexing. Indexing is a recursive process, meaning all documents within subfolders of this root folder will also be indexed. Supported file types: .pdf, .xls, .docx, .txt, .md, .csv.

**EMBEDDING_MODEL_ID**: Specify the embedding model to use. Currently, only Sentence Transformer models are supported. Testing has been done with sentence-transformers/all-mpnet-base-v2, but other Sentence Transformer models can be used.

**EMBEDDING_SIZE**: Define the embedding dimension provided by the model, which is needed to configure Qdrant vector storage. Ensure this value matches the actual embedding size of the specified EMBEDDING_MODEL_ID.

**START_INDEXING**: Set this to ‘true’ on initial startup to begin indexing. Data can be queried while it indexes. Note that reindexing is not yet supported. To reindex, remove the qdrant_data folder (created automatically), set this flag to ‘true,’ and restart the containers. After indexing completes, you can keep the container running or restart without reindexing by setting this flag to ‘false’.

Example of .env file:
```
LOCAL_FILES_PATH=/Users/davidmayboroda/Downloads/PDFs/
EMBEDDING_MODEL_ID=sentence-transformers/all-mpnet-base-v2
EMBEDDING_SIZE=768
START_INDEXING=false
```

Ollama chatting model - qwen2:0.5b (hard coded, but we will provide you with a model options in next updates)

WE ARE PREPARING A CONTAINER FOR CHATGPT ACTIONS USAGE! FOR NOW IGNORE 'linker' CONTAINER AND 'firebase' FOLDER!

Minima (https://github.com/dmayboroda/minima) is licensed under the Mozilla Public License v2.0 (MPLv2).
