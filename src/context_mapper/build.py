"""Build the context map from a model file (what it describes) and a style file (how it looks).

Writes an interactive page (index.html), one static Mermaid page per view
(mermaid/*.html) and the same diagrams as Markdown (markdown/*.md), all under
the output directory.

Fails (exit 1) on unknown ids, duplicates, dependency cycles between bounded
contexts, and unknown or invalid Mermaid options, so a bad change breaks the
pipeline instead of the picture.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

from . import graph
from . import mermaid

TEMPLATE = Path(__file__).parent / "template.html"
DIAGRAMS_KEYS = {"types", "groups", "domains", "mermaid"}


class StrictLoader(yaml.SafeLoader):
    """A SafeLoader that refuses duplicate keys, which would otherwise silently overwrite each other."""


def _construct_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark,
                f"found duplicate key {key!r}", key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def read_yaml(path):
    try:
        return yaml.load(path.read_text(), Loader=StrictLoader)
    except yaml.YAMLError as err:
        sys.exit(f"error: {path}: {err}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="context-mapper",
        description="Build a context map site from a model file (what it describes) "
                    "and a style file (how it looks).")
    parser.add_argument("--model", type=Path, default=Path("context-map.yml"),
                        help="the model file (default: %(default)s)")
    parser.add_argument("--diagrams", type=Path, default=Path("context-map.style.yml"),
                        help="the style file (default: %(default)s)")
    parser.add_argument("--out", type=Path, default=Path("public"),
                        help="the directory to build into (default: %(default)s)")
    return parser.parse_args(argv)


def load(model_path, diagrams_path):
    model = read_yaml(model_path)
    diagrams = read_yaml(diagrams_path) or {}
    data, errors = graph.normalize(model, diagrams)

    for key in diagrams:
        if key not in DIAGRAMS_KEYS:
            errors.append(f"context-map.style.yml: {key}: unknown section. Known: {', '.join(sorted(DIAGRAMS_KEYS))}")

    mermaid_cfg, mermaid_errors = mermaid.settings(diagrams.get("mermaid"))
    errors += mermaid_errors

    if not errors:
        errors += mermaid.check(data, mermaid_cfg)

    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        sys.exit(1)

    # Contexts may depend on each other across domains in both directions without
    # forming a context cycle. At domain level that is still worth knowing about.
    cycle = graph.find_cycle(graph.level_graph(data, "domain"))
    if cycle:
        _, _, _, names = graph.index(data)
        print("warning: domains depend on each other: " + " -> ".join(names[i] for i in cycle), file=sys.stderr)

    return data, diagrams.get("mermaid")


def main(argv=None):
    args = parse_args(argv)
    for flag, path in (("--model", args.model), ("--diagrams", args.diagrams)):
        if not path.exists():
            sys.exit(f"error: {path} not found. Pass {flag} to set the path.")
    data, mermaid_config = load(args.model, args.diagrams)
    cfg, _ = mermaid.settings(mermaid_config)
    payload = json.dumps({**data, "mermaid": mermaid.client_settings(cfg)}, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("/*__MODEL__*/null", payload)
    index = args.out / "index.html"
    args.out.mkdir(parents=True, exist_ok=True)
    index.write_text(html)
    print(f"built {index}: {len(data['domains'])} domains, "
          f"{len(data['contexts'])} bounded contexts, {len(data['edges'])} dependencies")
    count = mermaid.build(data, mermaid_config, args.out)
    print(f"built {count} Mermaid views in {args.out}/mermaid/ and {args.out}/markdown/")


if __name__ == "__main__":
    main()
