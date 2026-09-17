from pathlib import Path
from phomemo_studio.core import *

def test_label_pixels():
    assert label_pixels(40,12)==(320,96)

def test_pack_and_packet():
    px=[[False]*16 for _ in range(8)]; px[0][0]=True; px[0][15]=True
    data,w,h=pack_mono_pixels(px)
    assert (w,h)==(16,8); assert data[0]==0x80 and data[1]==0x01
    packets=make_print_packet(data,w,h,density=6)
    assert packets[0]==bytes([0x1b,0x37,0x07,6,0x02])
    assert packets[-1]==bytes([0x1b,0x64,0])

def test_state_round_trip(tmp_path):
    p=tmp_path/'state.json'; s=AppState(groups=['General','Cafe'],roll_total=100,roll_remaining=77,density=8); s.templates=[Template('1','A','Cafe',40,12,[])]
    StateStore(p).save(s); loaded=StateStore(p).load(); assert loaded.roll_remaining==77 and loaded.templates[0].name=='A'
