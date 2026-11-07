"""全量烘焙第一弹 std 整换 anm 贴图像素级替换 独立 png 整换"""
import struct, subprocess, sys, pathlib, os
sys.path.insert(0, r'C:\Users\admin\.zcode\workspace\draft-38b7f925-6205-41a1-a094-de2526f4cd0d')
from tha1 import Tha1, resource_crypt, CIPHERS
import numpy as np
from PIL import Image

SRC = r'C:/Touhou Pearl Tower/game/th15.dat'
DST = r'C:/touhou15-web-port/dl/th15_full.dat'
PATCH = pathlib.Path(r'C:/Touhou Pearl Tower/thcrap/repos/thpatch/lang_zh-hans/th15')
RUN_LZ = r'C:\Users\admin\.zcode\workspace\draft-38b7f925-6205-41a1-a094-de2526f4cd0d\run-lz.mjs'

def cpp_lzss(data):
    p = subprocess.run(['node', RUN_LZ], input=data, capture_output=True)
    assert p.returncode == 0, p.stderr.decode('utf-8', 'replace')[-200:]
    return p.stdout

def load_png_rgba(path, w, h):
    im = Image.open(path).convert('RGBA')
    if im.size != (w, h):
        im = im.resize((w, h), Image.LANCZOS)
    return np.array(im)

