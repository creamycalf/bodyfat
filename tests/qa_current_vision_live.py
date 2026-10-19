"""Current vision service probe using synthetic images and temporary storage.

The caller supplies the controlled model environment. No credentials or personal
health photos are exported, and real application storage is never opened.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import zlib


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'tmp/current-vision-live-0.4.30.json'
EXISTING_SYNTHETIC = ROOT/'tmp/workbench-v3-qa/synthetic-menu.png'


def synthetic_png():
    """Draw three geometric shapes with only the standard library."""
    width, height = 240, 120
    rows = []
    for y in range(height):
        pixels = bytearray()
        for x in range(width):
            color = (255, 255, 255)
            if 15 <= x < 75 and 20 <= y < 100:
                color = (220, 45, 45)
            elif (x-120)**2+(y-60)**2 <= 35**2:
                color = (45, 150, 65)
            elif 180 <= x <= 225 and 20 <= y <= 100 and abs(x-202) <= (y-20)*0.29:
                color = (40, 80, 220)
            pixels.extend(color)
        rows.append(b'\x00'+bytes(pixels))

    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data))

    return (b'\x89PNG\r\n\x1a\n'
            +chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            +chunk(b'IDAT', zlib.compress(b''.join(rows)))+chunk(b'IEND', b''))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, choices=range(1, 4), default=1,
                        help='Analyze consecutive fresh uploads sequentially (1 to 3).')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    results = []

    with tempfile.TemporaryDirectory(prefix='zhiheng-current-vision-') as folder:
        os.environ['ZHIHENG_DATA_DIR'] = folder
        import server
        import storage

        assert server.DATA.resolve() == Path(folder).resolve()
        server.CONFIG = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
        storage.initialize(server.DATA)
        if EXISTING_SYNTHETIC.is_file():
            image = EXISTING_SYNTHETIC.read_bytes()
            image_source = 'existing_synthetic_menu_fixture'
        else:
            image = synthetic_png()
            image_source = 'generated_geometric_fixture'
        assert server.detect_image_mime(image) == 'image/png'
        dimensions = server.validate_image_dimensions(image, 'image/png')
        assert dimensions
        actual_call = server.call_ai
        call_results = []

        def capture_structured_response(*call_args, **call_kwargs):
            raw = actual_call(*call_args, **call_kwargs)
            parsed = server.parse_json(raw)
            # Keep only format information; never retain request args/headers.
            call_results.append({'structured_json':isinstance(parsed, dict),
                                 'response_chars':len(raw) if isinstance(raw, str) else 0})
            return raw

        server.call_ai = capture_structured_response
        try:
            for number in range(1, args.runs+1):
                call_results.clear()
                started = time.monotonic()
                row = {'run':number, 'image_source':image_source, 'image_bytes':len(image),
                       'image_sha256':hashlib.sha256(image).hexdigest(),
                       'dimensions':list(dimensions)}
                try:
                    answer = server.analyze_image({
                        'data':base64.b64encode(image).decode('ascii'),
                        'mime':'image/png', 'category':'general',
                        'context':'这是软件测试用合成图片，不是真人健康资料。请描述图中可见文字或物体，不推断本人摄入、病史或诊断。',
                    })
                    review = answer.get('review', {})
                    row.update(model=answer.get('model'), status=answer.get('ai_status'),
                               error=answer.get('ai_error'), summary=review.get('summary', ''),
                               category=review.get('category'),
                               media_id=answer.get('media', {}).get('id'))
                except Exception as error:
                    # Exception messages can contain transport details; retain
                    # only the class and sanitized server error code.
                    row.update(status='exception', error=server.ai_meta().get('ai_error')
                               or type(error).__name__, exception_type=type(error).__name__)
                row.update(elapsed_ms=round((time.monotonic()-started)*1000),
                           model_calls=list(call_results))
                failures = []
                if row.get('error'):
                    failures.append('Vision request or structured analysis failed')
                if not row.get('summary', '').strip():
                    failures.append('No nonempty parsed image summary')
                if not call_results or not call_results[-1]['structured_json']:
                    failures.append('Model did not return a parsed JSON object')
                if server.records():
                    failures.append('Synthetic image was incorrectly saved as actual health records')
                row['check_failures'] = failures
                results.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
                OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        finally:
            server.call_ai = actual_call
            OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        failed = any(row.get('check_failures') for row in results)
        print(json.dumps({'run_status':'failed' if failed else 'completed',
                          'runs':len(results), 'failed_runs':sum(bool(row['check_failures'])
                                                               for row in results)}, ensure_ascii=False), flush=True)
        return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
