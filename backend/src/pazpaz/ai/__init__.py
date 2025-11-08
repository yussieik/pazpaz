"""
PazPaz AI Assistant Package

This package provides AI-powered capabilities for therapists to interact with patient data:
- Session history summarization
- Natural language search across SOAP notes
- Session preparation insights

Architecture:
- embeddings.py: Vector generation via Cohere API
- vector_store.py: pgvector CRUD operations with workspace scoping
- retrieval.py: RAG pipeline (query → retrieve → rank)
- agent.py: LangGraph-based conversational agent
- tasks.py: Background jobs for async embedding generation
- prompts.py: System prompts (Hebrew/English bilingual)

Security:
- All queries filtered by workspace_id (multi-tenant isolation)
- PHI automatically decrypted via EncryptedString type
- Audit logging for all AI interactions
- PII redaction in LLM outputs
"""

__version__ = "0.1.0"
