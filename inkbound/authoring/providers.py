"""Provider-neutral tool responses plus Ollama and compatible HTTP adapters."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Protocol
from urllib.parse import urlparse

from inkbound.realm.package import canonical


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    schema: dict

    def wire(self):
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.schema}}


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    requests: int = 0
    cache_hits: int = 0
    estimated_cost: float | None = None


@dataclass
class Response:
    calls: list[ToolCall]
    text: str = ""
    usage: Usage = field(default_factory=Usage)


class Provider(Protocol):
    identity: str

    def complete(self, system: str, prompt: str, tools: list[Tool]) -> Response: ...


class ProviderError(RuntimeError):
    pass


def decode_response(message, usage):
    calls = []
    for call in message.get("tool_calls", []):
        function = call["function"]; args = function["arguments"]
        args = json.loads(args) if isinstance(args, str) else args
        if not isinstance(args, dict): raise ProviderError("Tool arguments must be objects")
        calls.append(ToolCall(function["name"], args))
    return Response(calls, message.get("content") or "", usage)


class HTTPProvider:
    """Configure any local or remote server exposing one of these two dialects.

    Credentials are supplied by environment, never written to cache or packages.
    Ollama /api/chat and llama.cpp /v1/chat/completions are the tested protocols.
    """
    def __init__(self, endpoint: str, model: str, *, dialect="ollama", api_key_env="INKBOUND_API_KEY",
                 timeout=180, retries=2, input_price_per_million: float | None = None, output_price_per_million: float | None = None):
        parsed = urlparse(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Provider endpoint must be an HTTP(S) URL without embedded credentials")
        if dialect not in ("ollama", "compatible"):
            raise ValueError("Unknown provider dialect")
        self.endpoint = endpoint.rstrip("/")
        self.model = model; self.dialect = dialect; self.api_key_env = api_key_env
        self.timeout = timeout; self.retries = retries
        self.identity = f"{dialect}:{self.endpoint}:{model}"
        self.input_price = input_price_per_million; self.output_price = output_price_per_million

    def _request(self, system, prompt, tools, stream=False):
        data = {"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "tools": [t.wire() for t in tools], "stream": stream}
        if self.dialect == "ollama":
            data["options"] = {"temperature": 0.35, "seed": 42, "num_ctx": 32768}
            route = "/api/chat"
        else:
            data.update(temperature=0.35, tool_choice="required")
            if stream: data["stream_options"] = {"include_usage": True}
            route = "/chat/completions" if self.endpoint.endswith("/v1") else "/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(self.api_key_env)
        if key: headers["Authorization"] = "Bearer " + key
        return urllib.request.Request(self.endpoint + route, data=canonical(data), headers=headers)

    def _usage(self, data):
        raw = data.get("usage", {})
        incoming = int(data.get("prompt_eval_count", raw.get("prompt_tokens", 0)))
        outgoing = int(data.get("eval_count", raw.get("completion_tokens", 0)))
        cached = int(data.get("prompt_eval_cached_count", raw.get("prompt_tokens_details", {}).get("cached_tokens", 0)))
        cost = None if self.input_price is None or self.output_price is None else (incoming * self.input_price + outgoing * self.output_price) / 1000000
        return Usage(incoming, outgoing, cached, requests=1, estimated_cost=cost)

    def complete(self, system, prompt, tools):
        request = self._request(system, prompt, tools)
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read(8 * 1024 * 1024 + 1)
                    if len(raw) > 8 * 1024 * 1024: raise ProviderError("Provider response too large")
                    data = json.loads(raw)
                message = data.get("message") if self.dialect == "ollama" else data["choices"][0]["message"]
                return decode_response(message, self._usage(data))
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise ProviderError(f"Provider HTTP {exc.code}; verify endpoint/model/authentication") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt == self.retries: raise ProviderError(f"Provider unavailable: {type(exc).__name__}") from None
            except (KeyError, TypeError, ValueError) as exc:
                raise ProviderError(f"Malformed provider response: {type(exc).__name__}") from None
            time.sleep(min(2**attempt, 4))

    def stream_text(self, system: str, prompt: str) -> Iterator[str]:
        """Optional progress/prose streaming; compiled structures use atomic calls.

        Not used for gameplay and never treats unfinished text as realm data.
        """
        request = self._request(system, prompt, [], stream=True)
        if self.dialect == "compatible":
            data = json.loads(request.data); data.pop("tool_choice", None); data.pop("tools", None)
            request.data = canonical(data)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                for raw in response:
                    line = raw.decode().strip()
                    if self.dialect == "compatible":
                        if not line.startswith("data:"): continue
                        line = line[5:].strip()
                        if line == "[DONE]": break
                    if not line: continue
                    data = json.loads(line)
                    if self.dialect == "ollama":
                        content = data.get("message", {}).get("content", "")
                    else:
                        choices = data.get("choices", []); content = choices[0].get("delta", {}).get("content", "") if choices else ""
                    if content: yield content
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise ProviderError(f"Provider stream failed: {type(exc).__name__}") from None


class OMPProvider:
    """Use the installed OMP harness and its login without exporting credentials."""

    def __init__(self, model: str, *, executable="omp", timeout=180, retries=2):
        self.model = model; self.executable = executable
        self.timeout = timeout; self.retries = retries
        self.identity = f"omp:{model}"
        self.accounting = HTTPProvider("http://localhost", model, dialect="compatible")

    def complete(self, system, prompt, tools):
        request = {"id": "inkbound", "path": "/v1/chat/completions", "body": {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "tools": [tool.wire() for tool in tools], "tool_choice": "required",
            "temperature": 0.35, "reasoning_effort": "medium", "stream": False}}
        for attempt in range(self.retries + 1):
            try:
                process = subprocess.run([self.executable, "auth-gateway", "stdio"],
                                         input=canonical(request).decode() + "\n", text=True,
                                         capture_output=True, timeout=self.timeout)
                if process.returncode:
                    raise ProviderError("OMP gateway failed; verify the installed CLI and OMP authentication")
                if len(process.stdout.encode()) > 8 * 1024 * 1024:
                    raise ProviderError("OMP response too large")
                envelopes = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
                envelope = next(e for e in envelopes if e.get("id") == "inkbound")
                status = envelope["status"]
                if status != 200:
                    if status in (429, 500, 502, 503, 504) and attempt < self.retries:
                        time.sleep(min(2**attempt, 4)); continue
                    raise ProviderError(f"OMP gateway HTTP {status}; verify model and OMP authentication")
                data = envelope["body"]
                return decode_response(data["choices"][0]["message"], self.accounting._usage(data))
            except subprocess.TimeoutExpired:
                if attempt == self.retries: raise ProviderError("OMP request timed out") from None
            except OSError:
                raise ProviderError("OMP CLI is unavailable; install and authenticate OMP") from None
            except (KeyError, TypeError, ValueError, IndexError, AttributeError, StopIteration) as exc:
                raise ProviderError(f"Malformed OMP response: {type(exc).__name__}") from None
            time.sleep(min(2**attempt, 4))


class CachedProvider:
    def __init__(self, provider: Provider, directory: str | Path, *, notify: Callable[[str], None] | None = None):
        self.provider = provider; self.identity = provider.identity; self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True); self.usage = Usage(); self.notify = notify

    def complete(self, system, prompt, tools):
        key = hashlib.sha256(canonical({"protocol": 1, "provider": self.identity, "system": system, "prompt": prompt,
                                        "tools": [t.wire() for t in tools]})).hexdigest()
        path = self.directory / (key + ".json")
        if path.exists():
            data = json.loads(path.read_text())
            response = Response([ToolCall(**c) for c in data["calls"]], data["text"], Usage(cache_hits=1))
        else:
            response = self.provider.complete(system, prompt, tools)
            # Cache results, never the source text or request, and never credentials.
            data = {"calls": [c.__dict__ for c in response.calls], "text": response.text}
            stage = path.with_suffix(f".{os.getpid()}.tmp")
            stage.write_bytes(canonical(data)); os.replace(stage, path)
        for key2 in ("input_tokens", "output_tokens", "cached_tokens", "requests", "cache_hits"):
            setattr(self.usage, key2, getattr(self.usage, key2) + getattr(response.usage, key2))
        if response.usage.estimated_cost is not None:
            self.usage.estimated_cost = (self.usage.estimated_cost or 0) + response.usage.estimated_cost
        if self.notify: self.notify(f"Authorship: {self.usage.requests} model calls, {self.usage.cache_hits} cached results")
        return response
