"""Verify actual candidate animation, then optionally export silent MP4 and SRT."""
import argparse
import base64
import hashlib
import json
import math
import pathlib
import subprocess
import time

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'out'


def screenshot_difference(page, a, b):
    if a == b:
        return {'changed_pixels': 0, 'max_channel_delta': 0}
    # Chromium caches filtered SVG/text layers differently after playback. Allow
    # only <=250 differing pixels (0.013% of 1080p) with channel delta <=24.
    # Text, bounds, opacity and subtitle state must still match exactly below.
    return page.evaluate('''async ([a,b])=>{
      const decode=async s=>{const image=new Image();image.src='data:image/png;base64,'+s;await image.decode();const c=document.createElement('canvas');c.width=image.width;c.height=image.height;const ctx=c.getContext('2d');ctx.drawImage(image,0,0);return ctx.getImageData(0,0,c.width,c.height).data;};
      const x=await decode(a),y=await decode(b);let changed=0,max=0;
      for(let i=0;i<x.length;i+=4){let delta=0;for(let j=0;j<4;j++)delta=Math.max(delta,Math.abs(x[i+j]-y[i+j]));if(delta)changed++;max=Math.max(max,delta);}
      return {changed_pixels:changed,max_channel_delta:max};
    }''', [base64.b64encode(a).decode(), base64.b64encode(b).decode()])


