**Minima** is an open source RAG on-premises containers, with ability to integrate with ChatGPT and MCP. 
Minima can also be used as a fully local RAG.

[![smithery badge](https://smithery.ai/badge/minima)](https://smithery.ai/protocol/minima)

Minima currently supports three modes:
1. Isolated installation – Operate fully on-premises with containers, free from external dependencies such as ChatGPT or Claude. All neural networks (LLM, reranker, embedding) run on your cloud or PC, ensuring your data remains secure.

2. Custom GPT – Query your local documents using ChatGPT app or web with custom GPTs. The indexer running on your cloud or local PC, while the primary LLM remains ChatGPT.

3. Anthropic Claude – Use Anthropic Claude app to query your local documents. The indexer operates on your local PC, while Anthropic Claude serves as the primary LLM.

### Running as containers

1. Create a .env file in the project’s root directory (where you’ll find env.sample). Place .env in the same folder and copy all environment variables from env.sample to .env.

2. Ensure your .env file includes the following variables:
<ul>
   <li> LOCAL_FILES_PATH </li>
   <li> EMBEDDING_MODEL_ID </li>
   <li> EMBEDDING_SIZE </li>
   <li> OLLAMA_MODEL </li>
   <li> RERANKER_MODEL </li>
   <li> USER_ID </li> - required for ChatGPT integration, just use your email
   <li> PASSWORD </li> - required for ChatGPT integration, just use any password
</ul>

3. For fully local installation use: **docker compose -f docker-compose-ollama.yml --env-file .env up --build**.

4. For ChatGPT enabled installation use: **docker compose -f docker-compose-chatgpt.yml --env-file .env up --build**.

5. For MCP integration (Anthropic Desktop app usage): **docker compose -f docker-compose-mcp.yml --env-file .env up --build**.

6. In case of ChatGPT enabled installation copy OTP from terminal where you launched docker and use [Minima GPT](https://chatgpt.com/g/g-r1MNTSb0Q-minima-local-computer-search)  

7. If you use Anthropic Claude, just add folliwing to **/Library/Application\ Support/Claude/claude_desktop_config.json**

```
{
    "mcpServers": {
      "minima": {
        "command": "uv",
        "args": [
          "--directory",
          "/path_to_cloned_minima_project/mcp-server",
          "run",
          "minima"
        ]
      }
    }
  }
```
   
8. To use fully local installation go to `cd electron`, then run `npm install` and `npm start` which will launch Minima electron app.

9. Ask anything, and you'll get answers based on local files in {LOCAL_FILES_PATH} folder.

Explanation of Variables:

**LOCAL_FILES_PATH**: Specify the root folder for indexing (on your cloud or local pc). Indexing is a recursive process, meaning all documents within subfolders of this root folder will also be indexed. Supported file types: .pdf, .xls, .docx, .txt, .md, .csv.

**EMBEDDING_MODEL_ID**: Specify the embedding model to use. Currently, only Sentence Transformer models are supported. Testing has been done with sentence-transformers/all-mpnet-base-v2, but other Sentence Transformer models can be used.

**EMBEDDING_SIZE**: Define the embedding dimension provided by the model, which is needed to configure Qdrant vector storage. Ensure this value matches the actual embedding size of the specified EMBEDDING_MODEL_ID.

**OLLAMA_MODEL**: Set up the Ollama model, use an ID available on the Ollama [site](https://ollama.com/search). Please, use LLM model here, not an embedding.

**RERANKER_MODEL**: Specify the reranker model. Currently, we have tested with BAAI rerankers. You can explore all available rerankers using this [link](https://huggingface.co/collections/BAAI/).

**USER_ID**: Just use your email here, this is needed to authenticate custom GPT to search in your data.

**PASSWORD**: Put any password here, this is used to create a firebase account for the email specified above.


Example of .env file for on-premises/local usage:
```
LOCAL_FILES_PATH=/Users/davidmayboroda/Downloads/PDFs/
EMBEDDING_MODEL_ID=sentence-transformers/all-mpnet-base-v2
EMBEDDING_SIZE=768
OLLAMA_MODEL=qwen2:0.5b # must be LLM model id from Ollama models page
RERANKER_MODEL=BAAI/bge-reranker-base # please, choose any BAAI reranker model
```

To use a chat ui, please navigate to **http://localhost:3000**

Example of .env file for Claude app:
```
LOCAL_FILES_PATH=/Users/davidmayboroda/Downloads/PDFs/
EMBEDDING_MODEL_ID=sentence-transformers/all-mpnet-base-v2
RERANKER_MODEL=BAAI/bge-reranker-base
EMBEDDING_SIZE=768
```
For the Claude app, please apply the changes to the claude_desktop_config.json file as outlined above.

Example of .env file for ChatGPT custom GPT usage:
```
LOCAL_FILES_PATH=/Users/davidmayboroda/Downloads/PDFs/
EMBEDDING_MODEL_ID=sentence-transformers/all-mpnet-base-v2
EMBEDDING_SIZE=768
USER_ID=user@gmail.com # your real email
PASSWORD=password # you can create here password that you want
```

Also, you can run minima using **run.sh**.

### Installing via Smithery (MCP usage)

To install Minima for Claude Desktop automatically via [Smithery](https://smithery.ai/protocol/minima):

```bash
npx -y @smithery/cli install minima --client claude
```

**For MCP usage, please be sure that your local machines python is >=3.10 and 'uv' installed.**

Minima (https://github.com/dmayboroda/minima) is licensed under the Mozilla Public License v2.0 (MPLv2).
