"""
Kereznikov v.2 — CS 1.6 hack
- Автоматическое подключение к CS
- Автоматический поиск окна CS по процессу (не по заголовку)
- Автоматический перевод CS в оконный режим для ESP
- ESP через все стены
- AIM через мышь
"""
import struct, math, threading, time, os, sys
import pymem, pymem.process
import customtkinter as ctk

# ── ОФФСЕТЫ build 8684 ───────────────────────────────────
VA     = 0x1230274
ELIST  = 0x12043C8
ESIZE  = 0x250
ENAME  = 0x104
EPOS   = 0x188
ONGRND = 0x122E2D4
FJUMP  = 0x131434

pm = None; hw = cl = 0; ok = False; cs_pid = 0

# ── ПАМЯТЬ ────────────────────────────────────────────────
def attach():
    global pm, hw, cl, ok, cs_pid
    try:
        pm     = pymem.Pymem("cs.exe")
        cs_pid = pm.process_id
        hw     = pymem.process.module_from_name(pm.process_handle, "hw.dll").lpBaseOfDll
        cl     = pymem.process.module_from_name(pm.process_handle, "client.dll").lpBaseOfDll
        ok     = True
        return True, "OK"
    except Exception as e:
        ok = False; return False, str(e)

def rv3(a):
    try: return struct.unpack('fff', pm.read_bytes(a, 12))
    except: return (0.,0.,0.)
def ri(a):
    try: return pm.read_int(a)
    except: return 0
def wi(a,v):
    try: pm.write_int(a, v)
    except: pass
def rstr(a):
    try: return pm.read_bytes(a,44).split(b'\x00')[0].decode('utf-8','ignore').strip()
    except: return ""

def get_angles(): return rv3(hw + VA)
def is_ground():  return ri(hw + ONGRND) == 1
def my_pos():     return rv3(hw + ELIST + ESIZE + EPOS)

def get_bots():
    me = rstr(hw + ELIST + ESIZE + ENAME)
    out = []
    for i in range(1, 33):
        n = rstr(hw + ELIST + i*ESIZE + ENAME)
        if not n or n == me: continue
        p = rv3(hw + ELIST + i*ESIZE + EPOS)
        if p != (0.,0.,0.): out.append(p)
    return out

def norm(a):
    while a >  180: a -= 360
    while a < -180: a += 360
    return a

def move_mouse(dx, dy):
    try:
        import win32api, win32con
        if abs(dx) > 0.3 or abs(dy) > 0.3:
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)
    except: pass

def w2s(rel, ang, sw, sh):
    p,y = math.radians(ang[0]), math.radians(ang[1])
    cp,sp,cy,sy = math.cos(p),math.sin(p),math.cos(y),math.sin(y)
    fwd=(cp*cy,cp*sy,-sp); right=(sy,-cy,0); up=(sp*cy,sp*sy,cp)
    dx,dy,dz = rel
    f=dx*fwd[0]+dy*fwd[1]+dz*fwd[2]
    r=dx*right[0]+dy*right[1]+dz*right[2]
    u=dx*up[0]+dy*up[1]+dz*up[2]
    if f < 0.1: return None
    sc=sw/(2*math.tan(math.radians(45)))
    sx,sy_=int(sw/2+r/f*sc),int(sh/2-u/f*sc)
    if -400<sx<sw+400 and -400<sy_<sh+400: return sx,sy_,f
    return None

# ── Найти окно CS по PID ──────────────────────────────────
def find_cs_hwnd():
    try:
        import win32gui, win32process
        found = []
        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd): return
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid == cs_pid:
                    rc = win32gui.GetWindowRect(hwnd)
                    w,h = rc[2]-rc[0], rc[3]-rc[1]
                    if w > 200 and h > 200:
                        found.append(hwnd)
            except: pass
        win32gui.EnumWindows(cb, None)
        return found[0] if found else 0
    except: return 0

# ── Перевести CS в оконный режим автоматически ───────────
def make_windowed(hwnd, w=1280, h=720):
    try:
        import win32gui, win32con
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        # Убираем полноэкранный стиль, добавляем оконный
        style = (style & ~(win32con.WS_POPUP)) | win32con.WS_OVERLAPPEDWINDOW
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 50, 50, w, h,
            win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)
        return True
    except: return False

# ── СОСТОЯНИЕ ─────────────────────────────────────────────
S   = {'aim': False, 'bhop': False, 'esp': False}
CFG = {'fov': 180., 'strength': 12., 'head': True}

