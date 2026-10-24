import subprocess
jobs = [l.split() for l in open('broll_jobs.txt') if l.strip()]
inp = ['-i', 'video_raw.mp4']; fc = []; last = '0:v'
for i, (a, b, f) in enumerate(jobs):
    a0 = round(float(a) * 24) / 24; b0 = round(float(b) * 24) / 24
    inp += ['-i', f]
    fc.append(f"[{i + 1}:v]setpts=PTS-STARTPTS+{a0}/TB[s{i}]")
    fc.append(f"[{last}][s{i}]overlay=eof_action=pass:enable='between(t,{a0},{b0 - 0.001})'[o{i}]"); last = f"o{i}"
fc.append(f"[{last}]ass=alt.ass[v]")
inp += ['-i', 'mix.m4a']
cmd = ['ffmpeg', '-y', '-loglevel', 'error'] + inp + ['-filter_complex', ';'.join(fc), '-map', '[v]', '-map', f'{len(jobs) + 1}:a',
       '-c:v', 'libx264', '-crf', '23', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
       '-c:a', 'aac', '-b:a', '320k', '-shortest', '-movflags', '+faststart', 'Alysa_Liu_16x9_final.mp4']
subprocess.run(cmd, check=True); print('ok')
