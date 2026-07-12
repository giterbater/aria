from __future__ import annotations

import datetime
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def _canonical(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


@dataclass
class EntityNode:
    id: str
    label: str
    kind: str = "entity"
    confidence: float = 1.0
    created_at: datetime.datetime = field(default_factory=_now)
    updated_at: datetime.datetime = field(default_factory=_now)
    sources: list[str] = field(default_factory=list)


@dataclass
class RelationshipEdge:
    id: str
    source_id: str
    relation: str
    target_id: str
    confidence: float = 1.0
    created_at: datetime.datetime = field(default_factory=_now)
    updated_at: datetime.datetime = field(default_factory=_now)
    sources: list[str] = field(default_factory=list)


@dataclass
class GraphFact:
    subject: str
    relation: str
    object: str
    confidence: float = 1.0
    source: str = "conversation"


class SemanticGraph:
    """Persistent graph of language-level entities and relationships."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else None
        self._nodes: dict[str, EntityNode] = {}
        self._edges: dict[str, RelationshipEdge] = {}
        if self._path and self._path.exists():
            self.load()

    def add_fact(
        self,
        subject: str,
        relation: str,
        object: str,
        *,
        confidence: float = 1.0,
        source: str = "conversation",
    ) -> GraphFact:
        subject_node = self._upsert_node(subject, source=source, confidence=confidence)
        object_node = self._upsert_node(object, source=source, confidence=confidence)
        edge_id = self._edge_id(subject_node.id, relation, object_node.id)
        now = _now()
        existing = self._edges.get(edge_id)
        if existing:
            existing.confidence = max(existing.confidence, confidence)
            existing.updated_at = now
            if source not in existing.sources:
                existing.sources.append(source)
        else:
            self._edges[edge_id] = RelationshipEdge(
                id=edge_id,
                source_id=subject_node.id,
                relation=_canonical(relation),
                target_id=object_node.id,
                confidence=confidence,
                sources=[source],
            )
        self.save()
        return GraphFact(subject_node.label, _canonical(relation), object_node.label, confidence, source)

    def remove_fact(self, subject: str, relation: str, object: str) -> bool:
        edge_id = self._edge_id(_canonical(subject), relation, _canonical(object))
        removed = self._edges.pop(edge_id, None) is not None
        if removed:
            self.save()
        return removed

    def query(
        self,
        subject: str | None = None,
        relation: str | None = None,
        object: str | None = None,
    ) -> list[GraphFact]:
        subject_id = _canonical(subject) if subject else None
        target_id = _canonical(object) if object else None
        relation_id = _canonical(relation) if relation else None
        facts: list[GraphFact] = []
        for edge in self._edges.values():
            if subject_id and edge.source_id != subject_id:
                continue
            if target_id and edge.target_id != target_id:
                continue
            if relation_id and edge.relation != relation_id:
                continue
            source = self._nodes.get(edge.source_id)
            target = self._nodes.get(edge.target_id)
            if source and target:
                facts.append(GraphFact(source.label, edge.relation, target.label, edge.confidence, ", ".join(edge.sources)))
        return facts

    def neighbors(self, entity: str) -> list[GraphFact]:
        entity_id = _canonical(entity)
        return [
            fact for fact in self.query()
            if _canonical(fact.subject) == entity_id or _canonical(fact.object) == entity_id
        ]

    def related_entities(self, entity: str, limit: int = 10) -> list[EntityNode]:
        ids: list[str] = []
        entity_id = _canonical(entity)
        for edge in self._edges.values():
            if edge.source_id == entity_id:
                ids.append(edge.target_id)
            elif edge.target_id == entity_id:
                ids.append(edge.source_id)
        seen: set[str] = set()
        nodes: list[EntityNode] = []
        for node_id in ids:
            if node_id not in seen and node_id in self._nodes:
                seen.add(node_id)
                nodes.append(self._nodes[node_id])
        return nodes[:limit]

    def search(self, text: str, limit: int = 10) -> list[EntityNode | GraphFact]:
        q = _canonical(text)
        results: list[EntityNode | GraphFact] = []
        for node in self._nodes.values():
            if q in node.id or any(part in node.id for part in q.split()):
                results.append(node)
        for fact in self.query():
            blob = _canonical(f"{fact.subject} {fact.relation} {fact.object}")
            if q in blob or any(part in blob for part in q.split()):
                results.append(fact)
        return results[:limit]

    def merge_duplicates(self) -> int:
        groups: dict[str, list[str]] = {}
        for node_id in self._nodes:
            groups.setdefault(_canonical(node_id), []).append(node_id)
        merged = 0
        for canonical, node_ids in groups.items():
            if len(node_ids) < 2:
                continue
            keeper = node_ids[0]
            for duplicate in node_ids[1:]:
                self._merge_node(keeper, duplicate)
                merged += 1
        if merged:
            self.save()
        return merged

    def save(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": [self._dump_dataclass(n) for n in self._nodes.values()],
            "edges": [self._dump_dataclass(e) for e in self._edges.values()],
        }
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self._path:
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._nodes = {
            item["id"]: EntityNode(
                **{**item, "created_at": datetime.datetime.fromisoformat(item["created_at"]),
                   "updated_at": datetime.datetime.fromisoformat(item["updated_at"])}
            )
            for item in data.get("nodes", [])
        }
        self._edges = {
            item["id"]: RelationshipEdge(
                **{**item, "created_at": datetime.datetime.fromisoformat(item["created_at"]),
                   "updated_at": datetime.datetime.fromisoformat(item["updated_at"])}
            )
            for item in data.get("edges", [])
        }

    def _upsert_node(self, label: str, *, source: str, confidence: float) -> EntityNode:
        node_id = _canonical(label)
        now = _now()
        existing = self._nodes.get(node_id)
        if existing:
            existing.confidence = max(existing.confidence, confidence)
            existing.updated_at = now
            if source not in existing.sources:
                existing.sources.append(source)
            return existing
        node = EntityNode(id=node_id, label=label.strip(), confidence=confidence, sources=[source])
        self._nodes[node_id] = node
        return node

    def _merge_node(self, keeper: str, duplicate: str) -> None:
        kept = self._nodes[keeper]
        dup = self._nodes.pop(duplicate)
        kept.confidence = max(kept.confidence, dup.confidence)
        kept.sources = sorted(set(kept.sources + dup.sources))
        for edge in self._edges.values():
            if edge.source_id == duplicate:
                edge.source_id = keeper
            if edge.target_id == duplicate:
                edge.target_id = keeper

    @staticmethod
    def _edge_id(subject_id: str, relation: str, object_id: str) -> str:
        return f"{_canonical(subject_id)}::{_canonical(relation)}::{_canonical(object_id)}"

    @staticmethod
    def _dump_dataclass(obj) -> dict:
        data = asdict(obj)
        data["created_at"] = obj.created_at.isoformat()
        data["updated_at"] = obj.updated_at.isoformat()
        return data