def to_thtx(rgba, fmt):
    h, w = rgba.shape[:2]
    R, G, B, A = rgba[:, :, 0].astype(np.uint16), rgba[:, :, 1].astype(np.uint16), rgba[:, :, 2].astype(np.uint16), rgba[:, :, 3].astype(np.uint16)
    if fmt == 1:
        out = np.empty((h, w, 4), np.uint8)
        out[:, :, 0] = B; out[:, :, 1] = G; out[:, :, 2] = R; out[:, :, 3] = A
        return out.tobytes()
    if fmt == 4:
        out = np.empty((h, w, 3), np.uint8)
        out[:, :, 0] = B; out[:, :, 1] = G; out[:, :, 2] = R
        return out.tobytes()
    if fmt == 5:
        v = ((A >> 4) << 12) | ((R >> 4) << 8) | ((G >> 4) << 4) | (B >> 4)
        return v.astype('<u2').tobytes()
    if fmt == 2:
        v = ((A > 127).astype(np.uint16) << 15) | ((R * 31 // 255) << 10) | ((G * 31 // 255) << 5) | (B * 31 // 255)
        return v.astype('<u2').tobytes()
    if fmt == 3:
        v = ((R * 31 // 255) << 11) | ((G * 63 // 255) << 5) | (B * 31 // 255)
        return v.astype('<u2').tobytes()
    if fmt == 6:
        v = ((A & 255) << 8) | ((R * 7 // 255) << 5) | ((G * 7 // 255) << 2) | (B * 3 // 255)
        return v.astype('<u2').tobytes()
    if fmt == 7:
        return A.astype(np.uint8).tobytes()
    raise ValueError('不支持格式 ' + str(fmt))

def make_copy_line(w, h):
    """©2026 wuyulbw All right reserved 深蓝衬线白描边 仿原版式"""
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    from PIL import ImageDraw, ImageFont
    text = '\u00a92026 wuyulbw All right reserved'
    size = 27
    font = ImageFont.truetype('C:/Windows/Fonts/times.ttf', size)
    d = ImageDraw.Draw(img)
    tw = d.textbbox((0, 0), text, font=font, stroke_width=3)
    x = (w - (tw[2] - tw[0])) // 2 - tw[0]
    y = (h - (tw[3] - tw[1])) // 2 - tw[1]
    d.text((x, y), text, font=font, fill=(16, 45, 110, 255), stroke_width=3, stroke_fill=(255, 255, 255, 255))
    return np.array(img)

def logo_slot_rgba(w, h):
    """白卡镂空字 png 反相:卡->透明 字孔->白字形 描边红带保留 等比适配槽位"""
    im = Image.open(PATCH / 'title' / 'title_logo.png').convert('RGBA')
    a = np.array(im).astype(np.uint16)
    A = a[:, :, 3]; R = a[:, :, 0]; G = a[:, :, 1]; B = a[:, :, 2]
    card = (A == 255) & (R >= 245) & (G >= 245) & (B >= 245)
    hole = (A == 0)
    out = a.copy()
    out[:, :, 3] = np.where(card, 0, A)
    out[hole] = [244, 177, 205, 255]
    src = Image.fromarray(out.astype('uint8'), 'RGBA')
    bbox = src.getbbox() or (0, 0, src.width, src.height)
    content = src.crop(bbox)
    scale = min(w / content.width, h / content.height)
    nw, nh = max(1, int(content.width * scale)), max(1, int(content.height * scale))
    canvas = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    canvas.alpha_composite(content.resize((nw, nh), Image.LANCZOS), ((w - nw) // 2, (h - nh) // 2))
    return np.array(canvas)

def bake_anm_textures(anm: bytes, pngs: dict, tag: str):
    if os.environ.get('BAKE_NO_TEX'):
        return anm
    t = bytes(anm)
    def g32(buf, o): return struct.unpack_from('<I', buf, o)[0]
    def g16(buf, o): return struct.unpack_from('<H', buf, o)[0]
    # 收集条目范围
    ents = []
    base = 0
    while base < len(t):
        stride = g32(t, base + 36)
        end = len(t) if not stride else base + stride
        ents.append((base, end))
        if not stride: break
        base = end
    out = bytearray(); done = []
    for bi, (b0, b1) in enumerate(ents):
        chunk = bytearray(t[b0:b1])
        def c32(o): return struct.unpack_from('<I', chunk, o)[0]
        def c16(o): return struct.unpack_from('<H', chunk, o)[0]
        noff = c32(16)
        nend = chunk.find(b'\x00', noff)
        name = chunk[noff:nend].decode('ascii', errors='replace')
        if chunk[32] and (name in pngs or name == 'title/title_copy.png'):
            tex = c32(28)
            fmt = c16(tex + 6); pw = c16(tex + 8); ph = c16(tex + 10)
            if name == 'title/title_copy.png':
                rgba = make_copy_line(pw, ph)
            elif name == 'title/title_logo.png':
                mode = os.environ.get('BAKE_LOGO_MODE', 'chars')
                if mode == 'transparent':
                    rgba = np.zeros((ph, pw, 4), np.uint8)
                elif mode == 'mod':
                    rgba = np.array(Image.open(r'C:/Touhou Pearl Tower/thcrap/repos/thpatch/lang_zh-hans/th15/title/title_logo.png').convert('RGBA').resize((pw, ph), Image.LANCZOS))
                elif mode == 'calibrated':
                    rgba = np.array(Image.open(r'C:/touhou15-web-port/dl/logo_slot_calibrated.png').convert('RGBA').resize((pw, ph), Image.LANCZOS))
                else:
                    rgba = np.array(Image.open(r'C:/touhou15-web-port/dl/logo-slot-chars-600.png').convert('RGBA').resize((pw, ph), Image.LANCZOS))
            elif os.environ.get('BAKE_LOGO_MODE', 'chars') == 'chars' and name != 'title/title_copy.png':
                # 其余贴图: thcrap 通用语义 THTX/条目头 = MOD png 原尺寸 精灵 UV 重缩放 不 squeeze
                pim = Image.open(str(pngs[name])).convert('RGBA')
                nw2, nh2 = pim.size
                rgba = np.array(pim)
            else:
                rgba = load_png_rgba(pngs[name], pw, ph)
            nh2, nw2 = rgba.shape[:2]
            new = to_thtx(rgba, fmt)
            # THTX 头与条目头宽高更新
            struct.pack_into('<HH', chunk, tex + 8, nw2, nh2)
            struct.pack_into('<I', chunk, tex + 12, len(new))
            struct.pack_into('<HH', chunk, 10, nw2, nh2)
            # 精灵 UV 重缩放(包络基准): 精灵表在名字串后 nameoff+len+(16-len%16) 每 20 字节 {id,x,y,w,h float}
            # MOD png 内容布局 = 原精灵 UV 包络的等比缩放 -> 新 UV = 旧 UV * (png/包络)
            if True:
                spr = noff + (nend - noff) + (16 - (nend - noff) % 16)
                cnt = c16(4)
                xs = []; ys = []; xe = []; ye = []
                for si in range(cnt):
                    fx, fy, fw, fh = struct.unpack_from('<4f', chunk, spr + si * 20 + 4)
                    xs.append(fx); ys.append(fy); xe.append(fx + fw); ye.append(fy + fh)
                env_w, env_h = max(xe) - min(xs), max(ye) - min(ys)
                if env_w > 0 and env_h > 0:
                    sxr, syr = nw2 / env_w, nh2 / env_h
                    minx, miny = min(xs), min(ys)
                    for si in range(cnt):
                        so = spr + si * 20
                        fx, fy, fw, fh = struct.unpack_from('<4f', chunk, so + 4)
                        nx = minx + (fx - minx) * sxr
                        ny = miny + (fy - miny) * syr
                        struct.pack_into('<4f', chunk, so + 4, nx, ny, fw * sxr, fh * syr)
                    done.append(f'{name} env({env_w:.0f}x{env_h:.0f}) UVx({sxr:.2f},{syr:.2f})')
            # 替换数据区 保留条目内其余部分 偏移全部相对条目不变
            chunk[tex + 16:tex + 16 + len(new)] = new
            done.append(f'{name} {pw}x{ph}->{nw2}x{nh2}')
        # 条目内数据长度可能变化 stride 重算 4 对齐
        new_stride = len(chunk) if bi + 1 < len(ents) else 0
        if new_stride: new_stride = (new_stride + 3) & ~3
        struct.pack_into('<I', chunk, 36, new_stride)
        if len(chunk) < new_stride: chunk += bytes(new_stride - len(chunk))
        out += chunk
    return bytes(out), done

def main():
    a = Tha1(SRC)
    patch_pngs = {str(p.relative_to(PATCH)).replace('\\', '/'): p for p in PATCH.rglob('*.png')}
    patch_std = {str(p.relative_to(PATCH)).replace('\\', '/'): p for p in PATCH.rglob('*.std')}
    patch_anm = {str(p.relative_to(PATCH)).replace('\\', '/'): p for p in PATCH.rglob('*.anm')}
    title_idx = next(i for i, e in enumerate(a.entries) if e['name'] == 'title.anm')

    order = [i for i in range(len(a.entries)) if i != title_idx] + [title_idx]
    body = bytearray(); rows = []; report = []
    for i in order:
        e = a.entries[i]
        name = e['name']
        if name == 'title.anm':
            src_anm = a.read(name)
        elif name in patch_anm:
            src_anm = patch_anm[name].read_bytes()
        if name in patch_std:
            raw = patch_std[name].read_bytes()
            blob = resource_crypt(cpp_lzss(raw), CIPHERS[sum(name.encode()) & 7], encrypt=True)
            size, comp = len(raw), len(blob); report.append(f'std {name}')
        elif name.endswith('.anm'):
            src_anm = patch_anm[name].read_bytes() if name in patch_anm else a.read(name)
            new_anm, done = bake_anm_textures(src_anm, patch_pngs, name)
            blob = resource_crypt(cpp_lzss(new_anm), CIPHERS[sum(name.encode()) & 7], encrypt=True)
            size, comp = len(new_anm), len(blob)
            if done: report.append(f'{name}: {len(done)} 贴图')
            elif name in patch_anm: report.append(f'{name}: 整文件替换 无贴图命中')
        elif not os.environ.get('BAKE_NO_MSG') and name.endswith('.msg') and (PATCH.parent.parent / 'patched-msg' or True) and name in {q.name: q for q in pathlib.Path(r'C:/touhou15-web-port/dl/patched-msg').glob('*.msg')}:
            raw = (pathlib.Path(r'C:/touhou15-web-port/dl/patched-msg') / name).read_bytes()
            blob = resource_crypt(cpp_lzss(raw), CIPHERS[sum(name.encode()) & 7], encrypt=True)
            size, comp = len(raw), len(blob); report.append(f'msg {name}')
        elif not os.environ.get('BAKE_NO_TEX') and name.endswith('.png') and name in patch_pngs:
            raw = patch_pngs[name].read_bytes()
            orig = a.read(name)
            assert orig[:8] == b'\x89PNG\r\n\x1a\n', name
            blob = resource_crypt(cpp_lzss(raw), CIPHERS[sum(name.encode()) & 7], encrypt=True)
            size, comp = len(raw), len(blob); report.append(f'png {name}')
        else:
            blob = a.data[e['offset']:e['offset'] + e['compressed']]
            size, comp = e['size'], e['compressed']
        rows.append((name, 16 + len(body), size, e['reserved'], comp))
        assert len(blob) == comp, (name, len(blob), comp)
        body += blob
    table = bytearray()
    for name, off, size, rsv, comp in rows:
        table += name.encode('ascii') + b'\x00'
        while len(table) % 4: table.append(0)
        table += struct.pack('<III', off, size, rsv)
    assert len(table) == a.unpacked
    pt = cpp_lzss(bytes(table))
    et = resource_crypt(pt, (62, 155, 128, len(pt)), encrypt=True)
    hs = struct.pack('<4sIII', b'THA1', (a.unpacked + 123456789) & 0xFFFFFFFF, (len(pt) + 987654321) & 0xFFFFFFFF, (a.count + 135792468) & 0xFFFFFFFF)
    open(DST, 'wb').write(resource_crypt(hs, (27, 55, 16, 16), encrypt=True) + bytes(body) + et)
    print('\n'.join(report))
    print('full dat 完成', DST, 16 + len(body) + len(et), '字节')

if __name__ == '__main__':
    main()
