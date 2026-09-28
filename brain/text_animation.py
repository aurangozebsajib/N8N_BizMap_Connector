
import os, pathlib, subprocess
from PIL import Image, ImageFont, ImageDraw, features
def find_bengali_font():
    candidates=[]
    search_dirs=["/usr/share/fonts/truetype/noto","/usr/share/fonts","/usr/share/fonts/truetype"]
    for d in search_dirs:
        p=pathlib.Path(d)
        if not p.exists():
            continue
        for f in p.rglob("*Bengali*.ttf"):
            candidates.append(str(f))
        for f in p.rglob("*NotoSansBengali*.ttf"):
            candidates.append(str(f))
    for c in candidates:
        if "Regular" in c:
            return c
    if candidates:
        return candidates[0]
    return None
def render_text_image(text, font_path, width=1280, height=720):
    has_raqm=features.check("raqm")
    if not has_raqm:
        print("ERROR: Pillow raqm feature missing, Bangla will be garbled")
        return None, "failed-local-render"
    img=Image.new("RGB",(width,height),(18,18,18))
    draw=ImageDraw.Draw(img)
    font_size=48
    try:
        font=ImageFont.truetype(font_path, font_size, layout_engine=ImageFont.Layout.RAQM)
    except Exception as e:
        print(f"Font load fail {e}")
        return None, f"failed-local-render {e}"
    accent=False
    for prefix in ("প্রথম শিক্ষা","দ্বিতীয় শিক্ষা","তৃতীয় শিক্ষা","সারকথা"):
        if text.startswith(prefix):
            accent=True
            break
    words=text.split()
    lines=[]
    cur=""
    for w in words:
        test=(cur+" "+w).strip() if cur else w
        try:
            bbox=draw.textbbox((0,0), test, font=font)
            w_px=bbox[2]-bbox[0]
        except:
            w_px=len(test)*font_size*0.6
        if w_px > width-120:
            if cur:
                lines.append(cur)
            cur=w
        else:
            cur=test
    if cur:
        lines.append(cur)
    while len(lines)>12 and font_size>28:
        font_size-=4
        try:
            font=ImageFont.truetype(font_path, font_size, layout_engine=ImageFont.Layout.RAQM)
        except:
            break
        lines=[]
        cur=""
        for w in words:
            test=(cur+" "+w).strip() if cur else w
            try:
                bbox=draw.textbbox((0,0), test, font=font)
                w_px=bbox[2]-bbox[0]
            except:
                w_px=len(test)*font_size*0.6
            if w_px > width-120:
                if cur:
                    lines.append(cur)
                cur=w
            else:
                cur=test
        if cur:
            lines.append(cur)
    line_h=font_size+12
    total_h=len(lines)*line_h
    y_start=(height-total_h)//2
    for i, line in enumerate(lines):
        try:
            bbox=draw.textbbox((0,0), line, font=font)
            tw=bbox[2]-bbox[0]
        except:
            tw=len(line)*font_size*0.6
        x=(width-tw)//2
        y=y_start + i*line_h
        color=(255,220,100) if accent and i==0 else (240,240,240)
        draw.text((x,y), line, font=font, fill=color)
    return img, "ok"
def probe_duration(file_path):
    try:
        cmd=["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", file_path]
        out=subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(out.stdout.strip())
    except:
        return 0.0
def make_text_animation_clip(text, output_path, duration_sec, font_path=None):
    if font_path is None:
        font_path=find_bengali_font()
    if not font_path:
        print("No Bengali font found")
        return False, "failed-local-render no font", 0
    img, status = render_text_image(text, font_path)
    if img is None:
        return False, status, 0
    tmp_png=output_path + ".tmp.png"
    img.save(tmp_png)
    dur=max(duration_sec, 3.0)
    cmd=["ffmpeg","-y","-loop","1","-i",tmp_png,"-t", str(dur),"-vf","scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,zoompan=d=1:s=1280x720:fps=24:z='min(zoom+0.0015,1.2)',fade=t=in:st=0:d=0.5","-c:v","libx264","-pix_fmt","yuv420p","-r","24",output_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg text anim fail: {e}")
        return False, "failed-local-render ffmpeg", 0
    except Exception as e:
        print(f"ffmpeg exception {e}")
        return False, f"failed-local-render {e}", 0
    finally:
        try:
            os.remove(tmp_png)
        except:
            pass
    clip_dur=probe_duration(output_path)
    return True, "success-local", clip_dur
def make_kenburns_clip(ref_image_path, output_path, duration_sec):
    dur=max(duration_sec, 3.0)
    cmd=["ffmpeg","-y","-loop","1","-i", ref_image_path,"-t", str(dur),"-vf","scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,zoompan=d=1:s=1280x720:fps=24:z='min(zoom+0.001,1.15)',fade=t=in:st=0:d=0.5","-c:v","libx264","-pix_fmt","yuv420p","-r","24",output_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg kenburns fail {e}")
        return False, 0
    clip_dur=probe_duration(output_path)
    return True, clip_dur
