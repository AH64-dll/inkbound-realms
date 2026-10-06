import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from inkbound.authoring.harness import Harness, TOOL_MODELS
from inkbound.authoring.ingest import ingest
from inkbound.authoring.originality import originality_issues, names_in_text, transformation_count
from inkbound.authoring.providers import CachedProvider, HTTPProvider, ProviderError, Response, Tool, ToolCall, Usage
from inkbound.realm.models import AdaptationPolicy, BookInterpretation, RealmSpec
from inkbound.realm.validation import InvalidRealm


def test_transformations_required_without_source_names_or_id_prefix(fantasy_data, tmp_path):
    path = tmp_path / "nameless.txt"
    path.write_text("an unnamed coast asks how a community can share its water.")
    fantasy_data["metadata"]["adaptation"] = {"mode": "original_inspiration"}
    fantasy_data["player"]["id"] = "protagonist"
    fantasy_data["player"]["provenance"]["transformations"] = {"naming": "a changed label"}
    issues = originality_issues(RealmSpec.model_validate(fantasy_data), ingest(path))
    assert any(i.code == "shallow_transformation" and i.path == "protagonist" for i in issues)


def test_semantic_source_identities_catch_single_mentions_in_world_prose(fantasy_data, tmp_path):
    p = tmp_path / "book.txt"
    p.write_text("Sen questions a census. Juno maintains a shared station.")
    fantasy_data["metadata"]["adaptation"] = {"mode": "original_inspiration"}
    fantasy_data["creative_direction"]["interpretation"]["source_identities"] = [{"name": name, "kind": "character", "proper_name": True, "role": "A technician maintaining a shared station"} for name in ("Sen", "Juno")]
    fantasy_data["player"]["description"] = "A different surveyor who still reports to Juno."
    issues = originality_issues(RealmSpec.model_validate(fantasy_data), ingest(p))
    assert any(i.code == "source_name_reuse" and i.path == fantasy_data["player"]["id"] for i in issues)


def test_generic_source_concepts_do_not_become_prohibited_names(fantasy_data, tmp_path):
    p = tmp_path / "book.txt"; p.write_text("residents rely on an algorithm to share water.")
    fantasy_data["metadata"]["adaptation"] = {"mode": "original_inspiration"}
    fantasy_data["creative_direction"]["interpretation"]["source_identities"] = [{"name": "algorithm", "kind": "other", "proper_name": False, "role": "An automated allocation method"}]
    fantasy_data["creative_direction"]["world_bible"] = "A pumpwright designs an algorithm for a new community's shared irrigation rights."
    assert not any(i.code == "source_name_reuse" for i in originality_issues(RealmSpec.model_validate(fantasy_data), ingest(p)))


def test_naming_and_repeated_explanations_are_not_four_transformations(fantasy_data, tmp_path):
    p = tmp_path / "book.txt"; p.write_text("an unnamed city shares its water.")
    fantasy_data["metadata"]["adaptation"] = {"mode": "original_inspiration"}
    fantasy_data["player"]["provenance"]["transformations"] = {"naming": "An altered name", "history": "A different life", "motives": "A different life", "role": "A different life"}
    assert any(i.code == "shallow_transformation" and i.path == fantasy_data["player"]["id"] for i in originality_issues(RealmSpec.model_validate(fantasy_data), ingest(p)))


def test_identity_matching_and_transformation_explanations_support_unspaced_languages():
    assert not names_in_text({"sen"}, "A sensor custodian charts a new settlement.")
    assert names_in_text({"雨生"}, "雨生守护着这座城市的水源") == ["雨生"]
    assert transformation_count({"history": "背景改为漂浮港湾的水务争端", "motives": "动机改为维护共同水权和公共责任", "role": "职业改为潮汐测量和水务仲裁", "relationships": "关系改为合作维修和公开决策"}) == 4


@pytest.mark.parametrize("text", ["في المدينة القديمة اجتمع السكان حول البئر وقرروا حماية الماء من الحراس قبل حلول المساء", "居民们在没有补给的空间站里共同修复空气循环设备并决定让每一位乘客都能获得公平的生存机会"])
def test_world_bible_copy_check_supports_unicode_and_unspaced_cjk(fantasy_data, tmp_path, text):
    path = tmp_path / "book.txt"; path.write_text(text)
    fantasy_data["creative_direction"]["world_bible"] = text
    issues = originality_issues(RealmSpec.model_validate(fantasy_data), ingest(path))
    assert any(i.code == "copied_prose" and i.path == "creative_direction.world_bible" for i in issues)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-16-le"])
