"""Heuristics complement transformative design and critique; not a legal verdict."""
from __future__ import annotations

import difflib
import re
import unicodedata
from collections import Counter

from inkbound.authoring.ingest import Book
from inkbound.realm.models import RealmSpec, PlayerDefinition, NPC, Faction, Location, EnemyArchetype, Item
from inkbound.realm.validation import Issue


def words(text):
    text = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", text)


def cjk_letters(text):
    return "".join(re.findall(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", unicodedata.normalize("NFKC", text)))


def prose_fields(value, path):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for v in value: yield from prose_fields(v, path)
    elif isinstance(value, dict):
        for key, v in value.items(): yield from prose_fields(v, path + "." + key)


def copied_prose_issues(content, book: Book) -> list[Issue]:
    source = words(book.text)
    spans = {tuple(source[i:i + 10]) for i in range(max(0, len(source) - 9))}
    letters = cjk_letters(book.text)
    character_spans = {letters[i:i + 32] for i in range(max(0, len(letters) - 31))}
    issues = []
    for path, text in content:
        tokens = words(text)
        letters = cjk_letters(text)
        if any(tuple(tokens[i:i + 10]) in spans for i in range(max(0, len(tokens) - 9))) or any(letters[i:i + 32] in character_spans for i in range(max(0, len(letters) - 31))):
            issues.append(Issue("copied_prose", path, "Generated prose repeats a source sequence of ten words or 32 CJK characters"))
    return issues


def protected_names(book: Book) -> set[str]:
    # Sentence-start capitalizations alone aren't names; collect interior/title/frequent candidates.
    candidates = re.findall(r"\b[A-Z][a-z]{2,}(?:[ \t]+[A-Z][a-z]{2,}){0,2}\b", book.text)
    counts = Counter(candidates)
    names = set()
    stop = {"The", "This", "That", "There", "Chapter", "Part", "Book", "She", "They", "His", "Her", "When", "After", "Before", "Beyond", "In", "On", "It", "And", "But"}
    for name in candidates:
        tokens = [t for t in name.split() if t not in stop and t not in {"King", "Queen", "Captain", "Lord", "Lady"}]
        if tokens and (len(name.split()) > 1 or counts[name] > 1):
            names.add(" ".join(tokens).lower())
    return names


def originality_issues(spec: RealmSpec, book: Book) -> list[Issue]:
    issues = []
    names = protected_names(book) if not spec.metadata.adaptation.allow_source_names else set()
    content: list[tuple[str, str]] = []
    for entity in spec.entities():
        content.extend([(entity.id, entity.name), (entity.id, entity.description), (entity.id, entity.provenance.rationale)])
        for field in ("background", "appearance", "personality", "motivation", "culture", "ideology", "lore"):
            value = getattr(entity, field, None)
            if isinstance(value, str): content.append((entity.id, value))
        if isinstance(entity, (PlayerDefinition, NPC, Faction, Location, EnemyArchetype, Item)):
            name = entity.name.lower()
            for protected in names:
                if protected == name or protected in name.split() or (len(protected) >= 5 and difflib.SequenceMatcher(None, protected, name).ratio() >= 0.82):
                    issues.append(Issue("source_name_reuse", entity.id, "Name copies or trivially mutates a source identity")); break
            if spec.metadata.adaptation.mode == "original_inspiration" and len(entity.provenance.transformations) < 4:
                issues.append(Issue("shallow_transformation", entity.id, "Explain at least four changed dimensions, beyond naming"))
    for dialogue in spec.dialogues:
        content.extend((dialogue.id, node.text) for node in dialogue.nodes)
        content.extend((dialogue.id, c.text) for node in dialogue.nodes for c in node.choices)
    content.extend(("history", h.event) for h in spec.history)
    content.extend(prose_fields(spec.creative_direction.model_dump(mode="json"), "creative_direction"))
    return issues + copied_prose_issues(content, book)
