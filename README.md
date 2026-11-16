# Context Mapper

Builds a context map: an interactive page plus static Mermaid diagrams of your domains, bounded contexts, and the dependencies between them, from two YAML files. `context-map.yml` says what the map describes; `context-map.style.yml` says how it looks.

[![Interactive context map](docs/screenshot.png)](https://henriquemoody.github.io/context-mapper/)

The interactive page built from the [`example/`](example/) model, published by GitHub Actions — click the picture, or go straight to <https://henriquemoody.github.io/context-mapper/>.

The build fails on unknown ids, duplicates, dependency cycles between bounded contexts, and unknown or invalid `context-map.style.yml` options, so a bad change breaks the build instead of the picture. It warns when two domains depend on each other.

- `src/context_mapper/build.py` validates the model and builds everything.
- `src/context_mapper/graph.py` holds the model logic: levels, lifting context dependencies to domains, and the focus walk.
- `src/context_mapper/mermaid.py` turns views into Mermaid.
- `src/context_mapper/template/` is the interactive page: `index.html`, `style.css` and `app.js`, spliced into one file when it builds.
- `example/` is a small working model you can build right away.

## Install

Requires Python 3.9+; Mermaid itself is loaded from a CDN when you view a page, so the only build dependency is PyYAML.

```sh
pip install git+https://github.com/henriquemoody/context-mapper.git
```

Pin a tag (as above) or a branch, so a change here cannot break your build unannounced.

Run `context-mapper` in a directory that has a `context-map.yml` and a `context-map.style.yml`. The paths are flags:

```sh
context-mapper --model context-map.yml --diagrams context-map.style.yml --out public
```

## The model

```yaml
types:
  core:       { name: Core }                     # the colors live in context-map.style.yml
  supporting: { name: Supporting }
  generic:    { name: Generic }

clusters:                                         # a set of domains or contexts treated together
  foundations: { name: Shared Foundations }

context-map:                                      # every id is a key, exactly once
  payments:                                       # no `domain:` key: a domain
    name: Payments
    type: generic
    cluster: foundations                          # a member of the foundations cluster
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
    description: Takes a cart and turns it into a paid order.   # shows as a tooltip on the box
  fulfillment:
    name: Fulfillment
    domain: orders
    type: supporting                              # a context can override its domain's type
```

Three kinds of thing, in three sections. `types` is the role vocabulary of the model: a domain or bounded context has one. `clusters` names a set of domains or contexts treated together; members join with `cluster:`, and nothing can depend on a cluster. In `context-map`, an entry with a `domain:` key is a bounded context, and any other entry is a domain — one no context points at is a single bounded context. How anything first renders comes from `defaultDisplay` in the style file: a domain or a cluster takes `expanded` (the box and what it holds), `collapsed` (the box alone), `contents` (what it holds, no box), or `hidden` (neither). A bounded context — one box with nothing inside, and a domain no context points at is one too — takes only `expanded` or `hidden`; writing `collapsed` or `contents` for one fails the build, saying why.

Every entry can carry a `description`: the interactive page shows it as a tooltip when you hover over its box, and the item's page shows it under the title.

A domain no context points at is a single bounded context with the same name.

At domain level, context dependencies are lifted to their domains and merged, and dependencies inside a domain disappear.

## What gets built

| Output | What it is |
| --- | --- |
| `<out>/index.html` | Interactive view. Switch between bounded contexts and domains, click anything to focus on it, hide anything from the side panel, hover a box or an arrow for the details. |
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

`context-map.style.yml` holds all of it. Its sections mirror the model's — `types`, `clusters`, `context-map` — keyed by the same ids, and take Mermaid's own classDef attributes as keys (`fill`, `stroke`, `stroke-width`, ...), so what you write is what Mermaid draws: a domain's entry styles the box around its bounded contexts, a bounded context's entry styles its own box. Any entry also takes `defaultDisplay`, saying how it first renders — a bounded context hidden that way is hidden like `hide` hides it, everywhere except its own page. The build fails if one points at an id that doesn't exist, on an attribute Mermaid doesn't know, or on a type without `fill` and `stroke`.

```yaml
types:
  core: { fill: "#dedaff", stroke: "#6631d7" }                       # types need fill and stroke

clusters:
  foundations: { fill: "#eaf9ef", stroke: "#067429", stroke-dasharray: "4 3", defaultDisplay: collapsed }

context-map:
  orders: { fill: "#eef4ff", stroke: "#305bab" }                    # overrides mermaid.domain_style
  checkout: { fill: "#fff4f4", defaultDisplay: hidden }             # a bounded context styles its own box, and can start hidden
```

A style also fills in a readable text `color` when you don't set one.

The rest lives in the `mermaid` section. Every style in it is a map of the same Mermaid attributes as above, so `focus_style`, `domain_style` and `edge_styles` read like `types`, `clusters` and `context-map`. It styles the interactive page (`index.html`) and the static pages alike, since both are drawn with Mermaid. The interactive page uses the view `defaults` (such as `display` and `hide`) as its starting state. Unknown keys fail the build, so a typo tells you instead of doing nothing.

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
| `focus_style` | map of Mermaid attributes | How the focused item is highlighted. |
| `domain_style` | map of Mermaid attributes | Style of the box around a domain's bounded contexts. A domain with its own style under `context-map` overrides it — and its type colors, when drawn as one box. |
| `edge_styles.solid`, `edge_styles.dotted` | map of Mermaid attributes | Line styles. Dotted comes from `style: dotted` on a downstream. |
| `pages` | `all`, `domains`, `contexts`, or a list of ids | Which items get their own page. |

These can be set under `defaults` and overridden per view:

| Option | Values | What it does |
| --- | --- | --- |
| `level` | `context`, `domain` | Bounded contexts inside domain boxes, or one box per domain. |
| `depth` | number, `99` for all | Hops out from the focus. |
| `dir` | `both`, `up`, `down` | Depends on, used by, or both. |
| `display` | `expanded`, `collapsed`, `contents`, `hidden`, or a map from container id to one of those | How containers first render. A single value applies to every container; a map leaves the rest to their own `defaultDisplay` in the style file. |
| `hide` | a list of ids | What the view never draws, no matter what: hiding a domain or a cluster takes everything inside it, hiding a bounded context only its own box and arrows. In the whole system that trims domains and clusters; in a domain's view it leaves out bounded contexts; in a cluster's view, members. The focus itself is never hidden. |
| `child_labels` | `true`, `false` | A collapsed container names what it holds, in the box and on each arrow that reaches it. |
| `group_by_type` | `true`, `false` | Wrap Core, Supporting and Generic in their own boxes. |

A view can also set `id`, `title`, `focus` (a domain, context or cluster id), `description` and `direction`:

```yaml
    - id: catalog-detail
      title: Catalog in detail
      focus: catalog
      display: contents                # or { foundations: contents }
      hide: [search]                   # never draw the Search context here
      direction: LR
```

## Use it in another repository

Keep only the model in your repository and let CI install this tool. Pin a tag so the build is reproducible; when you want a newer version, bump the tag. This GitLab Pages job is all it takes (the GitHub tag tarball works everywhere, and needs no `git` in the image):

```yaml
pages:
  image: python:3.12-slim
  script:
    - pip install --quiet https://github.com/henriquemoody/context-mapper/archive/refs/tags/v0.19.0.tar.gz
    - context-mapper
  artifacts:
    paths:
      - public
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

## Links

- `index.html#focus=checkout`: interactive, Checkout and its direct neighbors
- `index.html#focus=foundations`: interactive, the foundations cluster, opened, and what its members touch
- `index.html#level=domain&focus=orders`: interactive, the Orders domain and its neighbors
- `index.html#focus=orders&hide.fulfillment=1`: interactive, the Orders domain without the Fulfillment context
- Other hash options: `depth=1|2|99`, `dir=both|up|down`, `display.<domain id>=expanded|collapsed|contents|hidden`, `hide.<id>=1|0`
- `mermaid/checkout.html`: static diagram for Checkout
- `mermaid/index.html`: all static diagrams