# ── AIMBOT ────────────────────────────────────────────────
def aim_loop():
    while True:
        if S['aim'] and ok:
            try:
                ca=get_angles(); src=my_pos(); bots=get_bots()
                best=None; best_d=CFG['fov']
                for pos in bots:
                    tz=pos[2]+(64. if CFG['head'] else 0.)
                    dx,dy,dz=pos[0]-src[0],pos[1]-src[1],tz-src[2]
                    ta=(-math.degrees(math.atan2(dz,math.hypot(dx,dy))),
                         math.degrees(math.atan2(dy,dx)))
                    d=math.hypot(norm(ca[0]-ta[0]),norm(ca[1]-ta[1]))
                    if d<best_d: best_d,best=d,ta
                if best:
                    dp=norm(best[0]-ca[0]); dy_=norm(best[1]-ca[1])
                    k=CFG['strength']
                    move_mouse(max(-120,min(120,dy_*k)),
                               max(-120,min(120,-dp*k)))
            except: pass
        time.sleep(0.008)

# ── BHOP ──────────────────────────────────────────────────
def bhop_loop():
    air=False
    while True:
        if S['bhop'] and ok:
            try:
                gnd=is_ground()
                if not gnd: wi(cl+FJUMP,5); air=True
                elif air:   wi(cl+FJUMP,0); air=False
            except: pass
        time.sleep(0.005)

# ── ESP ───────────────────────────────────────────────────
esp_status = ["Ожидание CS..."]

