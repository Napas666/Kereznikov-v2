"""
Kereznikov v.2 — CS 1.6 hack
"""
import struct, math, threading, time, os
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

def attach():
    global pm, hw, cl, ok, cs_pid
    try:
        pm     = pymem.Pymem("cs.exe")
        cs_pid = pm.process_id
        hw = pymem.process.module_from_name(pm.process_handle, "hw.dll").lpBaseOfDll
        cl = pymem.process.module_from_name(pm.process_handle, "client.dll").lpBaseOfDll
        ok = True; return True, "OK"
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
def wf(a,v):
    try: pm.write_float(a, v)
    except: pass
def rstr(a):
    try: return pm.read_bytes(a,44).split(b'\x00')[0].decode('utf-8','ignore').strip()
    except: return ""

def get_angles(): return rv3(hw + VA)

# Пишем в ОБА адреса — hw.dll и client.dll
def set_angles(p, y):
    for addr in (hw+VA, cl+0x12EAF0, cl+0x12D9F0):
        wf(addr,   p)
        wf(addr+4, y)
        wf(addr+8, 0.)

def is_ground():  return ri(hw + ONGRND) == 1

def get_entities():
    """Возвращает все entity с именем и позицией."""
    out = []
    for i in range(0, 33):
        n = rstr(hw + ELIST + i*ESIZE + ENAME)
        if not n: continue
        p = rv3(hw + ELIST + i*ESIZE + EPOS)
        out.append((i, n, p))
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

# ── СОСТОЯНИЕ ─────────────────────────────────────────────
S   = {'aim': False, 'bhop': False, 'esp': False}
CFG = {'strength': 8., 'head': True}
CS_W, CS_H = 1280, 720

# debug info для UI
dbg_info = {"my": (0,0,0), "bots": 0, "nearest": "—"}

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
    if -200<sx<sw+200 and -200<sy_<sh+200: return sx,sy_,f
    return None

# ── AIMBOT ────────────────────────────────────────────────
def aim_loop():
    while True:
        if S['aim'] and ok:
            try:
                ents = get_entities()
                if not ents:
                    time.sleep(0.05); continue

                ca = get_angles()

                # Находим себя: entity чьё имя встречается только один раз
                # или просто берём index 1 (стандарт для CS)
                my_idx  = 1
                my_name = rstr(hw + ELIST + my_idx*ESIZE + ENAME)
                my_pos  = rv3(hw + ELIST + my_idx*ESIZE + EPOS)
                dbg_info["my"] = my_pos

                enemies = [(i,n,p) for i,n,p in ents if i != my_idx and n != my_name]
                dbg_info["bots"] = len(enemies)

                if not enemies:
                    time.sleep(0.05); continue

                # Экранный подход: project → двигаем мышь к центру
                cx, cy = CS_W//2, CS_H//2
                best_dx = best_dy = None
                best_d  = float('inf')

                for _, name, pos in enemies:
                    tz  = pos[2] + (64. if CFG['head'] else 0.)
                    rel = (pos[0]-my_pos[0], pos[1]-my_pos[1], tz-my_pos[2])
                    pr  = w2s(rel, ca, CS_W, CS_H)
                    if not pr: continue
                    sx, sy, dist = pr
                    d = math.hypot(sx-cx, sy-cy)
                    # Только если в разумной зоне экрана
                    if d < best_d and d < CS_W * 0.6:
                        best_d  = d
                        best_dx = sx - cx
                        best_dy = sy - cy
                        dbg_info["nearest"] = f"{name} d={int(d)}px"

                if best_dx is not None:
                    k = CFG['strength'] * 0.05
                    move_mouse(
                        max(-60, min(60, best_dx * k)),
                        max(-60, min(60, best_dy * k))
                    )
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
esp_status = ["Ожидание..."]

def find_cs_hwnd():
    try:
        import win32gui, win32process
        found=[]
        def cb(hwnd,_):
            if not win32gui.IsWindowVisible(hwnd): return
            try:
                _,pid=win32process.GetWindowThreadProcessId(hwnd)
                if pid==cs_pid:
                    rc=win32gui.GetWindowRect(hwnd)
                    if rc[2]-rc[0]>200: found.append(hwnd)
            except: pass
        win32gui.EnumWindows(cb,None)
        return found[0] if found else 0
    except: return 0

