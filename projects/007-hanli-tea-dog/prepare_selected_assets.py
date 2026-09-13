"""Reproduce deterministic reference-sheet selection and the small prop repair."""
import json,pathlib
from PIL import Image,ImageDraw,ImageFilter
P=pathlib.Path(__file__).resolve().parent
a=Image.open(P/'storyboards/character_v1/13_images_00001_.png');b=Image.open(P/'storyboards/character_v2/13_images_00003_.png')
views=[a.crop((0,0,512,768)),a.crop((512,0,1024,768)),b.crop((1024,0,1536,768))]
sheet=Image.new('RGB',(1536,768))
for i,(name,view) in enumerate(zip(['front','three_quarter','profile'],views)):
    view.save(P/'assets'/('hanli_'+name+'.png'));sheet.paste(view,(i*512,0))
sheet.save(P/'assets/character_selected_views.png')
out=P/'storyboards/dog_frame_selected';cfg=json.loads((out/'composition.json').read_text())
base=Image.open(P/'storyboards/dog_frame_v1/13_images_00006_.png').convert('RGBA')
src=Image.open(P/'storyboards/dog_frame_v2/13_images_00007_.png').convert('RGBA')
mask=Image.new('L',src.size);d=ImageDraw.Draw(mask);d.polygon([tuple(x) for x in cfg['cup_polygon']],fill=255);d.ellipse((508,480,525,496),fill=0)
src.putalpha(mask.filter(ImageFilter.GaussianBlur(.45)))
cup=src.crop(tuple(cfg['cup_crop'])).resize(tuple(cfg['cup_size']),Image.Resampling.LANCZOS)
shadow=Image.new('RGBA',base.size);ImageDraw.Draw(shadow).ellipse((478,511,533,523),fill=(39,30,15,55))
base=Image.alpha_composite(base,shadow.filter(ImageFilter.GaussianBlur(3)));base.alpha_composite(cup,tuple(cfg['cup_position']))
base.convert('RGB').save(out/'start.png');cup.save(out/'cup_cutout.png')
