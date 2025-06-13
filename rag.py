# rag.py

from openai import OpenAI
from config import Config
from typing import List, Dict, Any
import time

class RAGSystem:
    def __init__(self, embeddings):
        self.embeddings = embeddings
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.llm_model = "gpt-3.5-turbo"
        self.max_retries = 3

    def ingest_document(self, text: str, metadata: Dict[str, Any]) -> str:
        return self.embeddings.add_document(text, metadata)

    # def search_documents(self, query: str, k: int = 5, document_ids: List[str] = None) -> List[Dict[str, Any]]:
    #     return self.embeddings.search(query, k, document_ids=document_ids)
    def search_documents(self, query: str, k: int = 5, document_ids: List[str] = None) -> List[Dict[str, Any]]:
        """Search documents and return in the expected format"""
        results = self.embeddings.search(query, k, document_ids=document_ids)
        
        # Convert to the format expected by generate_response
        formatted_results = []
        for result in results:
            formatted_results.append({
                'text': result['text'],
                'score': result['score'],
                'metadata': result.get('metadata', {}),
                'page_content': result['text']  # Add this for compatibility
            })
        
        return formatted_results
    def generate_response(self, query: str, context: List[Dict[str, Any]]) -> str:
        context_str = "\n\n".join([
            f"Document {i+1} (relevance: {doc['score']:.2f}):\n{doc['text']}"
            for i, doc in enumerate(context)
        ])

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {"role": "system", "content": "Answer using the provided context."},
                        {"role": "user", "content": f"Question: {query}\nContext:\n{context_str}"}
                    ],
                    temperature=0.7
                )
                return response.choices[0].message.content
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return f"Error generating response: {str(e)}"
                time.sleep(1)
        return "Could not generate response"
