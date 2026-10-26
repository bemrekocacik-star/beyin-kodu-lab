#!/bin/bash
# mix v3 (bulut): ses zinciri + müzik sidechain (release 700 ms) + iki geçiş loudnorm
V=$1; M=$2; MV=${3:-0.22}
ffmpeg -v error -y -i $V -af "highpass=f=80,equalizer=f=250:t=q:w=1:g=-3,acompressor=threshold=-20dB:ratio=3:attack=10:release=120,equalizer=f=3000:t=q:w=1.2:g=3,aresample=48000,aformat=channel_layouts=stereo" v_proc.wav
ffmpeg -v error -y -i v_proc.wav -i $M -filter_complex "[1:a]lowpass=f=9000,volume=$MV[m];[0:a]asplit[v1][v2];[m][v2]sidechaincompress=threshold=0.015:ratio=12:attack=15:release=700[md];[v1][md]amix=inputs=2:normalize=0:duration=first[mx]" -map "[mx]" pre.wav
ffmpeg -v error -y -i v_proc.wav -i $M -filter_complex "[1:a]lowpass=f=9000,volume=$MV[m];[0:a]anull[v2];[m][v2]sidechaincompress=threshold=0.015:ratio=12:attack=15:release=700[md]" -map "[md]" bg_stem.wav
J=$(ffmpeg -hide_banner -i pre.wav -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n '/{/,/}/p')
gi(){ echo "$J" | python3 -c "import json,sys;print(json.load(sys.stdin)['$1'])"; }
ffmpeg -v error -y -i pre.wav -af "loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$(gi input_i):measured_TP=$(gi input_tp):measured_LRA=$(gi input_lra):measured_thresh=$(gi input_thresh):offset=$(gi target_offset):linear=true,aresample=48000" -ar 48000 final_audio.wav
