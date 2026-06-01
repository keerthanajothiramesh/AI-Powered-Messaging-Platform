"""Typed state shared across all LangGraph nodes."""
from __future__ import annotations
from typing import Any, Dict, Optional, TypedDict


class AgentState(TypedDict):
    # inputs
    query: str
    user_id: str
    context: Dict[str, Any]
    # routing
    intent: str
    retry_query: Optional[str]
    # per-agent outputs
    moderation_result: Optional[Dict[str, Any]]
    search_result: Optional[Dict[str, Any]]
    summarisation_result: Optional[Dict[str, Any]]
    delivery_result: Optional[Dict[str, Any]]
    notification_result: Optional[Dict[str, Any]]
    judge_result: Optional[Dict[str, Any]]
    # control
    retry_count: int
    final_response: Optional[Dict[str, Any]]
    error: Optional[str]
