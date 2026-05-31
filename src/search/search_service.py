from typing import List, Dict, Any, Optional
from src.common.logger import get_logger

logger = get_logger(__name__)


async def hybrid_search(
    query: str,
    n_results: int = 10,
    filters: Optional[Dict] = None,
) -> List[Dict[str, Any]]:
    semantic_results = await _semantic_search(query, n_results, filters)
    bm25_results = await _bm25_search(query, n_results, filters)
    fused = _reciprocal_rank_fusion(semantic_results, bm25_results, k=60)
    return fused[:n_results]


async def _semantic_search(
    query: str, n_results: int, filters: Optional[Dict]
) -> List[Dict]:
    try:
        from src.ai.vector_store import get_vector_store
        from src.ai.embedding_service import get_embedding_service

        vs = get_vector_store()
        if not vs:
            return []

        svc = get_embedding_service()
        embedding = None
        if svc:
            embedding = await svc.generate_embedding_async(query)

        results = vs.search_similar(query, n_results=n_results, filters=filters, query_embedding=embedding)
        return results
    except Exception as e:
        logger.error("semantic_search_failed", error=str(e))
        return []


async def _bm25_search(
    query: str, n_results: int, filters: Optional[Dict]
) -> List[Dict]:
    try:
        from src.common.database import get_mongo_db
        from rank_bm25 import BM25Okapi

        db = get_mongo_db()
        mongo_filter: Dict = {}
        if filters:
            if filters.get("sender_id"):
                mongo_filter["sender_id"] = filters["sender_id"]
            if filters.get("group_id"):
                mongo_filter["group_id"] = filters["group_id"]
            if filters.get("media_type"):
                mongo_filter["media_type"] = filters["media_type"]
            if filters.get("language"):
                mongo_filter["language"] = filters["language"]

        cursor = db.messages.find(
            {**mongo_filter, "media_type": "text", "deleted": {"$ne": True}},
            {"message_id": 1, "content": 1, "sender_id": 1, "group_id": 1,
             "receiver_id": 1, "timestamp": 1, "media_type": 1},
        ).sort("timestamp", -1).limit(2000)
        messages = await cursor.to_list(length=2000)

        if not messages:
            return []

        corpus = [m["content"].lower().split() for m in messages]
        bm25 = BM25Okapi(corpus)
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)

        ranked = sorted(
            zip(scores, messages), key=lambda x: x[0], reverse=True
        )[:n_results]

        results = []
        for score, msg in ranked:
            if score > 0:
                ts = msg.get("timestamp")
                results.append({
                    "message_id": msg["message_id"],
                    "content": msg["content"],
                    "score": float(score),
                    "metadata": {
                        "sender_id": str(msg.get("sender_id", "")),
                        "group_id": str(msg.get("group_id", "")) if msg.get("group_id") else "",
                        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                        "media_type": msg.get("media_type", "text"),
                    },
                })
        return results
    except Exception as e:
        logger.error("bm25_search_failed", error=str(e))
        return []


def _reciprocal_rank_fusion(
    list1: List[Dict], list2: List[Dict], k: int = 60
) -> List[Dict]:
    scores: Dict[str, float] = {}
    docs: Dict[str, Dict] = {}

    for rank, item in enumerate(list1):
        msg_id = item["message_id"]
        scores[msg_id] = scores.get(msg_id, 0) + 1.0 / (k + rank + 1)
        docs[msg_id] = item

    for rank, item in enumerate(list2):
        msg_id = item["message_id"]
        scores[msg_id] = scores.get(msg_id, 0) + 1.0 / (k + rank + 1)
        docs.setdefault(msg_id, item)

    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [{**docs[i], "rrf_score": scores[i]} for i in sorted_ids]


async def search_media(
    query: str, media_type: Optional[str] = None, n_results: int = 20
) -> List[Dict]:
    try:
        from src.ai.vector_store import get_vector_store
        vs = get_vector_store()
        if vs:
            return vs.search_media(query, n_results=n_results, media_type=media_type)

        from src.common.database import get_mongo_db
        db = get_mongo_db()
        mongo_filter = {"media_type": {"$ne": "text"}}
        if media_type:
            mongo_filter["media_type"] = media_type

        cursor = db.messages.find(
            {**mongo_filter, "content": {"$regex": query, "$options": "i"}}
        ).limit(n_results)
        messages = await cursor.to_list(length=n_results)
        results = []
        for m in messages:
            m.pop("_id", None)
            results.append({"message_id": m["message_id"], "content": m.get("content", ""), "metadata": m})
        return results
    except Exception as e:
        logger.error("media_search_failed", error=str(e))
        return []
