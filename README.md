**Minima** is an open source solution to search documents (and photos, calendar etc. in future) with a simple query in chat GPT.
It's a fully local RAG, enbedding models and simple setup via docker.

1.	Create a .env file in the project’s root directory (where you’ll find env.sample). Place .env in the same folder and copy all environment variables from env.sample to .env.
2.	Ensure your .env file includes the following variables:
<ol>
   <li> LOCAL_FILES_PATH </li>
   <li> EMBEDDING_MODEL_ID </li>
   <li> EMBEDDING_SIZE</li>
   <li> QDRANT_BOOTSTRAP </li>
   <li> QDRANT_COLLECTION </li>
   <li> START_INDEXING </li>
   <li> FIRESTORE_COLLECTION_NAME </li>
   <li> FIREBASE_KEY_FILE </li>
   <li> USER_ID </li>
</ol>

Explanation of Variables

LOCAL_FILES_PATH: Specify the root folder for indexing. Indexing is a recursive process, meaning all documents within subfolders of this root folder will also be indexed. Supported file types: .pdf, .xls, .docx, .txt, .md, .csv.

EMBEDDING_MODEL_ID: Specify the embedding model to use. Currently, only Sentence Transformer models are supported. Testing has been done with sentence-transformers/all-mpnet-base-v2, but other Sentence Transformer models can be used.

EMBEDDING_SIZE: Define the embedding dimension provided by the model, which is needed to configure Qdrant vector storage. Ensure this value matches the actual embedding size of the specified EMBEDDING_MODEL_ID.

QDRANT_BOOTSTRAP: Name of the Qdrant container used by LangChain to connect to Qdrant. Default is ‘qdrant’. This may be removed in a future release.

QDRANT_COLLECTION: Name of the collection for storing vectors locally. Do not change this name after indexing, as it may disrupt access to your embeddings.

START_INDEXING: Set this to ‘true’ on initial startup to begin indexing. Data can be queried while it indexes. Note that reindexing is not yet supported. To reindex, remove the qdrant_data folder (created automatically), set this flag to ‘true,’ and restart the containers. After indexing completes, you can keep the container running or restart without reindexing by setting this flag to ‘false’.

FIRESTORE_COLLECTION_NAME and FIREBASE_KEY_FILE: Set these to userTasks and tasks, respectively, to connect to the Firebase backend for ChatGPT actions. Files are not sent to ChatGPT; they’re indexed locally, and when you make a query in ChatGPT, the local container processes it, embeds it, and retrieves relevant information. This data is then sent to ChatGPT via a secure proxy.

USER_ID: Create a unique user ID, which will link your ChatGPT connection to your local machine. Choose any name, but remember it, as you’ll need it within ChatGPT.

WE DO NOT STORE ANY PRIVATE DATA.

Minima (https://github.com/dmayboroda/minima) is licensed under the Mozilla Public License v2.0 (MPLv2).
