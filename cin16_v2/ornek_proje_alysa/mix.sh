#!/bin/bash
V=$1; D=$2; MV=$3; FV=$4
PRE="aresample=48000,highpass=f=80,equalizer=f=250:t=q:w=1:g=-3,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,equalizer=f=3000:t=q:w=1:g=3,apad=whole_dur=$D"
LN(){ python3 -c "import json,sys;j=json.loads(sys.argv[1]);print(f\"loudnorm=I=-14:TP=-1.5:LRA=$2:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true\")" "$1"; }
if [ ! -f v_norm.wav ]; then
J=$(ffmpeg -hide_banner -i "$V" -af "$PRE,loudnorm=I=-14:TP=-1.5:LRA=9:print_format=json" -t $D -f null - 2>&1 | sed -n '/^{/,/^}/p')
ffmpeg -hide_banner -loglevel error -y -i "$V" -af "$PRE,$(LN "$J" 9),aresample=48000" -t $D -ac 1 v_norm.wav
fi
F="[0:a]asplit=3[v][k1][k2];[1:a]aresample=48000,volume=$MV,equalizer=f=2500:t=q:w=1:g=-8,equalizer=f=1000:t=q:w=1:g=-4,lowpass=f=9000[m];[m][k1]sidechaincompress=threshold=0.006:ratio=10:attack=5:release=300[mc];[2:a]aresample=48000,volume=$FV,lowpass=f=9000[f];[f][k2]sidechaincompress=threshold=0.01:ratio=6:attack=5:release=250[fc]"
ffmpeg -hide_banner -loglevel error -y -i v_norm.wav -i music.wav -i fx.wav -filter_complex "$F;[mc][fc]amix=inputs=2:normalize=0[bg];[bg]asplit[b1][b2];[v][b1]amix=inputs=2:normalize=0,alimiter=limit=0.84:level=0[o]" -map "[o]" -t $D -ac 2 -ar 48000 mix.wav -map "[b2]" -t $D -ac 1 bg_only.wav
J=$(ffmpeg -hide_banner -i mix.wav -af "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json" -f null - 2>&1 | sed -n '/^{/,/^}/p')
ffmpeg -hide_banner -loglevel error -y -i mix.wav -af "$(LN "$J" 11),aresample=48000" mix_n.wav && mv mix_n.wav mix.wav
ffmpeg -hide_banner -loglevel error -y -i mix.wav -c:a aac -b:a 192k mix.m4a
ffmpeg -hide_banner -i mix.m4a -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|Peak):" | tail -2