def subtitle_time(value):
    ms = round(value * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='+')
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--url', default='http://127.0.0.1:8932')
    args = parser.parse_args()
    trials = json.loads((HERE / 'trials.json').read_text())
    manifest = json.loads((HERE / 'vendor/sources.json').read_text())
    for source in manifest:
        assert hashlib.sha256((HERE / source['local']).read_bytes()).hexdigest() == source['sha256'], source['local']
    font = json.loads((HERE / 'vendor/font.json').read_text())
    assert hashlib.sha256((HERE / 'vendor/teaching-subset.woff').read_bytes()).hexdigest() == font['subset_sha256']
    for trial in trials:
        previous = 0
        for start, end, text in trial['subtitles']:
            assert previous <= start < end <= trial['duration']
            assert len(text) / (end - start) <= 10, (trial['id'], text)
            previous = end
    chart = next(t for t in trials if t['id'] == 'chart')['payload']
    assert [s['value'] for s in chart['series']] == [chart['n'], chart['n'] ** 2]
    chalk = next(t for t in trials if t['id'] == 'chalk')['payload']
    assert chalk['chars'] == list('Hello') and chalk['capacity'] == len(chalk['chars']) + 1
    drafting = next(t for t in trials if t['id'] == 'drafting')['payload']
    assert drafting['addresses'] == [drafting['base'] + i * drafting['bytes_per_item'] for i in range(4)]
    OUT.mkdir(exist_ok=True)
    reports = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for trial in trials:
            if args.ids and trial['id'] not in args.ids:
                continue
            started = time.time()
            errors = []
            page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
            url = args.url + '/sample.html?export&id=' + trial['id']
            page.goto(url)
            page.wait_for_function('window.__ready || window.__failed')
            assert not page.evaluate('window.__failed || null'), trial['id']
            assert page.evaluate('window.__sourceId') == trial['source_id']
            frame = page.locator('#frame')
            times = sorted({0, .5, 2.5, 5, 8, 11, 14.9, *[s[0] for s in trial['subtitles']]})
            baseline = {}
            states = {}
            for t in times:
                cold = browser.new_page(viewport={'width': 1920, 'height': 1080})
                cold.goto(url)
                cold.wait_for_function('window.__ready || window.__failed')
                assert not cold.evaluate('window.__failed || null')
                states[t] = cold.evaluate('t=>renderFrame(t)', t)
                baseline[t] = cold.locator('#frame').screenshot()
                cold.close()
            boxes = []
            seek_differences = []
            for t in [*times, *reversed(times)]:
                info = page.evaluate('t=>renderFrame(t)', t)
                if info != states[t]:
                    (OUT / f'{trial["id"]}.seek-failure.json').write_text(json.dumps({'time':t,'actual':info,'expected':states[t]},ensure_ascii=False,indent=2))
                    raise AssertionError((trial['id'], 'seek state mismatch', t))
                difference = screenshot_difference(page, frame.screenshot(), baseline[t])
                if difference['changed_pixels'] > 250 or difference['max_channel_delta'] > 24:
                    (OUT / f'{trial["id"]}.seek-failure-expected.png').write_bytes(baseline[t])
                    (OUT / f'{trial["id"]}.seek-failure-actual.png').write_bytes(frame.screenshot())
                assert difference['changed_pixels'] <= 250 and difference['max_channel_delta'] <= 24, (trial['id'], 'seek pixels mismatch', t, difference)
                seek_differences.append({'t': t, **difference})
                for box in info['texts']:
                    if box['alpha'] < .15 or not box['text'].strip():
                        continue
                    assert box['x'] >= -2 and box['y'] >= -2 and box['x'] + box['w'] <= 1922 and box['y'] + box['h'] <= 1082, (trial['id'], t, box)
                    if box.get('role') == 'subtitle':
                        assert box['font_px'] >= 38 and box['y'] >= 910, (trial['id'], box)
                    else:
                        assert box['y'] + box['h'] <= 912, (trial['id'], 'caption occlusion', t, box)
                    boxes.append({'t': t, **box})
            assert not errors, (trial['id'], errors)
            for t in [2.5, 8, 14.9]:
                page.evaluate('t=>renderFrame(t)', t)
                frame.screenshot(path=str(OUT / f'{trial["id"]}-{t}.png'))
            frames = math.ceil(trial['duration'] * 24)
            video = OUT / f'{trial["id"]}.mp4'
            if args.export:
                encoder = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-vcodec', 'png', '-r', '24', '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video)], stdin=subprocess.PIPE)
                try:
                    for k in range(frames):
                        info = page.evaluate('t=>renderFrame(t)', k / 24)
                        for box in info['texts']:
                            if box['alpha'] >= .15 and box['text'].strip():
                                assert box['x'] >= -2 and box['y'] >= -2 and box['x'] + box['w'] <= 1922 and box['y'] + box['h'] <= 1082, (trial['id'], k, box)
                                if box.get('role') != 'subtitle':
                                    assert box['y'] + box['h'] <= 912, (trial['id'], 'caption occlusion', k, box)
                        encoder.stdin.write(frame.screenshot(type='png'))
                        if (k + 1) % 120 == 0:
                            print(f'{trial["id"]}: {k + 1}/{frames} frames', flush=True)
                finally:
                    encoder.stdin.close()
                assert encoder.wait() == 0
                probe = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(video)], check=True, capture_output=True, text=True).stdout)
                v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
                assert int(v['nb_read_frames']) == frames and [v['width'], v['height']] == [1920, 1080] and v['r_frame_rate'] == '24/1'
                assert not any(s['codec_type'] == 'audio' for s in probe['streams'])
                subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-xerror', '-i', str(video), '-f', 'null', '-'], check=True)
                for t in [0, 8, 14.9]:
                    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(t), '-i', str(video), '-frames:v', '1', str(OUT / f'{trial["id"]}-mp4-{t}.png')], check=True)
                (OUT / f'{trial["id"]}.srt').write_text('\n\n'.join(f'{i}\n{subtitle_time(start)} --> {subtitle_time(end)}\n{text}' for i, (start, end, text) in enumerate(trial['subtitles'], 1)) + '\n')
            assert not errors, (trial['id'], errors)
            report = {'id': trial['id'], 'source_id': trial['source_id'], 'duration': trial['duration'], 'fps': 24, 'frames': frames if args.export else None, 'exported': args.export, 'cold_and_reverse_seek': True, 'errors': errors, 'text_measurements': boxes, 'seek_pixel_differences': seek_differences, 'seconds': round(time.time() - started, 2)}
            (OUT / f'{trial["id"]}.report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            reports.append({k: v for k, v in report.items() if k not in ('text_measurements', 'seek_pixel_differences')})
            print(json.dumps(reports[-1], ensure_ascii=False), flush=True)
            page.close()
        browser.close()


if __name__ == '__main__':
    main()
