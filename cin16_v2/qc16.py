# kullanım: qc16.py plan.json out_prefix t1 t2 ... (tam çözünürlük tek kare + kontak)
import sys
args = sys.argv[1:]; plan, pre, ts = args[0], args[1], [float(x) for x in args[2:]]
sys.argv = ['cin16', plan, '0', '0', '/dev/null']
import os
__file__ = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0] if False else __file__)), 'cin16.py')
src = open(__file__, encoding='utf-8').read().split('\nff = subprocess.Popen')[0]
exec(src)
ims = []
for t in ts:
    fr = frame(t); Image.fromarray(fr).save(f'{pre}_{t:.1f}.jpg', quality=88); ims.append(Image.fromarray(fr).resize((640, 360)))
cols = 4; rows = (len(ims) + cols - 1) // cols; sheet = Image.new('RGB', (640 * cols, 360 * rows))
for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * 640, (i // cols) * 360))
sheet.save(f'{pre}_sheet.jpg', quality=85); print('ok')
