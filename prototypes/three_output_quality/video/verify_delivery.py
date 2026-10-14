"""核對最終 MP4，另作音量交付版；固定音訊的 A/B 保留不動。"""
import hashlib
import json
import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "out"


def run(args):
	return subprocess.run(args,check=True,capture_output=True,text=True)


def probe(path):
	return json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)]).stdout)


def loudness(path, log):
	r=run(['ffmpeg','-hide_banner','-i',str(path),'-af','loudnorm=I=-16:TP=-1:LRA=11:print_format=json','-f','null','-'])
	log.write_text(r.stderr)
	return json.loads(re.search(r'\{\s*"input_i".*?\}',r.stderr,re.S).group(0))


def video_hash(path):
	return run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(path),'-map','0:v:0','-c','copy','-f','hash','-hash','sha256','-']).stdout.strip().split('=')[1]


def main():
	base=OUT/'B-board.mp4'
	delivery=OUT/'B-delivery-normalized.mp4'
	run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(base),'-map','0:v:0','-map','0:a:0','-c:v','copy','-af','loudnorm=I=-16:TP=-1.5:LRA=11','-c:a','aac','-b:a','160k','-movflags','+faststart',str(delivery)])
	files=['A-original.mp4','B-board.mp4','B-delivery-normalized.mp4','C-y3_whiteboard.mp4','C-y5_kinetic_type.mp4']
	decoded=[]
	for name in files:
		r=run(['ffmpeg','-hide_banner','-v','error','-xerror','-i',str(OUT/name),'-f','null','-'])
		assert not r.stderr, r.stderr
		decoded.append(name)
	data=probe(base)
	(OUT/'B-probe.json').write_text(json.dumps(data,ensure_ascii=False,indent='\t')+'\n')
	v=next(s for s in data['streams'] if s['codec_type']=='video')
	a=next(s for s in data['streams'] if s['codec_type']=='audio')
	assert int(v['nb_read_frames'])==1672 and (v['width'],v['height'])==(1920,1080)
	original=loudness(base,OUT/'B-loudness.log')
	normal=loudness(delivery,OUT/'B-delivery-loudness.log')
	assert -16.5<=float(normal['input_i'])<=-15.5 and float(normal['input_tp'])<=-1
	base_hash=video_hash(base)
	assert base_hash==video_hash(delivery)
	rows=json.loads((OUT/'timing.json').read_text())
	last_end=rows[-1]['t1']
	assert float(a['duration'])>=last_end and float(v['duration'])>=float(a['duration'])
	check={'audio_original_duration':a['duration'],'video_duration':v['duration'],'video_frames':int(v['nb_read_frames']),'last_voiced_end':last_end,'tail_after_last_voiced_end':float(v['duration'])-last_end,'audio_end_after_last_voiced_end':float(a['duration'])-last_end,'full_decode_exit_0':decoded,'A_B_input_audio_same_sha256':hashlib.sha256((OUT/'audio.wav').read_bytes()).hexdigest(),'encoded_video_sha256':base_hash,'normalized_picture_unchanged':True,'loudness_original':{'integrated_lufs':float(original['input_i']),'true_peak_db':float(original['input_tp'])},'loudness_delivery':{'integrated_lufs':float(normal['input_i']),'true_peak_db':float(normal['input_tp'])},'word_precision':'not measured; only sample-rebuilt sentence WAV boundaries'}
	(OUT/'delivery-check.json').write_text(json.dumps(check,ensure_ascii=False,indent='\t')+'\n')
	manifest={name:{'bytes':(OUT/name).stat().st_size,'sha256':hashlib.sha256((OUT/name).read_bytes()).hexdigest()} for name in files}
	manifest['baseline_source']='saved 2026-10-04 q2; this run is a renderer fixture, zero generation'
	manifest['audio_identity']='identity.json'
	manifest['external_versions']='../vendor/sources.json'
	(OUT/'artifact-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent='\t')+'\n')
	print(json.dumps(check,ensure_ascii=False))


if __name__=='__main__':
	main()