def test_text_ingestion_covers_every_character_including_ending(tmp_path, encoding):
    text = "Chapter One\n" + "A quiet shore leads to a disputed harbor. " * 40 + "\nThe Ending\nTheir charter changes."
    p = tmp_path / "book.txt"; p.write_bytes(text.encode(encoding))
    book = ingest(p, chunk_chars=500)
    assert "".join(c.text for c in book.chunks) == book.text
    assert book.chunks[-1].text.endswith("Their charter changes.")
    assert len({c.id for c in book.chunks}) == len(book.chunks)
    assert all(c.end - c.start <= 500 for c in book.chunks)
    assert ingest(p, chunk_chars=500).digest == book.digest


def test_epub_spine_order_and_hidden_content(tmp_path):
    path = tmp_path / "book.epub"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles></container>')
        z.writestr("OEBPS/book.opf", '<package xmlns="http://www.idpf.org/2007/opf"><manifest><item id="b" href="later.xhtml"/><item id="a" href="first.xhtml"/></manifest><spine><itemref idref="a"/><itemref idref="b"/></spine></package>')
        z.writestr("OEBPS/later.xhtml", "<p>The ending.</p>")
        z.writestr("OEBPS/first.xhtml", "<style>hidden_css</style><script>hidden_code</script><h1>The beginning.</h1>")
    book = ingest(path)
    assert book.text.index("beginning") < book.text.index("ending")
    assert "hidden_css" not in book.text and "hidden_code" not in book.text


