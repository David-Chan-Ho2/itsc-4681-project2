# LangChain Vector Stores

Vector stores persist document embeddings so semantic retrieval can be reused across sessions.

The general workflow is:

1. load documentation files
2. split them into chunks
3. embed each chunk
4. store the vectors and metadata in a persistent database
5. query the store with an embedded question

Persistent vector stores are important for local RAG systems because the expensive indexing step only needs to happen once.
