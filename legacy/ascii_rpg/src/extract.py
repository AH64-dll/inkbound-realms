"""Lightweight lore extraction without heavy NLP deps.

Strategy: proper-noun candidates via regex, ranked by frequency,
classified by surrounding context keywords into people / places / groups.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2}\b")

STOPWORDS = {
    "The", "This", "That", "These", "Those", "There", "Here", "When", "Where",
    "Which", "While", "After", "Before", "Because", "However", "Although",
    "Chapter", "Part", "Page", "Book", "Volume", "Then", "Thus", "And", "But",
    "For", "With", "From", "Into", "Over", "Under", "Monday", "Tuesday",
    "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "June", "July", "August",
    "September", "October", "November", "December", "His", "Her", "Their",
    "Your", "Our", "Its", "She", "You", "They", "One", "Two", "Three",
    "Chronicle", "King", "Queen", "Lord", "Lady", "Captain", "Prince",
    "Princess", "Master", "Sir",
}

LEADING_ARTICLES_RE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)

KNOWN_GROUPS = {
    "elves", "dwarves", "dwarf", "orcs", "orc", "men", "humans", "human",
    "elvesfolk", "fae", "goblins", "goblin", "trolls", "undead", "gods",
}

PLACE_HINTS = {
    "city", "town", "village", "kingdom", "land", "empire", "castle", "port",
    "realm", "province", "harbor", "harbour", "forest", "mountain", "river",
    "island", "desert", "capital", "fort", "shire", "hold", "gate", "wall",
    "tower", "bridge", "valley", "bay", "coast", "docks", "market", "temple",
    "of", "in", "from", "to", "at", "near",
}

PERSON_HINTS = {
    "said", "asked", "replied", "shouted", "whispered", "cried", "laughed",
    "king", "queen", "lord", "lady", "sir", "captain", "prince", "princess",
    "wizard", "witch", "knight", "master", "brother", "sister", "father",
    "mother", "son", "daughter", "he", "she", "his", "her", "him",
}

GROUP_HINTS = {
    "people", "tribe", "clan", "race", "folk", "army", "horde", "order",
    "guild", "council", "men", "women", "children", "warriors", "soldiers",
    "elves", "dwarves", "orcs", "gods",
}


@dataclass
class Lore:
    people: list[str] = field(default_factory=list)
    places: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)  # frequent lore nouns
    flavor_lines: list[str] = field(default_factory=list)
    relic_words: list[str] = field(default_factory=list)  # name-safe nouns
    book_events: list = field(default_factory=list)  # {kind, names, snippet}
    relations: list = field(default_factory=list)  # {sub, verb, obj, snippet}
    role_tags: dict = field(default_factory=dict)  # person -> {killer,...}


TITLES_LOW = {"king", "queen", "lord", "lady", "sir", "captain", "prince",
              "princess", "master", "chronicle"}


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 20][:5000]


def extract_entities(text: str, top_n: int = 40) -> Lore:
    lore = Lore()
    if not text or not text.strip():
        return lore

    candidates = PROPER_NOUN_RE.findall(text)
    # Normalize whitespace, drop stopwords / single common words
    cleaned: list[str] = []
    for c in candidates:
        c = re.sub(r"\s+", " ", c).strip()
        c = LEADING_ARTICLES_RE.sub("", c).strip()
        if not c:
            continue
        words = c.split()
        if any(w in STOPWORDS for w in words):
            # Allow "King Aldor" style but drop lone "The"
            if len(words) == 1:
                continue
        if len(c) < 3:
            continue
        cleaned.append(c)

    freq = Counter(cleaned)
    # Drop single words that ONLY ever appear as the first word of a sentence
    # (e.g. "Beyond the forest..." -> "Beyond" is not a name).
    non_initial: Counter = Counter()
    for m in PROPER_NOUN_RE.finditer(text):
        raw = re.sub(r"\s+", " ", m.group(0)).strip()
        cand = LEADING_ARTICLES_RE.sub("", raw).strip()
        if not cand or " " in cand:
            continue  # multi-word names are rarely sentence-start artifacts
        prefix = text[max(0, m.start() - 3):m.start()]
        if not re.search(r"(^|[.!?]\s*)$", prefix):
            non_initial[cand] += 1
    ranked = [name for name, _ in freq.most_common(top_n * 3)
              if " " in name or freq[name] > 1 or non_initial.get(name, 0) > 0]

    sentences = _split_sentences(text)
    # index sentences containing each candidate for context + flavor
    sent_index: dict[str, list[str]] = {name: [] for name in ranked}
    lower_sents = [s.lower() for s in sentences]
    for name in ranked:
        nl = name.lower()
        for s, ls in zip(sentences, lower_sents):
            if nl in ls:
                sent_index[name].append(s)
                if len(sent_index[name]) >= 5:
                    break

    people, places, groups = [], [], []
    for name in ranked:
        first = name.split()[0].lower() if name.split() else ""
        if first in {"king", "queen", "lord", "lady", "sir", "captain",
                     "prince", "princess", "master"}:
            if name not in people:
                people.append(name)
            continue
        contexts = " ".join(sent_index.get(name, [])).lower()
        words = set(re.findall(r"[a-z]+", contexts))
        # Known fantasy peoples always count as groups
        if name.lower() in KNOWN_GROUPS or name.lower().rstrip("s") in KNOWN_GROUPS:
            if name not in groups:
                groups.append(name)
            continue
        place_score = len(words & PLACE_HINTS)
        # boost if preceded by "city of X" pattern in raw text
        if re.search(r"(city|town|village|kingdom|land|empire|castle|port|realm)\s+of\s+" + re.escape(name),
                     text, re.IGNORECASE):
            place_score += 3
        # boost if "X castle / X city" pattern
        if re.search(re.escape(name) + r"\s+(city|town|castle|port|forest|river|mountain|kingdom|gate|wall|tower)",
                     text, re.IGNORECASE):
            place_score += 2
        person_score = len(words & PERSON_HINTS)
        if re.search(r"(King|Queen|Lord|Lady|Sir|Captain|Prince|Princess|Master)\s+" + re.escape(name.split()[-1]), text):
            person_score += 3
        group_score = len(words & GROUP_HINTS)
        if name.endswith("s") and len(name.split()) == 1:
            group_score += 1

        # Multi-word names default to people unless place signals dominate
        if place_score >= 2 and place_score >= person_score:
            if name not in places:
                places.append(name)
        elif person_score >= 1 or len(name.split()) > 1:
            if name not in people:
                people.append(name)
        elif group_score >= 1:
            if name not in groups:
                groups.append(name)
        else:
            # single-word unknowns: alternate to keep pools filled
            if len(places) <= len(people):
                places.append(name)
            else:
                people.append(name)

        if len(people) >= top_n and len(places) >= top_n // 2:
            break

    # frequent lowercase lore nouns (magic, sword, dragon...)
    words = re.findall(r"[a-z]{4,}", text.lower())
    common = Counter(words)
    boring = {"that", "this", "with", "from", "have", "were", "been", "they",
              "them", "then", "than", "when", "what", "where", "there", "here",
              "would", "could", "should", "your", "their", "about", "into",
              "ruled", "said", "asked", "replied", "whispered", "shouted",
              "cried", "laughed", "traveled", "carried", "knew", "met",
              "spoke", "promised", "guard", "king", "queen", "city",
              "kingdom", "lord", "captain"}
    terms = [w for w, _ in common.most_common(60) if w not in boring][:20]

    # flavor lines: sentences mentioning top people/places
    flavor = []
    top_keys = (people[:8] + places[:8]) or ranked[:8]
    for s in sentences:
        sl = s.lower()
        if any(k.lower() in sl for k in top_keys):
            flavor.append(s.strip()[:220])
            if len(flavor) >= 30:
                break

    lore.people = people[:top_n]
    lore.places = places[: max(10, top_n // 2)]
    lore.groups = groups[:10]
    lore.terms = terms
    lore.flavor_lines = flavor
    # relic words: name-safe NOUNS only (entity fragments + curated fallbacks).
    # This is the pool for blades, rings, foes, and spells — never verbs.
    seen: set[str] = set()
    relics: list[str] = []
    for ent in lore.people + lore.places + lore.groups:
        for tok in re.findall(r"[A-Za-z]{4,}", ent):
            word = tok.capitalize()
            if word in STOPWORDS or word.lower() in TITLES_LOW:
                continue
            if word.lower() not in seen:
                seen.add(word.lower())
                relics.append(word)
    lore.relic_words = relics[:24]
    lore.book_events = extract_book_events(text)
    lore.relations, lore.role_tags = mine_relations(text, lore)
    return lore


# ---------------- relation triples ----------------
# Who did what to whom: NAME VERB NAME over sentences, with paragraph-local
# coreference (he/she -> last soul, the king -> titled soul) so pronouns and
# titles resolve, not just proper nouns. Feeds rivalries, lineages, and roles.

REL_VERBS: dict[str, list[str]] = {
    "slay": [r"\bslew\b", r"\bslay\b", r"\bslays\b", r"\bslain\b",
             r"\bkilled\b", r"\bkill\b", r"\bmurdered\b", r"\bmurder\b",
             r"\bavenged\b", r"\bavenge\b", r"\bexecuted\b"],
    "rule": [r"\bruled\b", r"\brules\b", r"\brule\b", r"\breigned\b",
             r"\breign\b", r"\bg governed\b", r"\bcrowned\b"],
    "wed": [r"\bwed\b", r"\bwedded\b", r"\bmarried\b", r"\bmarry\b",
            r"\bmarriage\b"],
    "betray": [r"\bbetrayed\b", r"\bbetray\b", r"\bbetrayal\b", r"\btreason\b"],
    "flee": [r"\bfled\b", r"\bflee\b", r"\bflees\b", r"\bescaped\b",
             r"\bbanished\b", r"\bexiled\b"],
    "siege": [r"\bsiege\b", r"\bbesieged\b", r"\bsacked\b", r"\bsack\b",
              r"\bstormed\b"],
    "serve": [r"\bserved\b", r"\bserve\b", r"\bswore\b", r"\bsworn\b",
              r"\bloyal\b"],
    "steal": [r"\bstole\b", r"\bsteal\b", r"\bstolen\b", r"\bseized\b"],
    "save": [r"\bsaved\b", r"\bsave\b", r"\brescued\b", r"\brescue\b"],
    "curse": [r"\bcursed\b", r"\bcurse\b", r"\bdoomed\b"],
    "burn": [r"\bburned\b", r"\bburnt\b", r"\bburn\b", r"\brazed\b"],
    "build": [r"\bbuilt\b", r"\bbuild\b", r"\bfounded\b", r"\braised\b"],
}

TITLE_WORDS = {"king", "queen", "lord", "lady", "sir", "prince", "princess",
               "captain", "master", "knight", "baron", "priest", "mage"}

HE_WORDS = {"he", "him", "his"}
SHE_WORDS = {"she", "her", "hers"}
THEY_WORDS = {"they", "them", "their", "theirs"}


def _title_index(text: str, people: list[str]) -> dict[str, str]:
    """Map 'the king' -> 'King Aldor' via TITLE Name sightings."""
    idx: dict[str, str] = {}
    for m in re.finditer(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", text):
        title, name = m.group(1).lower(), m.group(2)
        if title not in TITLE_WORDS:
            continue
        for p in people:
            if p == name or p.endswith(" " + name.split()[-1]) or name in p:
                idx[title] = p
                break
    return idx


def mine_relations(text: str, lore) -> tuple[list[dict], dict[str, set]]:
    """Return ([{sub, verb, obj, snippet}], {person: {roles}})."""
    people = list(getattr(lore, "people", []) or [])
    places = list(getattr(lore, "places", []) or [])
    groups = list(getattr(lore, "groups", []) or [])
    if not text or not text.strip() or not people:
        return [], {}
    entities = sorted(set(people + places + groups), key=len, reverse=True)
    # lone surnames resolve when unambiguous ("Aldor" is King Aldor)
    alias: dict[str, str] = {}
    for p in people:
        last = p.split()[-1]
        if last != p and sum(1 for q in people if q.split()[-1] == last) == 1:
            alias[last] = p
    ent_pat = re.compile("|".join(re.escape(e) for e in (entities + list(alias))[:160]))

    def norm(name: str) -> str:
        return alias.get(name, name)
    pats = {k: [re.compile(w, re.IGNORECASE) for w in words]
            for k, words in REL_VERBS.items()}
    titles = _title_index(text, people)
    relations: list[dict] = []
    roles: dict[str, set] = {}

    def tag(name: str, role: str) -> None:
        if name in people:
            roles.setdefault(name, set()).add(role)

    paragraphs = re.split(r"\n\s*\n", text)
    last_person, last_place, last_group = "", "", ""
    for para in paragraphs:
        for sent in _split_sentences(para):
            low = sent.lower()
            hit, mobj = "", None
            for kind, regs in pats.items():
                for rx in regs:
                    m = rx.search(low)
                    if m:
                        hit, mobj = kind, m
                        break
                if hit:
                    break
            if not hit or mobj is None:
                for m in ent_pat.finditer(sent):
                    nm = m.group(0)
                    if nm in people:
                        last_person = nm
                    elif nm in places:
                        last_place = nm
                    elif nm in groups:
                        last_group = nm
                continue
            vpos = mobj.start()

            def mention_at(pos: int, backward: bool) -> str:
                best, best_d = "", 10 ** 9
                for m in ent_pat.finditer(sent):
                    d = pos - m.end() if backward else m.start() - pos
                    if 0 <= d < best_d:
                        best, best_d = m.group(0), d
                if best:
                    return best
                # pronouns and titled references name discourse entities;
                # reach backward first, then forward ("betrayed him")
                for window in (sent[max(0, pos - 60):pos],
                               sent[pos:pos + 60]):
                    toks = re.findall(r"[a-z]+", window.lower())
                    if backward:
                        toks = list(reversed(toks))[:8]  # nearest first
                    else:
                        toks = toks[:8]
                    for t in toks:
                        if t in HE_WORDS or t in SHE_WORDS:
                            if last_person:
                                return last_person
                        elif t in THEY_WORDS:
                            if last_group:
                                return last_group
                            if last_person:
                                return last_person
                        elif t in TITLE_WORDS and t in titles:
                            return titles[t]
                return ""

            sub = norm(mention_at(vpos, True))
            obj = norm(mention_at(mobj.end(), False))
            # passive voice: "Y was slain by X"
            bym = re.search(r"\bby\s+([A-Z][A-Za-z ]*?)(?:[,.]|$)", sent[mobj.end():])
            if bym:
                cand = bym.group(1).strip()
                for e in entities + list(alias):
                    if cand == e or cand.endswith(e.split()[-1]) and len(cand.split()) <= 3:
                        sub, obj = norm(e), sub
                        break
            if not sub or not obj or sub == obj:
                for m in ent_pat.finditer(sent):
                    nm = norm(m.group(0))
                    if nm in people:
                        last_person = nm
                    elif nm in places:
                        last_place = nm
                    elif nm in groups:
                        last_group = nm
                continue
            snippet = re.sub(r"\s+", " ", sent.strip())[:200]
            relations.append({"sub": sub, "verb": hit, "obj": obj, "snippet": snippet})
            if hit == "slay":
                tag(sub, "killer")
                tag(obj, "victim")
            elif hit == "rule":
                tag(sub, "ruler")
            elif hit == "wed":
                tag(sub, "spouse")
                tag(obj, "spouse")
            elif hit == "betray":
                tag(sub, "betrayer")
                tag(obj, "wronged")
            elif hit == "flee":
                tag(sub, "exiled")
            elif hit == "siege":
                tag(sub, "besieger")
            elif hit == "serve":
                tag(sub, "sworn")
            elif hit == "curse":
                tag(obj, "wronged")
            for m in ent_pat.finditer(sent):
                nm = norm(m.group(0))
                if nm in people:
                    last_person = nm
                elif nm in places:
                    last_place = nm
                elif nm in groups:
                    last_group = nm
            if len(relations) >= 200:
                return relations, roles
    return relations, roles


# ---------------- book-event mining ----------------
# Verb-frame extraction: happenings in the books become {kind, names, snippet}
# Verb-frame extraction: happenings in the books become {kind, names, snippet}
# events that feed quest seeds, history seeds, and the director deck.
# Frequency voting over single parses: common kinds rank first.

BOOK_EVENT_FRAMES: dict[str, list[str]] = {
    "battle": [r"\bslew\b", r"\bslay\b", r"\bslays\b", r"\bslain\b",
               r"\bbattle\b", r"\bfought\b", r"\bfight\b", r"\bkilled\b",
               r"\bkill\b", r"\bwar\b"],
    "siege": [r"\bsiege\b", r"\bbesieged\b", r"\bsacked\b", r"\bsack\b",
              r"\bstormed\b", r"\brazed\b"],
    "exodus": [r"\bfled\b", r"\bflee\b", r"\bflees\b", r"\bexile\b",
               r"\bbanished\b", r"\bescaped\b"],
    "union": [r"\bwed\b", r"\bwedding\b", r"\bmarried\b", r"\bmarriage\b",
              r"\balliance\b", r"\bcouncil\b"],
    "betrayal": [r"\bbetrayed\b", r"\bbetray\b", r"\bbetrayal\b",
                 r"\btreason\b", r"\btreachery\b"],
    "storm": [r"\bstorm\b", r"\btempest\b", r"\bflood\b", r"\bdrought\b"],
    "plague": [r"\bplague\b", r"\bpestilence\b", r"\bfever\b", r"\bfamine\b"],
    "voyage": [r"\bvoyage\b", r"\bsailed\b", r"\bsail\b", r"\bvoyager\b",
               r"\bexpedition\b", r"\bjourney\b"],
}


def extract_book_events(text: str, limit: int = 40) -> list[dict]:
    """Mine verb-frame happenings: [{kind, names, snippet}]."""
    if not text or not text.strip():
        return []
    sents = _split_sentences(text)
    found: list[dict] = []
    pats: dict[str, list] = {}
    for kind, words in BOOK_EVENT_FRAMES.items():
        pats[kind] = [re.compile(w, re.IGNORECASE) for w in words]
    for s in sents:
        low = s.lower()
        hit = ""
        for kind, regs in pats.items():
            for rx in regs:
                if rx.search(low):
                    hit = kind
                    break
            if hit:
                break
        if not hit:
            continue
        names = []
        for m in PROPER_NOUN_RE.finditer(s):
            raw = re.sub(r"\s+", " ", m.group(0)).strip()
            cand = LEADING_ARTICLES_RE.sub("", raw).strip()
            if not cand or len(cand) < 3:
                continue
            words = cand.split()
            if len(words) == 1 and words[0] in STOPWORDS:
                continue
            if cand not in names:
                names.append(cand)
            if len(names) >= 3:
                break
        snippet = re.sub(r"\s+", " ", s.strip().replace("\x00", ""))[:220]
        if snippet:
            found.append({"kind": hit, "names": names[:3], "snippet": snippet})
        if len(found) >= 400:
            break
    # frequency voting over single parses, but keep diversity: kinds ordered
    # by count, then round-robin so the deck sees sieges and voyages too
    from collections import Counter as _C
    counts = _C(e["kind"] for e in found)
    by_kind: dict[str, list[dict]] = {}
    for e in found:
        by_kind.setdefault(e["kind"], []).append(e)
    ranked_kinds = sorted(by_kind, key=lambda k: -counts.get(k, 0))
    out: list[dict] = []
    i = 0
    while len(out) < limit and any(by_kind.values()):
        for k in ranked_kinds:
            if by_kind[k] and len(out) < limit:
                out.append(by_kind[k].pop(0))
        i += 1
        if i > limit * 2:
            break
    return out