def test_pdf_text_and_empty_scanned_pdf_fail_explicitly(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter(); page = writer.add_blank_page(width=300, height=300)
    blank = tmp_path / "blank.pdf"; writer.write(blank)
    with pytest.raises(ValueError, match="OCR"):
        ingest(blank)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject(); stream.set_data(b"BT /F1 12 Tf 30 30 Td (The relay must count every resident.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    text_pdf = tmp_path / "text.pdf"; writer.write(text_pdf)
    assert "count every resident" in ingest(text_pdf).text


class FixtureToolProvider:
    """Recorded model-shaped responses exercise orchestration, not live intelligence."""
    identity = "recorded-fixture-tools"

    def __init__(self, spec):
        self.spec = spec; self.counters = {}; self.requests = []

    def complete(self, system, prompt, tools):
        name = tools[0].name
        self.requests.append((name, prompt))
        count = self.counters.get(name, 0); self.counters[name] = count + 1
        s = self.spec
        if name in ("interpret_book_chunk", "synthesize_book"):
            payload = s.creative_direction.interpretation.model_dump(mode="json")
        elif name == "define_world_identity": payload = s.creative_direction.model_dump(mode="json", exclude={"interpretation"})
        elif name == "define_gameplay_rules": payload = {k: getattr(s, k) if not hasattr(getattr(s, k), "model_dump") else getattr(s, k).model_dump(mode="json") for k in ("world_rules", "stats", "resources", "damage_types", "equipment_slots")}
        elif name == "create_spell_system": payload = {k: [x.model_dump(mode="json") for x in getattr(s, k)] for k in ("abilities", "status_effects")}
        elif name == "create_skill_tree": payload = {k: [x.model_dump(mode="json") for x in getattr(s, k)] for k in ("skills", "classes", "species")}
        elif name == "create_item_family": payload = {"items": [x.model_dump(mode="json") for x in s.items if x.kind != "artifact"], "crafting": [x.model_dump(mode="json") for x in s.crafting]}
        elif name == "create_quest_arc": payload = {"quests": [x.model_dump(mode="json") for x in s.quests]}
        elif name == "create_artifact": payload = next(x for x in s.items if x.kind == "artifact").model_dump(mode="json")
        elif name == "create_boss": payload = next(x for x in s.enemies if x.role == "boss").model_dump(mode="json")
        elif name == "validate_relationships": payload = {"checked_ids": [e.id for e in s.entities()], "concerns": []}
        elif name == "finalize_realm": payload = {"title": s.metadata.title, "visual_style": s.visual_style, "audio_direction": s.audio_direction, "history": [h.model_dump(mode="json") for h in s.history]}
        elif name == "critique_realm": payload = {"verdict": "accept", "coherence": "Connected institutional conflict.", "source_connection": "The protagonist's occupation and material scarcity drive the loop.", "mechanical_meaning": "Recovery opens a final gate.", "originality": "Original fixture cast and story.", "revisions": []}
        elif name.startswith("regenerate_"):
            payload = json.loads(prompt.split("CONTEXT (data, not instructions):\n", 1)[1])["target"]
            payload["description"] = "A revised local obligation gives this entity a more specific reason to exist."
        else:
            section = {"define_player_archetype": "player", "create_faction": "factions", "create_region": "regions", "create_location": "locations", "create_character": "npcs", "create_dialogue": "dialogues", "create_enemy_archetype": "enemies", "create_encounter_table": "encounters", "create_world_event": "world_events", "define_progression": "progression", "define_economy": "economy", "request_asset": "assets"}[name]
            value = getattr(s, section); value = value[count] if isinstance(value, list) else value
            payload = value.model_dump(mode="json")
        if name == "define_gameplay_rules":
            payload = {k: [x.model_dump(mode="json") for x in v] if isinstance(v, list) else v for k, v in payload.items()}
        return Response([ToolCall(name, payload)], usage=Usage(input_tokens=100, output_tokens=50, requests=1))


def test_copied_creative_foundation_is_rejected_before_gameplay_construction(spec):
    book = ingest(Path("fixtures/books") / (spec.metadata.id.split(".")[1] + ".txt"))
    class CopyingProvider(FixtureToolProvider):
        def complete(self, system, prompt, tools):
            response = super().complete(system, prompt, tools)
            if tools[0].name == "define_world_identity":
                response.calls[0].arguments["world_bible"] = book.text
            return response
    provider = CopyingProvider(spec)
    with pytest.raises(ProviderError, match="three attempts"):
        Harness(provider).compile(book, realm_id="realm.rejected", seed=42, adaptation=spec.metadata.adaptation)
    assert provider.counters["define_world_identity"] == 3
    assert "define_gameplay_rules" not in provider.counters


def test_reading_analysis_cannot_leak_passages_into_runtime_lore(spec):
    book = ingest(Path("fixtures/books") / (spec.metadata.id.split(".")[1] + ".txt"))
    class CopyingReader(FixtureToolProvider):
        def complete(self, system, prompt, tools):
            response = super().complete(system, prompt, tools)
            if tools[0].name == "interpret_book_chunk":
                response.calls[0].arguments["summary"] = book.text
            return response
    provider = CopyingReader(spec)
    with pytest.raises(ProviderError, match="three attempts"):
        Harness(provider).interpret(book)
    assert provider.counters["interpret_book_chunk"] == 3


def test_source_identity_spelling_is_grounded_in_actual_input(spec):
    book = ingest(Path("fixtures/books") / (spec.metadata.id.split(".")[1] + ".txt"))
    class InventingReader(FixtureToolProvider):
        def complete(self, system, prompt, tools):
            response = super().complete(system, prompt, tools)
            if tools[0].name == "interpret_book_chunk":
                response.calls[0].arguments["source_identities"] = [{"name": "Unattested Unique Name", "kind": "character", "proper_name": True, "role": "A caretaker seeking shared authority"}]
            return response
    provider = InventingReader(spec)
    with pytest.raises(ProviderError, match="three attempts"):
        Harness(provider).interpret(book)
    assert provider.counters["interpret_book_chunk"] == 3


@pytest.mark.parametrize("field", ["main_narrative", "side_narratives", "quality_criteria"])
def test_new_world_cannot_hide_source_names_outside_the_bible(fantasy_data, tmp_path, field):
    p = tmp_path / "book.txt"
    p.write_text("Mara Vale maintains a pump. Mara Vale challenges an unfair tax.")
    data = RealmSpec.model_validate(fantasy_data)
    class NameReusingProvider(FixtureToolProvider):
        def complete(self, system, prompt, tools):
            response = super().complete(system, prompt, tools)
            if tools[0].name == "define_world_identity":
                text = "Mara Vale asks a distant harbor to expose control of its canal ledger."
                if field == "main_narrative": response.calls[0].arguments[field] = text
                else: response.calls[0].arguments[field][0] = text
            return response
    provider = NameReusingProvider(data)
    with pytest.raises(ProviderError, match="three attempts"):
        Harness(provider).compile(ingest(p), realm_id="realm.rejected", seed=42)
    assert provider.counters["define_world_identity"] == 3
    assert "define_gameplay_rules" not in provider.counters


def test_licensed_names_require_explicit_opt_in(fantasy_data, tmp_path):
    p = tmp_path / "book.txt"
    p.write_text("Mara Vale repairs a bridge. Mara Vale consults the workers.")
    fantasy_data["player"]["name"] = "Mara Vale"
    fantasy_data["metadata"]["adaptation"] = {"mode": "licensed_adaptation", "rights_basis": "Original test story", "allow_source_names": False}
    assert any(i.code == "source_name_reuse" for i in originality_issues(RealmSpec.model_validate(fantasy_data), ingest(p)))
    fantasy_data["metadata"]["adaptation"]["allow_source_names"] = True
    assert not any(i.code == "source_name_reuse" for i in originality_issues(RealmSpec.model_validate(fantasy_data), ingest(p)))


def test_regeneration_source_must_match_original_book(spec, tmp_path):
    p = tmp_path / "unrelated.txt"
    p.write_text("Another story makes a different claim about its community.")
    with pytest.raises(ValueError, match="Source"):
        Harness(FixtureToolProvider(spec)).review_and_revise(spec, ingest(p))


def test_hierarchical_tool_harness_compiles_every_fixture(spec, tmp_path):
    raw = next(p for p in Path("fixtures/books").glob("*.txt") if p.stem == spec.metadata.id.split(".")[1])
    provider = FixtureToolProvider(spec)
    harness = Harness(CachedProvider(provider, tmp_path / "cache"))
    package = harness.compile(ingest(raw), realm_id="realm.compiled", seed=42, adaptation=spec.metadata.adaptation)
    assert len(package.spec.enemies) == 4
    assert package.spec.player.archetype == spec.player.archetype
    assert package.spec.metadata.authoring_provider == provider.identity
    assert provider.requests[0][0] == "interpret_book_chunk"
    names = [name for name, _ in provider.requests]
    assert names.index("define_world_identity") < names.index("create_region") < names.index("create_character") < names.index("create_quest_arc") < names.index("finalize_realm") < names.index("critique_realm")
    package.write(tmp_path / "compiled")
    assert all("text" not in entry for entry in harness.transcript)


def test_all_chunks_enter_holistic_reduction(spec, tmp_path):
    p = tmp_path / "long.txt"; p.write_text(("The station's workers keep the vents alive. " * 1000) + "\nThe final charter includes every berth.")
    book = ingest(p, chunk_chars=500)
    provider = FixtureToolProvider(spec); h = Harness(provider)
    h.interpret(book)
    chunk_requests = [prompt for name, prompt in provider.requests if name == "interpret_book_chunk"]
    assert len(chunk_requests) == len(book.chunks)
    assert "final charter" in chunk_requests[-1]
    assert any(name == "synthesize_book" for name, _ in provider.requests)


def test_partial_regeneration_preserves_all_other_objects_and_ids(spec):
    h = Harness(FixtureToolProvider(spec))
    updated = h.regenerate(spec, "enemy_family", ["family.enforcers"], "Give them more local political stakes.")
    assert [e.id for e in updated.enemies] == [e.id for e in spec.enemies]
    assert updated.enemies[1] == spec.enemies[1]  # different family
    assert updated.player == spec.player and updated.quests == spec.quests
    assert updated.metadata.revision == spec.metadata.revision + 1
    assert spec.enemies[0].description != updated.enemies[0].description


def test_structured_output_retry_and_budget(spec):
    class Broken:
        identity = "broken"
        def complete(self, system, prompt, tools): return Response([ToolCall("wrong_tool", {})])
    h = Harness(Broken())
    with pytest.raises(ProviderError, match="three attempts") as failure:
        h.ask("define_economy", "Define economy", {})
    assert "Call exactly the offered tool once" in str(failure.value)
    assert h.calls == 3
    with pytest.raises(ProviderError, match="budget"):
        Harness(Broken(), max_calls=0).interpret(ingest("fixtures/books/fantasy.txt"))


def test_cache_does_not_store_prompts_and_tracks_usage(spec, tmp_path):
    p = FixtureToolProvider(spec); cache = CachedProvider(p, tmp_path)
    tool = Tool("define_economy", "economy", TOOL_MODELS["define_economy"].model_json_schema())
    cache.complete("System", "private-source-sentinel", [tool]); cache.complete("System", "private-source-sentinel", [tool])
    assert len(p.requests) == 1
    assert cache.usage.requests == 1 and cache.usage.cache_hits == 1
    assert cache.usage.input_tokens == 100
    assert "private-source-sentinel" not in next(tmp_path.glob("*.json")).read_text()


def test_originality_rejects_trivial_names_and_copied_dialogue(fantasy_data, tmp_path):
    p = tmp_path / "book.txt"; p.write_text("Captain Geralt hunted monsters. Geralt crossed Rivia and spoke. The harbor keeper asked him to carry the ancient ledger back before the flood returned.")
    fantasy_data["metadata"]["adaptation"] = {"mode": "original_inspiration"}
    fantasy_data["player"]["name"] = "Geralto"
    fantasy_data["dialogues"][0]["nodes"][0]["text"] = "The harbor keeper asked him to carry the ancient ledger back before the flood returned."
    issues = originality_issues(RealmSpec.model_validate(fantasy_data), ingest(p))
    assert {"source_name_reuse", "copied_prose"} <= {i.code for i in issues}


@pytest.mark.parametrize("dialect", ["ollama", "compatible"])
def test_http_adapter_wire_protocol_and_usage(dialect):
    captured = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"]))); captured.append((self.path, data))
            call = {"function": {"name": "define_economy", "arguments": {"currency_name": "credits"}}}
            if dialect == "compatible": call["function"]["arguments"] = json.dumps(call["function"]["arguments"])
            response = {"message": {"tool_calls": [call]}, "prompt_eval_count": 23, "eval_count": 7} if dialect == "ollama" else {"choices": [{"message": {"tool_calls": [call]}}], "usage": {"prompt_tokens": 23, "completion_tokens": 7}}
            raw = json.dumps(response).encode(); self.send_response(200); self.end_headers(); self.wfile.write(raw)
        def log_message(self, *args): pass
    server = HTTPServer(("127.0.0.1", 0), Handler); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        p = HTTPProvider(f"http://127.0.0.1:{server.server_port}", "test-model", dialect=dialect, input_price_per_million=1, output_price_per_million=2)
        response = p.complete("system", "prompt", [Tool("define_economy", "economy", TOOL_MODELS["define_economy"].model_json_schema())])
        assert response.calls[0].arguments == {"currency_name": "credits"}
        assert response.usage.input_tokens == 23 and response.usage.output_tokens == 7
        assert response.usage.estimated_cost == pytest.approx(0.000037)
        assert captured[0][0] == ("/api/chat" if dialect == "ollama" else "/v1/chat/completions")
        assert captured[0][1]["stream"] is False
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_endpoint_identity_never_includes_credentials():
    for url in ["https://user:secret@host", "https://host?key=secret", "file:///etc/passwd"]:
        with pytest.raises(ValueError): HTTPProvider(url, "model")


@pytest.mark.parametrize("dialect", ["ollama", "compatible"])
@pytest.mark.parametrize("failure", ["http_503", "disconnect"])
def test_transient_http_retry_and_optional_stream(dialect, failure, monkeypatch):
    captured = []
    monkeypatch.setattr("inkbound.authoring.providers.time.sleep", lambda _: None)
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"]))); captured.append(data)
            if len(captured) == 1:
                if failure == "disconnect":
                    self.close_connection = True; return
                self.send_response(503); self.end_headers(); return
            self.send_response(200); self.end_headers()
            if data["stream"]:
                assert not data.get("tools") and "tool_choice" not in data
                for word in ("reading ", "complete"):
                    value = {"message": {"content": word}} if dialect == "ollama" else {"choices": [{"delta": {"content": word}}]}
                    self.wfile.write((("" if dialect == "ollama" else "data: ") + json.dumps(value) + "\n\n").encode())
                if dialect == "compatible": self.wfile.write(b"data: [DONE]\n\n")
            else:
                call = {"function": {"name": "define_economy", "arguments": "{}" if dialect == "compatible" else {}}}
                value = {"message": {"tool_calls": [call]}} if dialect == "ollama" else {"choices": [{"message": {"tool_calls": [call]}}]}
                self.wfile.write(json.dumps(value).encode())
        def log_message(self, *args): pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        provider = HTTPProvider(f"http://127.0.0.1:{server.server_port}", "test", dialect=dialect)
        assert provider.complete("system", "prompt", []).calls[0].arguments == {}
        assert len(captured) == 2
        assert "".join(provider.stream_text("system", "read")) == "reading complete"
    finally:
        server.shutdown(); thread.join(); server.server_close()
