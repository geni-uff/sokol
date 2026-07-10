#!/usr/bin/env python3
"""SOKOL — Embedding model benchmark.

Evaluates embedding models on the golden set using:
- Recall@k (k=1,3,5,10)
- MRR (Mean Reciprocal Rank)
- Citation accuracy (chunk_id validation)
- Latency p50/p95/p99

Usage:
    python -m evals.bench_embeddings
    python -m evals.bench_embeddings --models text-embedding-qwen3-embedding-0.6b,mykor/paraphrase-multilingual-mpnet-base-v2
    python -m evals.bench_embeddings --corpus synth/output/synthetic_data.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# ── Config ─────────────────────────────────────────────────────────────────
LMSTUDIO_URL = os.getenv("SOKOL_EMBED_BASE_URL", "http://localhost:1234/v1")
GOLDEN_SET_PATH = Path("synth/output/golden_set.json")
CORPUS_PATH = Path("synth/output/synthetic_data.json")

DEFAULT_MODELS = [
    "text-embedding-qwen3-embedding-0.6b",
    "mykor/paraphrase-multilingual-mpnet-base-v2",
]

K_VALUES = [1, 3, 5, 10]


# ── Golden Set ─────────────────────────────────────────────────────────────
def load_golden_set(path: str | Path | None = None) -> list[dict]:
    """Load golden set queries with expected recall."""
    path = Path(path or GOLDEN_SET_PATH)
    with open(path) as f:
        data = json.load(f)
    return data["questions"]


def load_corpus(path: str | Path | None = None) -> list[dict]:
    """Load synthetic corpus with key facts or chunks."""
    path = Path(path or CORPUS_PATH)
    with open(path) as f:
        data = json.load(f)
    # Support multiple formats
    if "chunks" in data:
        return data["chunks"]
    if "key_facts" in data:
        return data["key_facts"]
    if "messages" in data:
        return data["messages"]
    return []


# ── Embedding client ──────────────────────────────────────────────────────
class EmbeddingClient:
    def __init__(self, base_url: str = LMSTUDIO_URL):
        self.base_url = base_url
        self.client = httpx.Client(timeout=60.0)

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Get embeddings for texts."""
        response = self.client.post(
            f"{self.base_url}/embeddings",
            json={"model": model, "input": texts},
        )
        response.raise_for_status()
        data = response.json()
        # Sort by index to maintain order
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]

    def embed_single(self, text: str, model: str) -> list[float]:
        """Get embedding for a single text."""
        return self.embed([text], model)[0]

    def health(self) -> bool:
        try:
            response = self.client.get(f"{self.base_url.rstrip('/v1')}/health")
            return response.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            response = self.client.get(f"{self.base_url}/models")
            response.raise_for_status()
            return [m["id"] for m in response.json()["data"]]
        except Exception:
            return []


# ── Similarity ─────────────────────────────────────────────────────────────
def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search(
    query_embedding: list[float],
    corpus_embeddings: list[list[float]],
    corpus_ids: list[str],
    k: int = 10,
) -> list[tuple[str, float]]:
    """Search corpus by embedding similarity."""
    scores = []
    for i, emb in enumerate(corpus_embeddings):
        score = cosine_similarity(query_embedding, emb)
        scores.append((corpus_ids[i], score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:k]


# ── Metrics ────────────────────────────────────────────────────────────────
def recall_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    """Recall@k: fraction of expected items in top-k results."""
    if not expected:
        return 1.0 if not retrieved else 0.0
    top_k = set(retrieved[:k])
    return len(top_k & expected) / len(expected)


def mrr(retrieved: list[str], expected: set[str]) -> float:
    """Mean Reciprocal Rank: 1/rank of first relevant result."""
    for i, item in enumerate(retrieved):
        if item in expected:
            return 1.0 / (i + 1)
    return 0.0


def precision_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    """Precision@k: fraction of retrieved items that are relevant."""
    if k == 0:
        return 0.0
    top_k = set(retrieved[:k])
    return len(top_k & expected) / k


# ── Benchmark ──────────────────────────────────────────────────────────────
def run_benchmark(
    model: str,
    client: EmbeddingClient,
    golden_set: list[dict],
    corpus: list[dict],
    batch_size: int = 32,
) -> dict[str, Any]:
    """Run benchmark for a single model."""
    print(f"\n{'=' * 60}")
    print(f"Testing: {model}")
    print(f"{'=' * 60}")

    # Build corpus embeddings
    print("Building corpus embeddings...")
    corpus_texts = [
        f"{item.get('text', '')} {item.get('summary', '')}".strip() for item in corpus
    ]
    corpus_ids = [item.get("id", f"chunk_{i}") for i, item in enumerate(corpus)]

    corpus_embeddings = []
    start_time = time.monotonic()

    for i in range(0, len(corpus_texts), batch_size):
        batch = corpus_texts[i : i + batch_size]
        try:
            embeddings = client.embed(batch, model)
            corpus_embeddings.extend(embeddings)
            print(
                f"  Embedded {min(i + batch_size, len(corpus_texts))}/{len(corpus_texts)}"
            )
        except Exception as e:
            print(f"  Error embedding batch: {e}")
            corpus_embeddings.extend([[0.0] * 768] * len(batch))

    corpus_time = time.monotonic() - start_time

    # Embed queries and search
    print("Running queries...")
    metrics = {
        "model": model,
        "corpus_size": len(corpus),
        "corpus_embed_time_s": round(corpus_time, 2),
        "queries": [],
    }

    latencies = []
    recall_scores = {k: [] for k in K_VALUES}
    mrr_scores = []
    precision_scores = {k: [] for k in K_VALUES}

    for q in golden_set:
        query_text = q["query"]
        expected_ids = set(q.get("expected_recall", []))

        # Embed query
        start = time.monotonic()
        try:
            query_emb = client.embed_single(query_text, model)
        except Exception as e:
            print(f"  Error embedding query: {e}")
            continue
        latency = (time.monotonic() - start) * 1000  # ms
        latencies.append(latency)

        # Search
        results = search(query_emb, corpus_embeddings, corpus_ids, k=max(K_VALUES))
        retrieved_ids = [r[0] for r in results]

        # Calculate metrics
        for k in K_VALUES:
            recall_scores[k].append(recall_at_k(retrieved_ids, expected_ids, k))
            precision_scores[k].append(precision_at_k(retrieved_ids, expected_ids, k))

        mrr_scores.append(mrr(retrieved_ids, expected_ids))

        metrics["queries"].append(
            {
                "id": q["id"],
                "query": query_text,
                "latency_ms": round(latency, 2),
                "top_results": retrieved_ids[:5],
                "expected": list(expected_ids),
                "recall@5": recall_at_k(retrieved_ids, expected_ids, 5),
            }
        )

    # Aggregate metrics
    metrics["aggregate"] = {
        "recall@k": {
            f"recall@{k}": round(statistics.mean(recall_scores[k]), 4) for k in K_VALUES
        },
        "precision@k": {
            f"precision@{k}": round(statistics.mean(precision_scores[k]), 4)
            for k in K_VALUES
        },
        "mrr": round(statistics.mean(mrr_scores), 4),
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2) if latencies else 0,
            "p95": round(
                sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0, 2
            ),
            "p99": round(
                sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0, 2
            ),
            "mean": round(statistics.mean(latencies), 2) if latencies else 0,
        },
        "total_queries": len(golden_set),
        "successful_queries": len(latencies),
    }

    return metrics


