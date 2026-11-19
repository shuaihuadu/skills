# video-config.json Schema Reference

The portable contract is `title`, `voice`, and `scenes[].narration` / `duration` (milliseconds). Other fields may be consumed by the authored HTML; adding a field does not change the recorder. See [the HTML contract](HTML-CONTRACT.md).

## Top-Level Fields

| Field           | Type    | Required | Default               | Description                                                          |
| --------------- | ------- | -------- | --------------------- | -------------------------------------------------------------------- |
| `title`         | string  | Yes      | —                     | Video title (used in metadata)                                       |
| `language`      | string  | No       | `"zh-CN"`             | BCP 47 language tag                                                  |
| `voice`         | string  | No       | `"zh-CN-YunxiNeural"` | edge-tts voice name                                                  |
| `voiceRate`     | string  | No       | `"-5%"`               | Speech rate adjustment                                               |
| `voiceVolume`   | string  | No       | `"+0%"`               | Volume adjustment                                                    |
| `scenes`        | array   | Yes      | —                     | Array of scene objects                                               |
| `maxDurationMs` | integer | No       | No hard limit         | Positive upper bound for the sum of scene durations, in milliseconds |

### Common Voices

| Language | Voice                  | Description     |
| -------- | ---------------------- | --------------- |
| Chinese  | `zh-CN-YunxiNeural`    | Male, natural   |
| Chinese  | `zh-CN-XiaoxiaoNeural` | Female, natural |
| English  | `en-US-GuyNeural`      | Male, natural   |
| English  | `en-US-JennyNeural`    | Female, natural |

## Scene Object (Common Fields)

Only narration and duration are required for a scene. A scene is a timing interval, not a page or a required camera cut. The recorder has no built-in scene renderers.

| Field       | Type    | Required | Description                                     |
| ----------- | ------- | -------- | ----------------------------------------------- |
| `narration` | string  | Yes      | Text for TTS; empty or whitespace means silence |
| `duration`  | integer | Yes      | Positive scene duration in milliseconds         |

`build_video.py --check video-config.json` checks the timeline before animation work. Voiced scenes need a readable MP3 and a nonempty, valid SRT at the same scene index. Both must fit the shot. Silent scenes keep their index and full duration; any leftover voice assets for them are ignored. If a hard limit is exceeded, edit the script and regenerate rather than truncating audio.

## Optional author-defined cues

For a software demo, one voice segment can cover an edit and its consequence. This is one scene object, not a complete config:

```json
{
    "narration": "Watch the total when the quantity changes.",
    "duration": 6000,
    "actions": [
        { "atMs": 1000, "quantity": 1 },
        { "atMs": 3200, "quantity": 2 }
    ]
}
```

Only the authored HTML interprets `actions`: on the same receipt, change the quantity and recalculate the total. The recorder will not animate anything by itself. A filmed procedure or a held view of a painting may not need custom fields at all. Existing projects can keep their own `type`, `heading`, or other fields; no migration is needed.
