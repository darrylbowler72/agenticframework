"""
RAG System for DevOps Agentic Framework

Implements semantic retrieval, reranking, and intelligent stitching
for templates, documentation, and code examples.
"""

import asyncio
import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from pathlib import Path

# Vector database options: pgvector, Pinecone, Weaviate, ChromaDB
# For this example, using in-memory with numpy (production: use pgvector)


@dataclass
class Chunk:
    """Represents a document chunk with metadata."""
    id: str
    content: str
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    chunk_index: int = 0
    total_chunks: int = 1
    parent_doc_id: str = ""

    def to_dict(self) -> Dict:
        """Serialize for storage."""
        return {
            'id': self.id,
            'content': self.content,
            'embedding': self.embedding.tolist() if self.embedding is not None else None,
            'metadata': self.metadata,
            'source': self.source,
            'chunk_index': self.chunk_index,
            'total_chunks': self.total_chunks,
            'parent_doc_id': self.parent_doc_id
        }


@dataclass
class RetrievalResult:
    """Result from retrieval with scoring."""
    chunk: Chunk
    similarity_score: float
    rerank_score: Optional[float] = None
    final_score: float = 0.0
    rank: int = 0


class ChunkingStrategy:
    """Implements various chunking strategies for different document types."""

    @staticmethod
    def chunk_by_tokens(
        text: str,
        max_tokens: int = 512,
        overlap_tokens: int = 50
    ) -> List[str]:
        """
        Fixed-size chunking with overlap.

        Best for: Dense documentation, general text
        Trade-off: May split semantic units
        """
        # Rough tokenization (4 chars ≈ 1 token)
        words = text.split()
        chunks = []

        current_chunk = []
        current_length = 0

        for word in words:
            word_tokens = len(word) // 4 + 1

            if current_length + word_tokens > max_tokens and current_chunk:
                chunks.append(' '.join(current_chunk))
                # Overlap: keep last N words
                overlap_words = int(overlap_tokens * 4)
                current_chunk = current_chunk[-overlap_words:] if overlap_words > 0 else []
                current_length = sum(len(w) // 4 + 1 for w in current_chunk)

            current_chunk.append(word)
            current_length += word_tokens

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    @staticmethod
    def chunk_by_structure(text: str, doc_type: str = 'code') -> List[Dict[str, Any]]:
        """
        Structure-aware chunking.

        Best for: Code files, structured documents
        Trade-off: Variable chunk sizes
        """
        chunks = []

        if doc_type == 'code':
            # Split by functions/classes
            lines = text.split('\n')
            current_block = []
            current_metadata = {}

            for i, line in enumerate(lines):
                # Detect function definitions
                if 'def ' in line or 'class ' in line or 'async def ' in line:
                    if current_block:
                        chunks.append({
                            'content': '\n'.join(current_block),
                            'metadata': current_metadata.copy(),
                            'type': 'code_block'
                        })
                    current_block = [line]

                    # Extract function/class name
                    if 'def ' in line:
                        func_name = line.split('def ')[1].split('(')[0].strip()
                        current_metadata = {'function': func_name, 'line': i}
                    elif 'class ' in line:
                        class_name = line.split('class ')[1].split(':')[0].strip()
                        current_metadata = {'class': class_name, 'line': i}
                else:
                    current_block.append(line)

                    # Split large blocks
                    if len(current_block) > 50:
                        chunks.append({
                            'content': '\n'.join(current_block),
                            'metadata': current_metadata.copy(),
                            'type': 'code_block'
                        })
                        current_block = []

            if current_block:
                chunks.append({
                    'content': '\n'.join(current_block),
                    'metadata': current_metadata,
                    'type': 'code_block'
                })

        elif doc_type == 'markdown':
            # Split by headers
            lines = text.split('\n')
            current_section = []
            current_header = ""

            for line in lines:
                if line.startswith('#'):
                    if current_section:
                        chunks.append({
                            'content': '\n'.join(current_section),
                            'metadata': {'header': current_header},
                            'type': 'markdown_section'
                        })
                    current_header = line.strip('#').strip()
                    current_section = [line]
                else:
                    current_section.append(line)

            if current_section:
                chunks.append({
                    'content': '\n'.join(current_section),
                    'metadata': {'header': current_header},
                    'type': 'markdown_section'
                })

        return chunks

    @staticmethod
    def chunk_by_semantic(text: str, model=None) -> List[str]:
        """
        Semantic chunking using sentence embeddings.

        Best for: Long documents requiring coherent sections
        Trade-off: Computationally expensive

        Algorithm:
        1. Split into sentences
        2. Compute embeddings for each sentence
        3. Find similarity boundaries
        4. Group sentences with high similarity
        """
        sentences = text.split('. ')

        if model is None:
            # Fallback: simple sentence grouping
            chunk_size = 5
            chunks = []
            for i in range(0, len(sentences), chunk_size):
                chunk = '. '.join(sentences[i:i+chunk_size])
                chunks.append(chunk)
            return chunks

        # With model: compute embeddings and cluster
        # (Implementation would use sentence-transformers)
        return [text]  # Placeholder


class EmbeddingGenerator:
    """Generates embeddings for text chunks."""

    def __init__(self, provider: str = 'anthropic'):
        """
        Initialize embedding generator.

        Options:
        - 'anthropic': Use Claude for embeddings (not available yet)
        - 'openai': Use OpenAI text-embedding-3-small
        - 'sentence-transformers': Local model
        - 'mock': Random embeddings for testing
        """
        self.provider = provider
        self.dimension = 1536  # Standard embedding dimension

    async def generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        if self.provider == 'mock':
            # For testing: generate consistent embeddings based on text hash
            hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
            np.random.seed(hash_val % (2**32))
            embedding = np.random.randn(self.dimension)
            # Normalize
            return embedding / np.linalg.norm(embedding)

        elif self.provider == 'openai':
            # import openai
            # response = await openai.Embedding.acreate(
            #     model="text-embedding-3-small",
            #     input=text
            # )
            # return np.array(response['data'][0]['embedding'])
            pass

        # Fallback
        return np.random.randn(self.dimension)

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[np.ndarray]:
        """Generate embeddings for multiple texts efficiently."""
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            batch_embeddings = await asyncio.gather(*[
                self.generate_embedding(text) for text in batch
            ])
            embeddings.extend(batch_embeddings)

        return embeddings


class Reranker:
    """Reranks retrieved results using multiple signals."""

    def __init__(self):
        self.weights = {
            'semantic_similarity': 0.4,
            'keyword_match': 0.2,
            'recency': 0.1,
            'popularity': 0.1,
            'source_quality': 0.2
        }

    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """
        Rerank results using multiple signals.

        Signals:
        1. Semantic similarity (from vector search)
        2. Keyword match (BM25-style)
        3. Recency (newer is better)
        4. Popularity (usage frequency)
        5. Source quality (curated > user-generated)
        """
        for result in results:
            scores = {
                'semantic_similarity': result.similarity_score,
                'keyword_match': self._compute_keyword_score(query, result.chunk.content),
                'recency': self._compute_recency_score(result.chunk.metadata),
                'popularity': self._compute_popularity_score(result.chunk.metadata),
                'source_quality': self._compute_source_quality(result.chunk.source)
            }

            # Weighted combination
            result.rerank_score = sum(
                scores[signal] * self.weights[signal]
                for signal in scores
            )
            result.final_score = result.rerank_score

        # Sort by final score
        results.sort(key=lambda x: x.final_score, reverse=True)

        # Assign ranks
        for rank, result in enumerate(results[:top_k], start=1):
            result.rank = rank

        return results[:top_k]

    def _compute_keyword_score(self, query: str, content: str) -> float:
        """BM25-style keyword matching."""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        overlap = query_words & content_words
        if not query_words:
            return 0.0

        return len(overlap) / len(query_words)

    def _compute_recency_score(self, metadata: Dict) -> float:
        """Score based on document recency."""
        if 'created_at' in metadata:
            # Newer documents get higher scores
            # (Simplified: would use actual date math)
            return 0.8
        return 0.5

    def _compute_popularity_score(self, metadata: Dict) -> float:
        """Score based on usage frequency."""
        if 'access_count' in metadata:
            # Log scale to prevent dominance
            return min(np.log1p(metadata['access_count']) / 10, 1.0)
        return 0.5

    def _compute_source_quality(self, source: str) -> float:
        """Score based on source quality."""
        quality_map = {
            'official_docs': 1.0,
            'curated_templates': 0.9,
            'community_examples': 0.7,
            'user_generated': 0.5
        }

        for key, score in quality_map.items():
            if key in source:
                return score

        return 0.5


class ResponseStitcher:
    """Stitches retrieved chunks into coherent responses."""

    def __init__(self, max_context_tokens: int = 4000):
        self.max_context_tokens = max_context_tokens

    async def stitch(
        self,
        query: str,
        results: List[RetrievalResult],
        strategy: str = 'smart'
    ) -> Dict[str, Any]:
        """
        Stitch chunks into coherent context.

        Strategies:
        - 'concatenate': Simple concatenation (fastest)
        - 'smart': Remove duplicates, order logically
        - 'synthesize': Use LLM to create coherent summary
        """
        if strategy == 'concatenate':
            return self._concatenate_simple(results)

        elif strategy == 'smart':
            return self._stitch_smart(query, results)

        elif strategy == 'synthesize':
            return await self._synthesize_with_llm(query, results)

        return {'context': '', 'chunks': []}

    def _concatenate_simple(self, results: List[RetrievalResult]) -> Dict:
        """Simple concatenation with source attribution."""
        context_parts = []
        chunks_used = []
        total_tokens = 0

        for result in results:
            chunk_tokens = len(result.chunk.content) // 4

            if total_tokens + chunk_tokens > self.max_context_tokens:
                break

            context_parts.append(
                f"[Source: {result.chunk.source}]\n{result.chunk.content}\n"
            )
            chunks_used.append(result.chunk.to_dict())
            total_tokens += chunk_tokens

        return {
            'context': '\n---\n'.join(context_parts),
            'chunks_used': chunks_used,
            'total_tokens': total_tokens,
            'strategy': 'concatenate'
        }

    def _stitch_smart(
        self,
        query: str,
        results: List[RetrievalResult]
    ) -> Dict:
        """
        Smart stitching with:
        - Deduplication
        - Logical ordering
        - Context preservation
        """
        # Group by source document
        by_source = {}
        for result in results:
            source = result.chunk.parent_doc_id or result.chunk.source
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(result)

        # Sort chunks within each source by index
        for source in by_source:
            by_source[source].sort(key=lambda x: x.chunk.chunk_index)

        # Build context
        context_parts = []
        chunks_used = []
        total_tokens = 0

        for source, source_results in by_source.items():
            # Check if we have consecutive chunks - merge them
            merged_content = self._merge_consecutive_chunks(source_results)

            chunk_tokens = len(merged_content) // 4
            if total_tokens + chunk_tokens > self.max_context_tokens:
                break

            context_parts.append(
                f"### From {source}\n\n{merged_content}\n"
            )

            chunks_used.extend([r.chunk.to_dict() for r in source_results])
            total_tokens += chunk_tokens

        return {
            'context': '\n\n'.join(context_parts),
            'chunks_used': chunks_used,
            'total_tokens': total_tokens,
            'strategy': 'smart',
            'sources': list(by_source.keys())
        }

    def _merge_consecutive_chunks(
        self,
        results: List[RetrievalResult]
    ) -> str:
        """Merge consecutive chunks from same document."""
        if not results:
            return ""

        # Sort by chunk index
        sorted_results = sorted(results, key=lambda x: x.chunk.chunk_index)

        merged = []
        current_group = [sorted_results[0].chunk.content]
        last_index = sorted_results[0].chunk.chunk_index

        for result in sorted_results[1:]:
            if result.chunk.chunk_index == last_index + 1:
                # Consecutive - merge
                current_group.append(result.chunk.content)
            else:
                # Gap - start new group
                merged.append(' '.join(current_group))
                current_group = [result.chunk.content]

            last_index = result.chunk.chunk_index

        if current_group:
            merged.append(' '.join(current_group))

        return '\n\n[...]\n\n'.join(merged)

    async def _synthesize_with_llm(
        self,
        query: str,
        results: List[RetrievalResult]
    ) -> Dict:
        """Use LLM to synthesize coherent response from chunks."""
        # Gather all relevant content
        all_content = '\n\n---\n\n'.join([
            f"Chunk {i+1} (score: {r.final_score:.3f}):\n{r.chunk.content}"
            for i, r in enumerate(results[:5])
        ])

        # This would call Claude to synthesize
        # For now, return smart stitching
        return self._stitch_smart(query, results)


class RAGSystem:
    """Complete RAG system integrating all components."""

    def __init__(
        self,
        chunking_strategy: str = 'structure',
        embedding_provider: str = 'mock',
        rerank: bool = True
    ):
        self.chunker = ChunkingStrategy()
        self.embedder = EmbeddingGenerator(provider=embedding_provider)
        self.reranker = Reranker() if rerank else None
        self.stitcher = ResponseStitcher()

        # In-memory vector store (production: use pgvector/Pinecone)
        self.chunks: List[Chunk] = []
        self.embeddings: List[np.ndarray] = []

    async def index_document(
        self,
        content: str,
        source: str,
        doc_type: str = 'code',
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Index a document for retrieval.

        Returns: Number of chunks created
        """
        metadata = metadata or {}

        # Step 1: Chunk
        if doc_type in ['code', 'markdown']:
            chunk_dicts = self.chunker.chunk_by_structure(content, doc_type)
            chunk_texts = [c['content'] for c in chunk_dicts]
        else:
            chunk_texts = self.chunker.chunk_by_tokens(content)
            chunk_dicts = [{'content': c, 'metadata': {}} for c in chunk_texts]

        # Step 2: Generate embeddings
        embeddings = await self.embedder.generate_embeddings_batch(chunk_texts)

        # Step 3: Store chunks
        parent_doc_id = hashlib.md5(source.encode()).hexdigest()

        for i, (chunk_dict, embedding) in enumerate(zip(chunk_dicts, embeddings)):
            chunk_id = f"{parent_doc_id}_{i}"

            chunk = Chunk(
                id=chunk_id,
                content=chunk_dict['content'],
                embedding=embedding,
                metadata={**metadata, **chunk_dict.get('metadata', {})},
                source=source,
                chunk_index=i,
                total_chunks=len(chunk_texts),
                parent_doc_id=parent_doc_id
            )

            self.chunks.append(chunk)
            self.embeddings.append(embedding)

        return len(chunk_texts)

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        rerank: bool = True,
        stitch_strategy: str = 'smart'
    ) -> Dict[str, Any]:
        """
        Retrieve and process relevant chunks for a query.

        Returns:
            {
                'context': str,          # Stitched context for LLM
                'chunks': List[Dict],    # Raw chunks used
                'sources': List[str],    # Source documents
                'stats': Dict           # Retrieval statistics
            }
        """
        start_time = datetime.utcnow()

        # Step 1: Generate query embedding
        query_embedding = await self.embedder.generate_embedding(query)

        # Step 2: Vector similarity search
        results = await self._vector_search(query_embedding, top_k=top_k*2)

        # Step 3: Rerank (optional)
        if rerank and self.reranker:
            results = self.reranker.rerank(query, results, top_k=top_k)
        else:
            results = results[:top_k]

        # Step 4: Stitch into coherent context
        stitched = await self.stitcher.stitch(query, results, strategy=stitch_strategy)

        # Step 5: Add statistics
        end_time = datetime.utcnow()
        stitched['stats'] = {
            'retrieval_time_ms': (end_time - start_time).total_seconds() * 1000,
            'chunks_retrieved': len(results),
            'chunks_used': len(stitched.get('chunks_used', [])),
            'total_tokens': stitched.get('total_tokens', 0),
            'reranked': rerank
        }

        return stitched

    async def _vector_search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 20
    ) -> List[RetrievalResult]:
        """Perform vector similarity search."""
        if not self.embeddings:
            return []

        # Compute cosine similarities
        embeddings_matrix = np.vstack(self.embeddings)
        similarities = np.dot(embeddings_matrix, query_embedding)

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        # Create results
        results = []
        for idx in top_indices:
            results.append(RetrievalResult(
                chunk=self.chunks[idx],
                similarity_score=float(similarities[idx]),
                final_score=float(similarities[idx])
            ))

        return results
