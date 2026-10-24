import subprocess
jobs = [l.split() for l in open('broll_jobs.txt') if l.strip()] + [l.split() for l in open('v2_jobs.txt') if l.strip()]
inp = ['-i', 'video_raw.mp4']; fc = []; last = '0:v'
for i, (a, b, f) in enumerate(jobs):
    a0 = round(float(a) * 24) / 24; b0 = round(float(b) * 24) / 24
    inp += ['-i', f]
    fc.append(f"[{i + 1}:v]setpts=PTS-STARTPTS+{a0}/TB[s{i}]")
    fc.append(f"[{last}][s{i}]overlay=eof_action=pass:enable='between(t,{a0},{b0 - 0.001})'[o{i}]"); last = f"o{i}"
fc.append(f"[{last}]ass=alt.ass[v]")
inp += ['-i', 'mix.m4a']
cmd = ['ffmpeg', '-y', '-loglevel', 'error'] + inp + ['-filter_complex', ';'.join(fc), '-map', '[v]', '-map', f'{len(jobs) + 1}:a',
       '-c:v', 'libx264', '-b:v', '5800k', '-maxrate', '9000k', '-bufsize', '12000k', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-r', '24',
       '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
       '-c:a', 'copy', '-shortest', '-movflags', '+faststart', 'Alysa_Liu_16x9_Kod2_v2.mp4']
subprocess.run(cmd, check=True); print('ok')
