# Context Mapper

Builds a context map: an interactive page plus static Mermaid diagrams of your domains, bounded contexts, and the dependencies between them, from two YAML files. `context-map.yml` says what the map describes; `context-map.style.yml` says how it looks.

The build fails on unknown ids, duplicates, dependency cycles between bounded contexts, and unknown or invalid `context-map.style.yml` options, so a bad change breaks the build instead of the picture. It warns when two domains depend on each other.

- `src/context_mapper/build.py` validates the model and builds everything.
- `src/context_mapper/graph.py` holds the model logic: levels, lifting context dependencies to domains, and the focus walk.
- `src/context_mapper/mermaid.py` turns views into Mermaid.
- `src/context_mapper/template.html` is the interactive page.
- `example/` is a small working model you can build right away.

## Install

Requires Python 3.9+; Mermaid itself is loaded from a CDN when you view a page, so the only build dependency is PyYAML.

```sh
pip install git+https://github.com/henriquemoody/context-mapper.git@v0.8.0
```

Pin a tag (as above) or a branch, so a change here cannot break your build unannounced.

Run `context-mapper` in a directory that has a `context-map.yml` and a `context-map.style.yml`. The paths are flags:

```sh
context-mapper --model context-map.yml --diagrams context-map.style.yml --out public
```

## The model

```yaml
types:
  core:       { label: Core }                     # the colors live in context-map.style.yml
  supporting: { label: Supporting }
  generic:    { label: Generic }

groups:
  foundations: Shared Foundations                 # views can show, hide or fold a group into one box

context-map:                                      # every id is a key, exactly once
  payments:                                       # no `domain:` key: a domain
    name: Payments
    type: generic
    group: foundations
    downstreams:                                 # who depends on it, and why
      checkout: Charges the payment method and signals whether it went through.   # a tooltip on the arrow
      fulfillment:                               # a bare key: no comment yet
  catalog:                                       # a dependency can point at a whole domain
    name: Catalog
    type: core
    downstreams:
      checkout:
        comment: Reads prices and availability at checkout time.
        style: dotted                             # or a map, for a styled edge
  checkout:                                      # a `domain:` key makes an entry a bounded context
    name: Checkout
    domain: orders
  fulfillment:
    name: Fulfillment
    domain: orders
    type: supporting                              # a context can override its domain's type
```

A group is any set of domains or contexts you want to treat together, such as shared foundations. A context takes its domain's `group` unless it sets its own.

A domain no context points at is a single bounded context with the same name.

At domain level, context dependencies are lifted to their domains and merged, and dependencies inside a domain disappear.

## What gets built

| Output | What it is |
| --- | --- |
| `<out>/index.html` | Interactive view. Switch between bounded contexts and domains, click anything to focus on it. |
| `<out>/mermaid/*.html` | One static Mermaid page per domain, per bounded context, and per named view. Click a box to jump to its page. |
| `<out>/markdown/*.md` | The same diagrams as Markdown. GitLab renders them natively, and they can go to Confluence. |

## Run locally

```sh
git clone https://github.com/henriquemoody/context-mapper.git
cd context-mapper
pip install .
cd example
context-mapper
open public/index.html
```

## Customize the diagrams

`context-map.style.yml` holds all of it. Type, group and domain styles are keyed by the ids in `context-map.yml`, and the build fails if one points at an id that doesn't exist or a type has no colors.

```yaml
types:
  core: { color: "#dedaff", border: "#6631d7" }               # or mermaid_style, a CSS-ish string

groups:
  foundations: { mermaid_style: "fill:#eaf9ef,stroke:#067429" }  # style of the group's box

domains:
  orders: { color: "#eef4ff", border: "#305bab" }             # style of one domain's box
```

The rest lives in the `mermaid` section. It styles the interactive page (`index.html`) and the static pages alike, since both are drawn with Mermaid. The interactive page uses the view `defaults` (such as `groups`) as its starting state. Unknown keys fail the build, so a typo tells you instead of doing nothing.

| Option | Values | What it does |
| --- | --- | --- |
| `direction` | `BT`, `TB`, `LR`, `RL` | Flow direction. `BT` puts upstream on top. |
| `theme` | `base`, `default`, `neutral`, `dark`, `forest` | Mermaid theme. |
| `layout` | `dagre`, `elk` | Layout engine. The HTML pages load ELK when you pick it. |
| `look` | `classic`, `handDrawn` | Mermaid look. |
| `curve` | `basis`, `linear`, `step`, `stepBefore`, ... | Line shape. Set on every edge with `linkStyle ... interpolate`, so it works with any layout. |
| `theme_variables` | map | Passed to Mermaid as-is (fonts, colors). |
| `config` | map | Any other [Mermaid config](https://mermaid.js.org/config/schema-docs/config.html), merged over the above. For example `elk.nodePlacementStrategy`. |
| `markdown_config` | map | Merged over everything for `<out>/markdown/*.md` only. GitLab's built-in Mermaid has no ELK, so the example sets `layout: dagre` here. |
| `focus_style` | CSS-ish string | How the focused item is highlighted. |
| `domain_style` | CSS-ish string | Style of the box around a domain's bounded contexts. A domain with its own style under `domains` overrides it — and its type colors, when drawn as one box. |
| `edge_styles.solid`, `edge_styles.dotted` | CSS-ish string | Line styles. Dotted comes from `style: dotted` on a downstream. |
| `pages` | `all`, `domains`, `contexts`, or a list of ids | Which items get their own page. |

These can be set under `defaults` and overridden per view:

| Option | Values | What it does |
| --- | --- | --- |
| `level` | `context`, `domain` | Bounded contexts inside domain boxes, or one box per domain. |
| `depth` | number, `99` for all | Hops out from the focus. |
| `dir` | `both`, `up`, `down` | Depends on, used by, or both. |
| `groups` | `show`, `hide`, `collapse`, or a map from group id to one of those | Draw the members of a group, drop them, or fold them into one box per group. A single value applies to every group. In a map, groups left out are collapsed. |
| `group_labels` | `true`, `false` | With `collapse`, label each arrow with the members of the group it stands for. |
| `context_labels` | `true`, `false` | With `level: domain`, list the bounded contexts inside each domain box. |
| `group_by_type` | `true`, `false` | Wrap Core, Supporting and Generic in their own boxes. |

A view can also set `id`, `title`, `focus` (a domain or context id), `description` and `direction`:

```yaml
    - id: catalog-detail
      title: Catalog in detail
      focus: catalog
      groups: show                       # or { foundations: show }
      direction: LR
```

## Use it in another repository

Keep only the model in your repository and let CI install this tool. Pin a tag so the build is reproducible; when you want a newer version, bump the tag. This GitLab Pages job is all it takes (the GitHub tag tarball works everywhere, and needs no `git` in the image):

```yaml
pages:
  image: python:3.12-slim
  script:
    - pip install --quiet https://github.com/henriquemoody/context-mapper/archive/refs/tags/v0.8.0.tar.gz
    - context-mapper
  artifacts:
    paths:
      - public
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

## Links

- `index.html#focus=checkout`: interactive, Checkout and its direct neighbors
- `index.html#level=domain&focus=orders`: interactive, the Orders domain and its neighbors
- Other hash options: `depth=1|2|99`, `dir=both|up|down`, `group.<group id>=collapse|show|hide`
- `mermaid/checkout.html`: static diagram for Checkout
- `mermaid/index.html`: all static diagrams
