# Context Mapper

Builds a context map: an interactive page plus static Mermaid diagrams of your domains, bounded contexts, and the dependencies between them, from two YAML files. `context-map.yml` says what the map describes; `diagrams.yml` says how it looks.

The build fails on unknown ids, duplicates, dependency cycles between bounded contexts, and unknown or invalid `diagrams.yml` options, so a bad change breaks the build instead of the picture. It warns when two domains depend on each other.

- `src/context_mapper/build.py` validates the model and builds everything.
- `src/context_mapper/graph.py` holds the model logic: levels, lifting context dependencies to domains, and the focus walk.
- `src/context_mapper/mermaid.py` turns views into Mermaid.
- `src/context_mapper/template.html` is the interactive page.
- `example/` is a small working model you can build right away.

## Install

Requires Python 3.9+; Mermaid itself is loaded from a CDN when you view a page, so the only build dependency is PyYAML.

```sh
pip install git+https://github.com/henriquemoody/context-mapper.git@v0.2.0
```

Pin a tag (as above) or a branch, so a change here cannot break your build unannounced.

Run `context-mapper` in a directory that has a `context-map.yml` and a `diagrams.yml`. The paths are flags:

```sh
context-mapper --model context-map.yml --diagrams diagrams.yml --out public
```

## The model

```yaml
types:
  core: { label: Core }                                       # the colors live in diagrams.yml

groups:
  - { id: foundations, name: Shared Foundations }             # views can show, hide or fold a group into one box

domains:
  - { id: legal, name: Legal Agreements, type: supporting, group: foundations }  # one bounded context, same name
  - id: business
    name: Business
    type: supporting                                          # contexts inherit type and group
    contexts:
      - { id: registry, name: Business Registry }
      - { id: reviews,  name: Reviews, type: core }           # a context can override its type

dependencies:
  - { upstream: legal, downstream: [registry, reviews] }      # registry and reviews depend on legal
  - upstream: marketplace
    downstream:
      - { id: crm, comment: Reads leads to sync them }   # a comment shows as a tooltip when you hover over the arrow
```

A group is any set of domains or contexts you want to treat together, such as shared foundations. A context takes its domain's `group` unless it sets its own.

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

`diagrams.yml` holds all of it. Type and group styles are keyed by the ids in `context-map.yml`, and the build fails if one points at an id that doesn't exist or a type has no colors.

```yaml
types:
  core: { color: "#dedaff", border: "#6631d7" }               # or mermaid_style, a CSS-ish string

groups:
  foundations: { mermaid_style: "fill:#eaf9ef,stroke:#067429" }  # style of the group's box
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
| `domain_style` | CSS-ish string | Style of the box around a domain's bounded contexts. |
| `edge_styles.solid`, `edge_styles.dotted` | CSS-ish string | Line styles. Dotted comes from `style: dotted` on a dependency. |
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
    - id: marketplace-detail
      title: Leads Marketplace in detail
      focus: marketplace
      groups: show                       # or { foundations: show }
      direction: LR
```

## Use it in another repository

Keep only the model in your repository and let CI install this tool. Pin a tag so the build is reproducible; when you want a newer version, bump the tag. This GitLab Pages job is all it takes (the GitHub tag tarball works everywhere, and needs no `git` in the image):

```yaml
pages:
  image: python:3.12-slim
  script:
    - pip install --quiet https://github.com/henriquemoody/context-mapper/archive/refs/tags/v0.2.0.tar.gz
    - context-mapper
  artifacts:
    paths:
      - public
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

## Links

- `index.html#focus=reviews`: interactive, Reviews and its direct neighbors
- `index.html#level=domain&focus=business`: interactive, the Business domain and its neighbors
- Other hash options: `depth=1|2|99`, `dir=both|up|down`, `group.<group id>=collapse|show|hide`
- `mermaid/reviews.html`: static diagram for Reviews
- `mermaid/index.html`: all static diagrams