def esp_loop():
    try:
        import pygame, win32gui, win32con, win32api
    except ImportError as e:
        esp_status[0] = f"Нет библиотеки: {e}"; return

    pygame.init(); pygame.font.init()

    # Ждём пока CS запустится и мы подключимся
    while not ok: time.sleep(1)

    esp_status[0] = "Ищу окно CS..."

    cs_hwnd = 0
    for _ in range(20):
        cs_hwnd = find_cs_hwnd()
        if cs_hwnd: break
        time.sleep(1)

    if not cs_hwnd:
        esp_status[0] = "Окно CS не найдено"; return

    esp_status[0] = "Перевожу в оконный режим..."
    make_windowed(cs_hwnd, 1280, 720)
    time.sleep(0.8)

    # Перечитываем позицию окна после изменения
    rc  = win32gui.GetWindowRect(cs_hwnd)
    W,H = rc[2]-rc[0], rc[3]-rc[1]

    os.environ['SDL_VIDEO_WINDOW_POS'] = f"{rc[0]},{rc[1]}"
    sc = pygame.display.set_mode((W,H), pygame.NOFRAME|pygame.SRCALPHA)
    pygame.display.set_caption("__ov__")

    ow = pygame.display.get_wm_info()['window']
    ex = win32gui.GetWindowLong(ow, win32con.GWL_EXSTYLE)
    win32gui.SetWindowLong(ow, win32con.GWL_EXSTYLE,
        ex|win32con.WS_EX_LAYERED|win32con.WS_EX_TRANSPARENT|win32con.WS_EX_TOPMOST)
    win32gui.SetLayeredWindowAttributes(ow, win32api.RGB(0,0,0), 0, win32con.LWA_COLORKEY)
    win32gui.SetWindowPos(ow, win32con.HWND_TOPMOST, rc[0],rc[1],W,H,0)

    fnt = pygame.font.SysFont("Arial", 11, bold=True)
    clk = pygame.time.Clock()
    esp_status[0] = f"ESP активен {W}x{H}"

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: return
        sc.fill((0,0,0))

        if S['esp'] and ok:
            try:
                # Обновляем позицию оверлея если окно переместилось
                rc2 = win32gui.GetWindowRect(cs_hwnd)
                if (rc2[0],rc2[1]) != (rc[0],rc[1]):
                    rc=rc2
                    win32gui.SetWindowPos(ow, win32con.HWND_TOPMOST,
                        rc[0],rc[1],W,H,0)

                mp=my_pos(); ang=get_angles()
                for pos in get_bots():
                    rel=(pos[0]-mp[0],pos[1]-mp[1],pos[2]-mp[2]+36)
                    pr=w2s(rel,ang,W,H)
                    if not pr: continue
                    sx,sy,dist=pr
                    bh=max(14,int(1400/max(dist,1))); bw=max(8,bh//2)
                    x1,y1=sx-bw//2,sy-bh
                    # Бокс
                    s2=pygame.Surface((bw,bh),pygame.SRCALPHA)
                    s2.fill((255,50,50,20))
                    pygame.draw.rect(s2,(255,50,50,255),(0,0,bw,bh),2)
                    sc.blit(s2,(x1,y1))
                    # Линия к боту
                    pygame.draw.line(sc,(180,50,255),(W//2,H),(sx,sy),1)
                    # Дистанция
                    dt=fnt.render(f"{int(dist)}u",True,(255,255,100))
                    sc.blit(dt,(sx-dt.get_width()//2,sy+2))
            except: pass

        pygame.display.flip()
        clk.tick(60)

# ── Авто-подключение ──────────────────────────────────────
def auto_attach(dot_lbl, status_lbl, dbg_lbl):
    while not ok:
        res, msg = attach()
        if res:
            dot_lbl.configure(text_color="#4f8")
            status_lbl.configure(text="ATTACHED")
        else:
            dot_lbl.configure(text_color="#fa0")
            status_lbl.configure(text="Жду CS...")
            time.sleep(2)

threading.Thread(target=aim_loop,  daemon=True).start()
threading.Thread(target=bhop_loop, daemon=True).start()
threading.Thread(target=esp_loop,  daemon=True).start()

# ── UI ────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
AC="#c850ff"; BG="#0d0d0d"; C1="#161616"; C2="#1a1a1a"

root = ctk.CTk()
root.title("Kereznikov v.2"); root.geometry("340x580")
root.resizable(False,False); root.configure(fg_color=BG)

hdr = ctk.CTkFrame(root, fg_color=C1, corner_radius=0, height=50)
hdr.pack(fill="x")
ctk.CTkLabel(hdr,text="KEREZNIKOV v.2",font=("Arial",15,"bold"),text_color=AC).pack(side="left",padx=14,pady=12)
dot  = ctk.CTkLabel(hdr,text="●",font=("Arial",18),text_color="#fa0"); dot.pack(side="right",padx=12)
slbl = ctk.CTkLabel(hdr,text="Жду CS...",font=("Arial",10),text_color="#fa0"); slbl.pack(side="right")

dbg = ctk.CTkLabel(root,text="p=--  y=--  bots=--",font=("Courier",10),text_color="#444")
dbg.pack(pady=4)

esp_lbl = ctk.CTkLabel(root,text="ESP: ожидание...",font=("Arial",10),text_color="#555")
esp_lbl.pack(pady=0)

def make_btn(lbl, key, col):
    btn = ctk.CTkButton(root,text=f"◯  {lbl}  —  ВЫКЛ",
                        fg_color=C2,hover_color="#222",
                        border_color="#333",border_width=1,
                        font=("Arial",13,"bold"),height=46,
                        corner_radius=8,text_color="#555")
    def click():
        S[key]=not S[key]
        if S[key]: btn.configure(text=f"●  {lbl}  —  ВКЛ", fg_color="#1e1040",border_color=col,text_color=col)
        else:      btn.configure(text=f"◯  {lbl}  —  ВЫКЛ",fg_color=C2,border_color="#333",text_color="#555")
    btn.configure(command=click)
    btn.pack(fill="x",padx=14,pady=3)

make_btn("AIMBOT",       "aim",  AC)
make_btn("WALLHACK/ESP", "esp",  "#ff5050")
make_btn("BHOP",         "bhop", "#50ffaa")

def sld(lbl, hint, mn, mx, df, cb, fmt=lambda v:f"{int(v)}"):
    f=ctk.CTkFrame(root,fg_color=C1,corner_radius=10); f.pack(fill="x",padx=14,pady=3)
    r=ctk.CTkFrame(f,fg_color="transparent"); r.pack(fill="x",padx=12,pady=(8,0))
    ctk.CTkLabel(r,text=lbl,font=("Arial",11,"bold"),text_color="#ccc").pack(side="left")
    vl=ctk.CTkLabel(r,text=fmt(df),font=("Arial",11,"bold"),text_color=AC); vl.pack(side="right")
    ctk.CTkLabel(f,text=hint,font=("Arial",9),text_color="#444").pack(anchor="w",padx=12)
    def _cb(v): vl.configure(text=fmt(float(v))); cb(float(v))
    sl=ctk.CTkSlider(f,from_=mn,to=mx,command=_cb,button_color=AC,progress_color=AC)
    sl.set(df); sl.pack(fill="x",padx=12,pady=(2,10))

sld("СИЛА АИМ","Медленно ← 1 ──── 30 → Резко",
    1,30,12,lambda v:CFG.update({'strength':v}))
sld("FOV","Узко ← 5 ───── 180 → Везде",
    5,180,180,lambda v:CFG.update({'fov':v}),lambda v:f"{int(v)}°")

tf=ctk.CTkFrame(root,fg_color=C1,corner_radius=10); tf.pack(fill="x",padx=14,pady=3)
tr=ctk.CTkFrame(tf,fg_color="transparent"); tr.pack(fill="x",padx=12,pady=10)
ctk.CTkLabel(tr,text="ЦЕЛЬ",font=("Arial",11,"bold"),text_color="#ccc").pack(side="left")
tb=ctk.CTkSegmentedButton(tr,values=["ГОЛОВА","ТЕЛО"],
    command=lambda v:CFG.update({'head':v=="ГОЛОВА"}),
    selected_color="#2a1040",unselected_color=C2,font=("Arial",11,"bold"))
tb.set("ГОЛОВА"); tb.pack(side="right")

# Авто-подключение в фоне
threading.Thread(target=auto_attach, args=(dot, slbl, dbg), daemon=True).start()

def tick():
    if ok:
        try:
            p,y,_=get_angles(); b=get_bots()
            st=" ►AIM" if S['aim'] and b else ""
            dbg.configure(text=f"p={p:.1f} y={y:.1f} bots={len(b)}{st}",text_color="#555")
        except: pass
    esp_lbl.configure(text=f"ESP: {esp_status[0]}")
    root.after(200, tick)

tick()
root.mainloop()
