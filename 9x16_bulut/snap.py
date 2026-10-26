import sys, time
from plan_fleming import *
from PIL import Image
ts=[0.0]+[C[k+1]-0.1 for k in range(len(SCENES))]
ims=[];t0=time.time()
for t in ts: ims.append(Image.fromarray(frame(t)[...,::-1][...,::-1]))
print('ms/frame',(time.time()-t0)/len(ts)*1000)
w,h=270,480;sheet=Image.new('RGB',(w*8,h*2))
for i,im in enumerate(ims): sheet.paste(im.resize((w,h)),((i%8)*w,(i//8)*h))
sheet.save(sys.argv[1])
