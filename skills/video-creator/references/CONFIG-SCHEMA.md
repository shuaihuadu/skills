# video-config.json Schema Reference

This document describes every field in the video configuration file.

## Top-Level Fields

| Field           | Type   | Required | Default                     | Description                    |
| --------------- | ------ | -------- | --------------------------- | ------------------------------ |
| `title`         | string | Yes      | —                           | Video title (used in metadata) |
| `language`      | string | No       | `"zh-CN"`                   | BCP 47 language tag            |
| `voice`         | string | No       | `"zh-CN-YunxiNeural"`       | edge-tts voice name            |
| `voiceRate`     | string | No       | `"-5%"`                     | Speech rate adjustment         |
| `voiceVolume`   | string | No       | `"+0%"`                     | Volume adjustment              |
| `theme`         | string | No       | `"dark-tech"`               | Visual theme name              |
| `resolution`    | object | No       | `{width:1920, height:1080}` | Video resolution               |
| `particleCount` | number | No       | `60`                        | Background particle count      |
| `scenes`        | array  | Yes      | —                           | Array of scene objects         |

### Common Voices

| Language | Voice                  | Description     |
| -------- | ---------------------- | --------------- |
| Chinese  | `zh-CN-YunxiNeural`    | Male, natural   |
| Chinese  | `zh-CN-XiaoxiaoNeural` | Female, natural |
| English  | `en-US-GuyNeural`      | Male, natural   |
| English  | `en-US-JennyNeural`    | Female, natural |

## Scene Object (Common Fields)

Every scene has these fields:

| Field       | Type   | Required | Description                              |
| ----------- | ------ | -------- | ---------------------------------------- |
| `type`      | string | Yes      | Scene type (see below)                   |
| `narration` | string | Yes      | TTS narration text for this scene        |
| `duration`  | number | Yes      | Scene display duration in milliseconds   |
| `heading`   | string | No       | Scene heading text (most types use this) |

## Scene Types

### `title`

Opening/title card scene.

| Field      | Type   | Required | Description                                |
| ---------- | ------ | -------- | ------------------------------------------ |
| `heading`  | string | Yes      | Main title text                            |
| `subtitle` | string | No       | Tagline below title                        |
| `badge`    | string | No       | Version badge text (e.g., "v1.0 · Python") |
| `icon`     | string | No       | Emoji or icon above title                  |

### `info-box`

Information display with description, badges, and optional statistics.

| Field           | Type     | Required | Description                                                 |
| --------------- | -------- | -------- | ----------------------------------------------------------- |
| `heading`       | string   | Yes      | Section heading                                             |
| `description`   | string   | Yes      | Rich text description (supports `<span class="highlight">`) |
| `icon`          | string   | No       | Large icon/emoji                                            |
| `badges`        | string[] | No       | Technology badges shown below description                   |
| `stats`         | object[] | No       | Counter statistics                                          |
| `stats[].value` | number   | Yes      | Target number for animated counter                          |
| `stats[].label` | string   | Yes      | Label below the counter                                     |

### `orbit-diagram`

Architecture diagram with a central node and orbiting nodes.

| Field                | Type     | Required | Description                 |
| -------------------- | -------- | -------- | --------------------------- |
| `heading`            | string   | Yes      | Section heading             |
| `centerNode`         | object   | Yes      | Central node                |
| `centerNode.icon`    | string   | Yes      | Emoji icon                  |
| `centerNode.label`   | string   | Yes      | Node label                  |
| `centerNode.desc`    | string   | No       | Short description           |
| `orbitNodes`         | object[] | Yes      | Array of 3-6 orbiting nodes |
| `orbitNodes[].icon`  | string   | Yes      | Emoji icon                  |
| `orbitNodes[].label` | string   | Yes      | Node label                  |
| `orbitNodes[].desc`  | string   | No       | Short description           |

### `workflow`

Horizontal workflow/flowchart with optional fork-merge.

| Field           | Type     | Required | Description                                                      |
| --------------- | -------- | -------- | ---------------------------------------------------------------- |
| `heading`       | string   | Yes      | Section heading                                                  |
| `steps`         | object[] | Yes      | 2-6 workflow step nodes                                          |
| `steps[].icon`  | string   | Yes      | Emoji icon                                                       |
| `steps[].label` | string   | Yes      | Step label                                                       |
| `forkAfter`     | number   | No       | Index (0-based) after which to fork into 2 parallel branches     |
| `forkNodes`     | object[] | No       | 2 parallel nodes shown during fork (required if `forkAfter` set) |
| `pills`         | string[] | No       | Feature tags shown below the workflow                            |

When `forkAfter` is set, the workflow renders as:
```
[step 0] → [step 1] → ... → [step forkAfter] → fork → [forkNode A] → merge → [remaining steps] → ...
                                                      → [forkNode B] ↗
```

### `feature-grid`

Grid of feature cards. Best with 3-4 items.

| Field              | Type     | Required | Description                                    |
| ------------------ | -------- | -------- | ---------------------------------------------- |
| `heading`          | string   | Yes      | Section heading                                |
| `features`         | object[] | Yes      | Array of feature cards                         |
| `features[].icon`  | string   | Yes      | Large emoji                                    |
| `features[].title` | string   | Yes      | Feature title                                  |
| `features[].desc`  | string   | Yes      | Feature description (use `\n` for line breaks) |

### `code-demo`

Animated code typing demonstration.

| Field                        | Type     | Required | Description                                              |
| ---------------------------- | -------- | -------- | -------------------------------------------------------- |
| `heading`                    | string   | Yes      | Section heading                                          |
| `filename`                   | string   | Yes      | Filename displayed in code window title bar              |
| `codeLines`                  | object[] | Yes      | Array of code lines                                      |
| `codeLines[].tokens`         | object[] | Yes      | Tokens in this line (empty array = blank line)           |
| `codeLines[].tokens[].text`  | string   | Yes      | Token text                                               |
| `codeLines[].tokens[].style` | string   | Yes      | CSS class: `kw`, `fn`, `str`, `cm`, `op`, `var`, or `""` |
| `installHint`                | string   | No       | Install command shown below code window                  |

### `closing`

Closing/CTA scene.

| Field          | Type     | Required | Description                      |
| -------------- | -------- | -------- | -------------------------------- |
| `heading`      | string   | Yes      | Closing title text               |
| `icon`         | string   | No       | Icon above heading               |
| `links`        | object[] | No       | Resource links                   |
| `links[].icon` | string   | Yes      | Link icon                        |
| `links[].text` | string   | Yes      | Link text                        |
| `tagline`      | string   | No       | Final tagline (e.g., star count) |