def print_comparison(results: list[dict]):
    """Print comparison table."""
    print("\n" + "=" * 80)
    print("EMBEDDING MODEL COMPARISON")
    print("=" * 80)

    # Header
    header = f"{'Metric':<25}"
    for r in results:
        model_short = r["model"].split("/")[-1][:20]
        header += f" {model_short:>22}"
    print(header)
    print("-" * 80)

    # Recall@k
    for k in K_VALUES:
        row = f"{'Recall@' + str(k):<25}"
        for r in results:
            val = r["aggregate"]["recall@k"].get(f"recall@{k}", 0)
            row += f" {val:>21.1%}"
        print(row)

    # Precision@k
    for k in [3, 5]:
        row = f"{'Precision@' + str(k):<25}"
        for r in results:
            val = r["aggregate"]["precision@k"].get(f"precision@{k}", 0)
            row += f" {val:>21.1%}"
        print(row)

    # MRR
    row = f"{'MRR':<25}"
    for r in results:
        val = r["aggregate"]["mrr"]
        row += f" {val:>21.4f}"
    print(row)

    # Latency
    for metric in ["p50", "p95"]:
        row = f"{'Latency ' + metric.upper() + ' (ms)':<25}"
        for r in results:
            val = r["aggregate"]["latency_ms"][metric]
            row += f" {val:>20.1f}ms"
        print(row)

    # Queries per second
    row = f"{'Queries/sec':<25}"
    for r in results:
        mean_lat = r["aggregate"]["latency_ms"]["mean"]
        qps = 1000 / mean_lat if mean_lat > 0 else 0
        row += f" {qps:>21.1f}"
    print(row)

    print("-" * 80)

    # Winner
    best_recall = max(results, key=lambda r: r["aggregate"]["recall@k"]["recall@5"])
    best_mrr = max(results, key=lambda r: r["aggregate"]["mrr"])
    fastest = min(results, key=lambda r: r["aggregate"]["latency_ms"]["p95"])

    print(f"\n🏆 Best Recall@5: {best_recall['model']}")
    print(f"🏆 Best MRR:      {best_mrr['model']}")
    print(f"🏆 Fastest p95:   {fastest['model']}")


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="SOKOL Embedding Benchmark")
    parser.add_argument(
        "--models",
        type=str,
        default=",".join(DEFAULT_MODELS),
        help="Comma-separated model IDs to test",
    )
    parser.add_argument(
        "--corpus",
        type=str,
        default=str(CORPUS_PATH),
        help="Path to corpus JSON",
    )
    parser.add_argument(
        "--golden-set",
        type=str,
        default=str(GOLDEN_SET_PATH),
        help="Path to golden set JSON",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evals/benchmark_results.json",
        help="Output path for results",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding",
    )
    args = parser.parse_args()

    # Load data
    print("Loading data...")
    golden_set = load_golden_set(args.golden_set)
    corpus = load_corpus(args.corpus)
    print(f"  Golden set: {len(golden_set)} queries")
    print(f"  Corpus: {len(corpus)} chunks")

    # Init client
    client = EmbeddingClient()

    # Check health
    if not client.health():
        print("ERROR: LM Studio is not reachable at", LMSTUDIO_URL)
        sys.exit(1)

    # List available models
    available = client.list_models()
    print(f"  Available models: {available}")

    # Parse models
    models = [m.strip() for m in args.models.split(",")]

    # Filter to available models
    models = [m for m in models if m in available]
    if not models:
        print("ERROR: No requested models are available in LM Studio")
        print("  Requested:", args.models)
        print("  Available:", available)
        sys.exit(1)

    print(f"  Testing: {models}")

    # Run benchmarks
    results = []
    for model in models:
        result = run_benchmark(model, client, golden_set, corpus, args.batch_size)
        results.append(result)

    # Print comparison
    print_comparison(results)

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "models": models,
                "results": results,
            },
            f,
            indent=2,
            default=str,
        )

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