def esp_loop():
    try:
        import pygame,win32gui,win32con,win32api
    except ImportError as e:
        esp_status[0]=f"Нет: {e}"; return

    pygame.init(); pygame.font.init()
    while not ok: time.sleep(1)

    esp_status[0]="Ищу окно CS..."
    cs_hwnd=0
    for _ in range(20):
        cs_hwnd=find_cs_hwnd()
        if cs_hwnd: break
        time.sleep(1)
    if not cs_hwnd:
        esp_status[0]="Окно не найдено"; return

    esp_status[0]="Перевожу в оконный режим..."
    try:
        import win32con
        style=win32gui.GetWindowLong(cs_hwnd,win32con.GWL_STYLE)
        style=(style&~win32con.WS_POPUP)|win32con.WS_OVERLAPPEDWINDOW
        win32gui.SetWindowLong(cs_hwnd,win32con.GWL_STYLE,style)
        win32gui.SetWindowPos(cs_hwnd,win32con.HWND_TOP,50,50,1280,720,
            win32con.SWP_FRAMECHANGED|win32con.SWP_SHOWWINDOW)
    except: pass
    time.sleep(0.8)

    rc=win32gui.GetWindowRect(cs_hwnd)
    W,H=rc[2]-rc[0],rc[3]-rc[1]
    global CS_W,CS_H; CS_W,CS_H=W,H

    os.environ['SDL_VIDEO_WINDOW_POS']=f"{rc[0]},{rc[1]}"
    sc=pygame.display.set_mode((W,H),pygame.NOFRAME|pygame.SRCALPHA)
    pygame.display.set_caption("__ov__")
    ow=pygame.display.get_wm_info()['window']
    ex=win32gui.GetWindowLong(ow,win32con.GWL_EXSTYLE)
    win32gui.SetWindowLong(ow,win32con.GWL_EXSTYLE,
        ex|win32con.WS_EX_LAYERED|win32con.WS_EX_TRANSPARENT|win32con.WS_EX_TOPMOST)
    win32gui.SetLayeredWindowAttributes(ow,win32api.RGB(0,0,0),0,win32con.LWA_COLORKEY)
    win32gui.SetWindowPos(ow,win32con.HWND_TOPMOST,rc[0],rc[1],W,H,0)

    fnt=pygame.font.SysFont("Arial",11,bold=True)
    clk=pygame.time.Clock()
    esp_status[0]=f"ESP OK {W}x{H}"

    while True:
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: return
        sc.fill((0,0,0))

        if S['esp'] and ok:
            try:
                ents=get_entities()
                my_idx=1
                my_name=rstr(hw+ELIST+my_idx*ESIZE+ENAME)
                my_pos=rv3(hw+ELIST+my_idx*ESIZE+EPOS)
                ang=get_angles()

                for i,name,pos in ents:
                    if i==my_idx or name==my_name: continue
                    rel=(pos[0]-my_pos[0],pos[1]-my_pos[1],pos[2]-my_pos[2]+36)
                    pr=w2s(rel,ang,W,H)
                    if not pr: continue
                    sx,sy,dist=pr
                    bh=max(14,int(1400/max(dist,1))); bw=max(8,bh//2)
                    x1,y1=sx-bw//2,sy-bh
                    s2=pygame.Surface((bw,bh),pygame.SRCALPHA)
                    s2.fill((255,50,50,20))
                    pygame.draw.rect(s2,(255,50,50,255),(0,0,bw,bh),2)
                    sc.blit(s2,(x1,y1))
                    pygame.draw.line(sc,(180,50,255),(W//2,H),(sx,sy),1)
                    t=fnt.render(f"{name[:10]} {int(dist)}u",True,(255,255,100))
                    sc.blit(t,(sx-t.get_width()//2,sy+2))
            except: pass

        pygame.display.flip(); clk.tick(60)

threading.Thread(target=aim_loop,  daemon=True).start()
threading.Thread(target=bhop_loop, daemon=True).start()
threading.Thread(target=esp_loop,  daemon=True).start()

# ── Авто-подключение ──────────────────────────────────────
def auto_attach(dot_lbl, status_lbl):
    while not ok:
        res,_=attach()
        if res:
            dot_lbl.configure(text_color="#4f8")
            status_lbl.configure(text="ATTACHED")
        else:
            dot_lbl.configure(text_color="#fa0")
            status_lbl.configure(text="Жду CS...")
            time.sleep(2)

# ── UI ────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
AC="#c850ff"; BG="#0d0d0d"; C1="#161616"; C2="#1a1a1a"
root=ctk.CTk()
root.title("Kereznikov v.2"); root.geometry("340x600")
root.resizable(False,False); root.configure(fg_color=BG)

hdr=ctk.CTkFrame(root,fg_color=C1,corner_radius=0,height=50); hdr.pack(fill="x")
ctk.CTkLabel(hdr,text="KEREZNIKOV v.2",font=("Arial",15,"bold"),text_color=AC).pack(side="left",padx=14,pady=12)
dot=ctk.CTkLabel(hdr,text="●",font=("Arial",18),text_color="#fa0"); dot.pack(side="right",padx=12)
slbl=ctk.CTkLabel(hdr,text="Жду CS...",font=("Arial",10),text_color="#fa0"); slbl.pack(side="right")

# Дебаг — показывает что реально читается
dbg1=ctk.CTkLabel(root,text="angles: p=-- y=--",font=("Courier",9),text_color="#333"); dbg1.pack()
dbg2=ctk.CTkLabel(root,text="my_pos: x=-- y=-- z=--",font=("Courier",9),text_color="#333"); dbg2.pack()
dbg3=ctk.CTkLabel(root,text="bots=-- nearest=--",font=("Courier",9),text_color="#333"); dbg3.pack()
dbg4=ctk.CTkLabel(root,text="esp: --",font=("Courier",9),text_color="#333"); dbg4.pack(pady=(0,4))

def make_btn(lbl,key,col):
    btn=ctk.CTkButton(root,text=f"◯  {lbl}  —  ВЫКЛ",
                      fg_color=C2,hover_color="#222",border_color="#333",border_width=1,
                      font=("Arial",13,"bold"),height=46,corner_radius=8,text_color="#555")
    def click():
        S[key]=not S[key]
        if S[key]: btn.configure(text=f"●  {lbl}  —  ВКЛ", fg_color="#1e1040",border_color=col,text_color=col)
        else:      btn.configure(text=f"◯  {lbl}  —  ВЫКЛ",fg_color=C2,border_color="#333",text_color="#555")
    btn.configure(command=click); btn.pack(fill="x",padx=14,pady=3)

make_btn("AIMBOT",       "aim",  AC)
make_btn("WALLHACK/ESP", "esp",  "#ff5050")
make_btn("BHOP",         "bhop", "#50ffaa")

# Слайдер силы
f=ctk.CTkFrame(root,fg_color=C1,corner_radius=10); f.pack(fill="x",padx=14,pady=4)
r=ctk.CTkFrame(f,fg_color="transparent"); r.pack(fill="x",padx=12,pady=(8,0))
ctk.CTkLabel(r,text="СИЛА",font=("Arial",11,"bold"),text_color="#ccc").pack(side="left")
vl=ctk.CTkLabel(r,text="8",font=("Arial",11,"bold"),text_color=AC); vl.pack(side="right")
ctk.CTkLabel(f,text="Медленно ← 1 ─────── 30 → Резко",font=("Arial",9),text_color="#444").pack(anchor="w",padx=12)
def _sf(v): vl.configure(text=f"{int(v)}"); CFG.update({'strength':float(v)})
sl=ctk.CTkSlider(f,from_=1,to=30,command=_sf,button_color=AC,progress_color=AC)
sl.set(8); sl.pack(fill="x",padx=12,pady=(2,10))

# Цель
tf=ctk.CTkFrame(root,fg_color=C1,corner_radius=10); tf.pack(fill="x",padx=14,pady=4)
tr=ctk.CTkFrame(tf,fg_color="transparent"); tr.pack(fill="x",padx=12,pady=10)
ctk.CTkLabel(tr,text="ЦЕЛЬ",font=("Arial",11,"bold"),text_color="#ccc").pack(side="left")
tb=ctk.CTkSegmentedButton(tr,values=["ГОЛОВА","ТЕЛО"],
    command=lambda v:CFG.update({'head':v=="ГОЛОВА"}),
    selected_color="#2a1040",unselected_color=C2,font=("Arial",11,"bold"))
tb.set("ГОЛОВА"); tb.pack(side="right")

threading.Thread(target=auto_attach,args=(dot,slbl),daemon=True).start()

def tick():
    if ok:
        try:
            p,y,_=get_angles()
            dbg1.configure(text=f"angles: p={p:.1f} y={y:.1f}",text_color="#555")
            mx,my_,mz=dbg_info["my"]
            dbg2.configure(text=f"my_pos: x={mx:.0f} y={my_:.0f} z={mz:.0f}",text_color="#555")
            dbg3.configure(text=f"bots={dbg_info['bots']} near={dbg_info['nearest']}",text_color="#555")
        except: pass
    dbg4.configure(text=f"esp: {esp_status[0]}",text_color="#444")
    root.after(200,tick)

tick()
root.mainloop()
