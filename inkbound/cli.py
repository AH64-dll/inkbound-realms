"""Author a realm once, then explore its persistent package offline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from inkbound.realm.models import RealmSpec
from inkbound.realm.package import RealmPackage
from inkbound.realm.validation import validate_realm


def read_realm(path):
    path = Path(path)
    return RealmPackage.load(path) if path.is_dir() else RealmPackage(RealmSpec.model_validate_json(path.read_bytes()))


def main():
    parser = argparse.ArgumentParser(description="Inkbound Realms — worlds authored from literature")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate a RealmSpec or compiled package")
    validate.add_argument("realm")
    package = commands.add_parser("package", help="Compile a validated spec into a persistent offline package")
    package.add_argument("realm"); package.add_argument("destination"); package.add_argument("--assets")
    play = commands.add_parser("play", help="Explore a compiled realm or an offline fixture")
    play.add_argument("realm"); play.add_argument("--save"); play.add_argument("--load", action="store_true")
    play.add_argument("--ascii", action="store_true"); play.add_argument("--frames", type=int); play.add_argument("--capture")
    legacy = commands.add_parser("legacy", help="Run the preserved original game")
    legacy.add_argument("args", nargs=argparse.REMAINDER)
    compile_command = commands.add_parser("compile", help="Interpret an entire book and author a validated realm")
    compile_command.add_argument("book"); compile_command.add_argument("destination"); compile_command.add_argument("--id", required=True)
    compile_command.add_argument("--seed", type=int, default=42)
    compile_command.add_argument("--adaptation", choices=["original_inspiration", "public_domain_adaptation", "licensed_adaptation"], default="original_inspiration")
    compile_command.add_argument("--rights-basis", default="")
    compile_command.add_argument("--allow-source-names", action="store_true")
    regenerate = commands.add_parser("regenerate", help="Revise selected content with stable IDs and full validation")
    regenerate.add_argument("realm"); regenerate.add_argument("destination"); regenerate.add_argument("--scope", required=True)
    regenerate.add_argument("--ids", nargs="+"); regenerate.add_argument("--instruction", required=True)
    regenerate.add_argument("--book", help="Original source for originality checks after regeneration")
    for command in (compile_command, regenerate):
        command.add_argument("--endpoint", required=True); command.add_argument("--model", required=True)
        command.add_argument("--dialect", choices=["ollama", "compatible"], default="ollama")
        command.add_argument("--cache", default=".cache/authoring"); command.add_argument("--max-calls", type=int, default=1000)
        command.add_argument("--timeout", type=float, default=180, help="Seconds per model request; increase for CPU inference")
    args = parser.parse_args()
    try:
        if args.command == "legacy":
            import subprocess, sys
            root = Path(__file__).resolve().parents[1] / "legacy/ascii_rpg"
            raise SystemExit(subprocess.call([sys.executable, "main.py", *args.args], cwd=root))
        if args.command in ("compile", "regenerate"):
            from inkbound.authoring.harness import Harness
            from inkbound.authoring.ingest import ingest
            from inkbound.authoring.providers import CachedProvider, HTTPProvider
            from inkbound.realm.models import AdaptationPolicy
            provider = CachedProvider(HTTPProvider(args.endpoint, args.model, dialect=args.dialect, timeout=args.timeout), args.cache)
            harness = Harness(provider, max_calls=args.max_calls, notify=print)
            if args.command == "compile":
                policy = AdaptationPolicy(mode=args.adaptation, rights_basis=args.rights_basis, allow_source_names=args.allow_source_names)
                realm = harness.compile(ingest(args.book), realm_id=args.id, seed=args.seed, adaptation=policy)
            else:
                original = read_realm(args.realm)
                spec = harness.regenerate(original.spec, args.scope, args.ids, args.instruction)
                spec = harness.review_and_revise(spec, ingest(args.book) if args.book else None)
                realm = RealmPackage(spec)
            destination = realm.write(args.destination, original.root if args.command == "regenerate" else None)
            # Trace records tool IDs and usage, not source text or model credentials.
            (destination / "authoring-report.json").write_text(json.dumps({"calls": harness.transcript, "usage": provider.usage.__dict__}, indent=2))
            print(destination)
            return
        realm = read_realm(args.realm)
        if args.command == "validate":
            issues = validate_realm(realm.spec)
            print(json.dumps({"realm": realm.spec.metadata.title, "valid": True, "issues": [i.__dict__ for i in issues]}, indent=2))
        elif args.command == "package":
            print(realm.write(args.destination, args.assets))
        elif args.command == "play":
            from inkbound.runtime.engine import Engine
            from inkbound.runtime.ui import App
            save = args.save or f"saves/{realm.spec.metadata.id}.json"
            engine = Engine.load(realm, save) if args.load else Engine(realm)
            app = App(engine, save)
            if args.ascii: app.ascii = True
            app.run(max_frames=args.frames, capture=args.capture)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, f"inkbound: {exc}\n")


if __name__ == "__main__":
    main()
