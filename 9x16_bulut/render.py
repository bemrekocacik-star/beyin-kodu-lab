import sys, subprocess
from plan_fleming import *
a, b, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
p = subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-",
  "-c:v","libx264","-preset","veryfast","-crf","12","-pix_fmt","yuv420p",out], stdin=subprocess.PIPE)
for n in range(a, b):
    p.stdin.write(frame(n / FPS).tobytes())
p.stdin.close(); p.wait()
