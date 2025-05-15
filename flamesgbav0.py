# gba_emu.py
import tkinter as tk
from tkinter import filedialog
import struct
import time

class ARM7TDMI:
    def __init__(self):
        self.reg = [0]*16  # R0-R15
        self.cpsr = 0x1F  # System mode
        self.memory = bytearray(0x1000000)  # 16MB address space
        self.thumb_mode = False
        
    def execute(self):
        pc = self.reg[15]
        if self.thumb_mode:
            opcode = struct.unpack('<H', self.memory[pc:pc+2])[0]
            self.reg[15] += 2
            self.execute_thumb(opcode)
        else:
            opcode = struct.unpack('<I', self.memory[pc:pc+4])[0]
            self.reg[15] += 4
            self.execute_arm(opcode)
    
    def execute_arm(self, opcode):
        # Partial ARM instruction decoding
        cond = (opcode >> 28) & 0xF
        if not self.check_cond(cond):
            return
            
        op = (opcode >> 24) & 0xF
        if op == 0b1010:  # Branch instruction
            offset = opcode & 0x00FFFFFF
            if offset & 0x00800000:  # Sign extend
                offset |= 0xFF000000
            self.reg[15] += offset * 4
    
    def execute_thumb(self, opcode):
        # Partial THUMB instruction support
        pass
    
    def check_cond(self, cond):
        # Simplified condition check
        return True  # Always execute for demo

class PPU:
    def __init__(self, memory):
        self.vram = memory[0x06000000:0x06018000]
        self.palette = memory[0x05000000:0x05000400]
        
    def render_frame(self):
        # Mode 3 (240x160 15bpp) rendering
        pixels = []
        for i in range(0, 240*160*2, 2):
            color = self.vram[i] | (self.vram[i+1] << 8)
            r = (color & 0x1F) << 3
            g = ((color >> 5) & 0x1F) << 3
            b = ((color >> 10) & 0x1F) << 3
            pixels.append(f"#{r:02x}{g:02x}{b:02x}")
        return pixels

class GBAEmulator:
    def __init__(self, root):
        self.root = root
        self.cpu = ARM7TDMI()
        self.ppu = PPU(self.cpu.memory)
        self.setup_gui()
        self.frame_time = time.time()
        
    def setup_gui(self):
        self.root.title("PyGBA 0.2")
        self.root.geometry("600x400")
        
        self.canvas = tk.Canvas(self.root, width=600, height=400, bg='black')
        self.canvas.pack()
        
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open ROM", command=self.load_rom)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)
        
        self.keys = {'a':0, 'b':0, 'left':0, 'right':0, 'up':0, 'down':0}
        self.root.bind('<KeyPress>', self.key_down)
        self.root.bind('<KeyRelease>', self.key_up)
        
    def key_down(self, event):
        key = event.keysym.lower()
        if key in self.keys:
            self.keys[key] = 1
        self.update_key_status()
            
    def update_key_status(self):
        # Map keys to GBA input register (0x04000130)
        key_bits = 0
        key_bits |= self.keys['a'] << 0
        key_bits |= self.keys['b'] << 1
        key_bits |= self.keys['left'] << 5
        key_bits |= self.keys['right'] << 4
        key_bits |= self.keys['up'] << 6
        key_bits |= self.keys['down'] << 7
        self.cpu.memory[0x04000130] = ~key_bits & 0xFF
            
    def load_rom(self):
        rom_path = filedialog.askopenfilename(filetypes=[("GBA ROMs", "*.gba")])
        if rom_path:
            with open(rom_path, 'rb') as f:
                rom_data = f.read()
                self.cpu.memory[0x08000000:0x08000000+len(rom_data)] = rom_data
            self.cpu.reg[15] = 0x08000000  # Entry point
            self.start_emulation()
            
    def start_emulation(self):
        self.running = True
        self.emulation_loop()
            
    def emulation_loop(self):
        if self.running:
            now = time.time()
            delta = now - self.frame_time
            if delta >= 1/60:  # 60Hz refresh
                self.execute_frame()
                self.frame_time = now
            self.root.after(1, self.emulation_loop)
            
    def execute_frame(self):
        # Execute ~280,896 cycles (16.78MHz / 60)
        for _ in range(280896 // 100):  # Reduced for demo
            self.cpu.execute()
        self.update_display()
            
    def update_display(self):
        pixels = self.ppu.render_frame()
        self.canvas.delete('all')
        for y in range(160):
            for x in range(240):
                color = pixels[y*240 + x]
                self.canvas.create_rectangle(
                    x*2.5, y*2.5, 
                    (x+1)*2.5, (y+1)*2.5, 
                    fill=color, 
                    outline=''
                )

if __name__ == '__main__':
    root = tk.Tk()
    emu = GBAEmulator(root)
    root.mainloop()
