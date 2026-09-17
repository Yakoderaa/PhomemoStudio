from phomemo_studio.core import Element
from phomemo_studio.render import render_label, image_to_d30_raster

def test_render_rotated_raster():
    img=render_label([Element('rect',2,2,30,20,stroke=2)],40,12)
    data,w,h=image_to_d30_raster(img)
    assert (w,h)==(96,320)
    assert len(data)==12*320
