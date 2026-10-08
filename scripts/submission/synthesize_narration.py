"""Generate separate OpenAI narration clips; API credential remains in environment."""
import argparse
import json
import os
from pathlib import Path
import re
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, default=Path('submission/video-story-v2/真人旁白讲稿.md'))
    parser.add_argument('--output', type=Path, default=Path('.submission-build/openai-narration'))
    parser.add_argument('--voice', default='marin')
    args = parser.parse_args()
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        parser.error('OPENAI_API_KEY is not configured; no API call was made')
    clips = re.split(r'^## .*$', args.script.read_text(), flags=re.M)[1:]
    if not clips:
        parser.error('No narration segments found')
    args.output.mkdir(parents=True, exist_ok=True)
    for i, text in enumerate(clips):
        text = text.strip().replace('PR', '代码合并请求').replace('CI', '自动测试')
        body = json.dumps({'model': 'gpt-4o-mini-tts', 'voice': args.voice, 'input': text,
            'response_format': 'wav', 'instructions': '用自然的普通话介绍自己做的产品，像开发者给同事演示。语速适中，句间自然停顿，不用播音腔，不夸张，不念标题。'}).encode()
        request = urllib.request.Request('https://api.openai.com/v1/audio/speech', data=body,
            headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=120) as response:
            audio = response.read()
        (args.output / f'{i:02}.wav').write_bytes(audio)
        print(f'Generated segment {i + 1}/{len(clips)}')


if __name__ == '__main__':
    main()
