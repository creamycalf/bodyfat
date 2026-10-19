"""Accept real meal-photo calories and their publication with isolated storage.

The caller supplies the existing controlled model environment. The source image
is read in place; no image or credential is exported to project fixtures. Only
model response content, normalized reports and product output are retained under
tmp for review. Application .data is never opened.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = Path('C:/Users/lxx/AppData/Local/Temp/codex-clipboard-8b48270d-70c1-435d-8911-1e2e68cc9da6.png')
DEFAULT_FOLLOWUP = '请识别这张图片。若是食物，提供营养估算报告并说明主要不确定性。这张图片不表示已经食用。'


def positive_range(value):
    if not isinstance(value, list) or len(value) != 2:
        return False
    return all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in value) \
        and 0 <= value[0] <= value[1] <= 50000 and value[1] > 0


def shown_range(value):
    return f'{value[0]:g}' if value[0] == value[1] else f'{value[0]:g}–{value[1]:g}'


def write_result(output, result):
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=DEFAULT_IMAGE,
                        help='Analyze this image in place; its bytes are not retained in the report.')
    parser.add_argument('--case', choices=['meal_photo'], default='meal_photo')
    parser.add_argument('--category', choices=['auto', 'food'], default='auto',
                        help='Default auto matches sending a photo directly in the Android app.')
    parser.add_argument('--context', default='',
                        help='Optional image note; default empty matches a direct photo upload.')
    parser.add_argument('--artifact-version', default='0.4.31')
    parser.add_argument('--output', type=Path,
                        help='JSON report path under the project tmp directory.')
    parser.add_argument('--prepare-only', action='store_true',
                        help='Validate and prepare the upload in temporary storage without calling a model.')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.artifact_version):
        parser.error('Expected a numeric version label')
    image_path = args.image.resolve()
    if not image_path.is_file():
        parser.error('The supplied image is not an existing file')
    if '.data' in [part.lower() for part in image_path.parts]:
        parser.error('Real application storage is not an eligible image fixture')
    output = args.output or ROOT/f'tmp/calorie-images-live-{args.artifact_version}-{args.case}.json'
    output = (ROOT/output).resolve() if not output.is_absolute() else output.resolve()
    if not output.is_relative_to((ROOT/'tmp').resolve()) or '.data' in [part.lower() for part in output.parts]:
        parser.error('Acceptance reports must stay within the project tmp directory')

    sys.path.insert(0, str(ROOT))
    result = {'case':args.case, 'artifact_version':args.artifact_version,
              'source_name':image_path.name, 'mode':'prepare_only' if args.prepare_only else 'live',
              'category_hint':args.category, 'context':args.context,
              'run_status':'running', 'check_failures':[]}
    failures = result['check_failures']
    with tempfile.TemporaryDirectory(prefix='zhiheng-calorie-photo-') as folder:
        # Import-time initialization must resolve to this fixture, never .data.
        os.environ['ZHIHENG_DATA_DIR'] = folder
        import product
        import server
        import storage

        assert server.DATA.resolve() == Path(folder).resolve()
        server.CONFIG = json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
        storage.initialize(server.DATA)
        image = image_path.read_bytes()
        mime = server.detect_image_mime(image)
        dimensions = server.validate_image_dimensions(image, mime) if mime else None
        if not mime or not dimensions:
            parser.error('The supplied file is not a supported valid image')
        result.update(image_bytes=len(image), image_sha256=hashlib.sha256(image).hexdigest(),
                      mime=mime, dimensions=list(dimensions))
        payload = {'data':base64.b64encode(image).decode('ascii'), 'mime':mime,
                   'category':args.category, 'context':args.context}
        model_calls = []
        actual_call = server.call_ai

        def capture_model_response(*call_args, **call_kwargs):
            started = time.monotonic()
            raw = actual_call(*call_args, **call_kwargs)
            # Retain returned content only, never request args, headers or config.
            parsed = server.parse_json(raw)
            model_calls.append({'raw_response':raw, 'parsed_response':parsed,
                                'structured_json':isinstance(parsed, dict),
                                'elapsed_ms':round((time.monotonic()-started)*1000)})
            return raw

        def prohibit_publication_model_call(*_args, **_kwargs):
            result['publication_extra_model_call'] = True
            raise AssertionError('Image report publication unexpectedly requested another model response')

        server.call_ai = capture_model_response
        started = time.monotonic()
        try:
            answer = server.analyze_image(payload, prepare_only=args.prepare_only)
            result['analysis_elapsed_ms'] = round((time.monotonic()-started)*1000)
            result['model_calls'] = model_calls
            if args.prepare_only:
                result['prepared_media'] = {key:answer.get(key) for key in
                                            ('id', 'type', 'mime', 'bytes', 'width', 'height', 'confirmed')}
                if model_calls:
                    failures.append('Prepare-only unexpectedly requested a model response')
                result['run_status'] = 'prepared' if not failures else 'failed'
            else:
                review = answer.get('review') or {}
                report = review.get('report') or {}
                result.update(model=answer.get('model'), ai_status=answer.get('ai_status'),
                              ai_error=answer.get('ai_error'), media_id=(answer.get('media') or {}).get('id'),
                              normalized_review=review, normalized_report=report)
                if answer.get('ai_status') != 'connected' or answer.get('ai_error'):
                    failures.append('Image analysis did not complete with a connected model and no error')
                if not model_calls or not any(row['structured_json'] for row in model_calls):
                    failures.append('Model did not return a structured JSON image analysis')
                if not str(review.get('summary') or '').strip():
                    failures.append('No nonempty image summary was published')
                if review.get('category') != 'food' or report.get('kind') != 'food':
                    failures.append('The visible meal photo was not recognized as food')
                foods = [row for row in report.get('foods') or [] if isinstance(row, dict)]
                included = [row for row in foods if row.get('included') is not False]
                if not included or not any(str(row.get('name') or '').strip() for row in included):
                    failures.append('No visible food component was retained in the report')
                if not any(positive_range((row.get('nutrition') or {}).get('kcal')) for row in included):
                    failures.append('All visible food calorie estimates are null or invalid')
                total = (report.get('totals') or {}).get('kcal')
                partial = (report.get('partial_totals') or {}).get('kcal')
                result.update(totals_kcal=total, partial_totals_kcal=partial,
                              calorie_coverage=(report.get('coverage') or {}).get('kcal'),
                              included_food_count=len(included),
                              foods_with_nonzero_kcal=sum(positive_range((row.get('nutrition') or {}).get('kcal'))
                                                         for row in included))
                displayed = total if positive_range(total) else partial if positive_range(partial) else None
                result['displayed_kcal'] = displayed
                result['displayed_kcal_is_partial'] = not positive_range(total) and displayed is not None
                if displayed is None:
                    failures.append('No usable calorie range is present in the normalized report')
                write_result(output, result)

                # This exercises the actual public chat path and exposes a second
                # request or nutrient-redaction regression after valid analysis.
                server.call_ai = prohibit_publication_model_call
                publication_started = time.monotonic()
                publication = product.chat(server, {'text':args.context or DEFAULT_FOLLOWUP,
                    'media_id':result['media_id'], 'conversation_id':'calorie-photo-live-acceptance',
                    'client_message_id':'calorie-photo-live-publication'}, image_review_only=True)
                result['publication_elapsed_ms'] = round((time.monotonic()-publication_started)*1000)
                result['publication'] = publication
                reply = str(publication.get('reply') or '')
                if not reply.strip():
                    failures.append('Image-report chat reply is empty')
                background = publication.get('background') or {}
                if (publication.get('ai_error') or publication.get('partial_error')
                        or publication.get('page_error') or publication.get('food_error')
                        or background.get('status') in ('partial', 'failed')
                        or background.get('failed_operations')):
                    failures.append('Image-report publication has an AI or partial error')
                if result.get('publication_extra_model_call'):
                    failures.append('Image-report publication incorrectly made another model request')
                if displayed is not None and f'{shown_range(displayed)} kcal' not in reply:
                    failures.append('Chat reply does not show the validated report calorie range')
                if result['displayed_kcal_is_partial'] and '不是整盘总量' not in reply:
                    failures.append('A partial calorie estimate was not marked as incomplete')
                if '未确认实际食用' not in reply and '未计入本人摄入' not in reply:
                    failures.append('Photo estimate reply omits the separation from actual consumption')
                result['run_status'] = 'failed' if failures else 'completed'
        except Exception as error:
            # Transport exception text may expose service details. Keep only its
            # class and the server's controlled error code, never request data.
            result.update(run_status='failed', exception_type=type(error).__name__,
                          ai_error=server.ai_meta().get('ai_error'), model_calls=model_calls)
            failures.append('Analysis or report publication raised an exception')
        finally:
            server.call_ai = actual_call
            records = server.records()
            result['actual_record_count'] = len(records)
            if records:
                failures.append('An unconfirmed photo was incorrectly saved as actual health intake')
                result['run_status'] = 'failed'
            result['total_elapsed_ms'] = round((time.monotonic()-started)*1000)
            write_result(output, result)

    print(json.dumps({'run_status':result['run_status'], 'case':args.case,
                      'analysis_elapsed_ms':result.get('analysis_elapsed_ms'),
                      'displayed_kcal':result.get('displayed_kcal'),
                      'actual_record_count':result.get('actual_record_count'),
                      'check_failures':failures, 'report':str(output)}, ensure_ascii=False), flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
