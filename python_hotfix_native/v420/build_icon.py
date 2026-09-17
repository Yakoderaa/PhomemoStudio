from collections import deque
from pathlib import Path
from PIL import Image

src=Path("python_app/assets/sr-gato.png")
img=Image.open(src).convert("RGBA")
w,h=img.size; px=img.load()
seen=set(); q=deque()

# Only remove near-white pixels connected to an image edge. Internal white details survive.
def bg(x,y):
    r,g,b,a=px[x,y]
    return a>0 and r>=242 and g>=242 and b>=242

for x in range(w):
    if bg(x,0): q.append((x,0))
    if bg(x,h-1): q.append((x,h-1))
for y in range(h):
    if bg(0,y): q.append((0,y))
    if bg(w-1,y): q.append((w-1,y))
while q:
    x,y=q.popleft()
    if (x,y) in seen or not (0<=x<w and 0<=y<h) or not bg(x,y): continue
    seen.add((x,y)); r,g,b,a=px[x,y]; px[x,y]=(r,g,b,0)
    q.extend(((x-1,y),(x+1,y),(x,y-1),(x,y+1)))

alpha=img.getchannel("A")
bbox=alpha.getbbox()
if bbox: img=img.crop(bbox)
side=max(img.size); pad=max(12,int(side*.09))
canvas=Image.new("RGBA",(side+pad*2,side+pad*2),(0,0,0,0))
canvas.alpha_composite(img,((canvas.width-img.width)//2,(canvas.height-img.height)//2))
canvas.save("python_app/assets/sr-gato-transparent.png")
canvas.save("python_app/assets/sr-gato.ico",sizes=[(16,16),(20,20),(24,24),(32,32),(40,40),(48,48),(64,64),(128,128),(256,256)])
print("transparent edge pixels removed",len(seen),"alpha",canvas.getchannel("A").getextrema())
