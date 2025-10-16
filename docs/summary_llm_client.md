# Algorithm Summary: `llm_client.py`

## 1. Role in the Pipeline

This script is a crucial library module that acts as an abstraction layer for interacting with various Large Language Model (LLM) and embedding model APIs. It provides a consistent, unified interface that the `code_graph_rag_generator.py` can use without needing to know the specific details of the underlying API being called.

This allows the project to easily switch between different model providers (like OpenAI, DeepSeek, or a local Ollama instance) by simply changing a command-line argument.

## 2. Design and Architecture

The script uses a classic **Factory and Strategy** design pattern.

### Strategy Pattern

*   **`LlmClient` / `EmbeddingClient`**: These are abstract base classes that define a common interface. For example, any LLM client must have a `generate_summary(prompt)` method, and any embedding client must have a `generate_embedding(text)` method.
*   **Concrete Implementations**: For each supported service, a concrete class is created that inherits from the base class and implements the required methods. Examples include:
    *   `OpenAiClient(LlmClient)`
    *   `DeepSeekClient(LlmClient)`
    *   `OllamaClient(LlmClient)`
    *   `SentenceTransformerClient(EmbeddingClient)`
*   **Subtlety (`is_local` flag)**: Each client class has a boolean flag, `is_local`. This allows the `RagGenerator` to intelligently choose the number of parallel workers to use. For a remote, network-bound API like `OpenAIClient`, it can use a high number of workers (`--num-remote-workers`). For a local, CPU-bound model like `OllamaClient` or `SentenceTransformerClient`, it will use a smaller number of workers (`--num-local-workers`) to avoid overloading the host machine.

### Factory Pattern

*   **`get_llm_client(api_name)` / `get_embedding_client(api_name)`**: These functions act as factories. They take a simple string (e.g., `'openai'`) and return an initialized instance of the corresponding client class.
*   **Benefit**: This decouples the main application logic from the client creation process. The main script doesn't need a complex `if/elif/else` block to create a client; it simply calls the factory, making the code cleaner and easier to extend with new clients in the future.

## 3. Supported Models

### LLM Clients

*   **`OpenAiClient`**: Interacts with the OpenAI API. Requires the `OPENAI_API_KEY` environment variable.
*   **`DeepSeekClient`**: Interacts with the DeepSeek API. Requires the `DEEPSEEK_API_KEY` environment variable.
*   **`OllamaClient`**: Interacts with a local Ollama instance. The URL and model name can be configured via `OLLAMA_BASE_URL` and `OLLAMA_MODEL` environment variables.

### Embedding Clients

*   **`SentenceTransformerClient`**: Uses the popular `sentence-transformers` library to run embedding models locally. 
*   **Subtlety**: This client will automatically download the specified model (e.g., `all-MiniLM-L6-v2`) on its first use and cache it for future runs. It requires `sentence-transformers` and a compatible version of `torch` to be installed.
