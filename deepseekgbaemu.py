# gba_emu.py
import tkinter as tk
from tkinter import filedialog
import struct

class GBACPU:
    def __init__(self):
        self.registers = [0] * 16  # ARM7 registers
        self.cpsr = 0  # Current Program Status Register
        self.memory = bytearray(0x1000000)  # 16MB GBA memory
        
    def reset(self):
        self.registers = [0] * 16
        self.cpsr = 0x1F  # System mode
        self.pc = 0x08000000  # Typical ROM entry point

class GBAEmulator:
    def __init__(self, root):
        self.root = root
        self.cpu = GBACPU()
        self.setup_gui()
        
    def setup_gui(self):
        self.root.title("PyGBA 0.1")
        self.root.geometry("600x400")
        
        # Display canvas (240x160 scaled to 480x320)
        self.canvas = tk.Canvas(self.root, width=600, height=400, bg='black')
        self.canvas.pack()
        
        # Menu
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open ROM", command=self.load_rom)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)
        
        # Input handling
        self.keys = {'a':0, 'b':0, 'left':0, 'right':0, 'up':0, 'down':0}
        self.root.bind('<KeyPress>', self.key_down)
        self.root.bind('<KeyRelease>', self.key_up)
        
    def key_down(self, event):
        key = event.keysym.lower()
        if key in self.keys:
            self.keys[key] = 1
            
    def key_up(self, event):
        key = event.keysym.lower()
        if key in self.keys:
            self.keys[key] = 0
            
    def load_rom(self):
        rom_path = filedialog.askopenfilename(filetypes=[("GBA ROMs", "*.gba")])
        if rom_path:
            with open(rom_path, 'rb') as f:
                rom_data = f.read()
                self.load_rom_into_memory(rom_data)
            self.start_emulation()
            
    def load_rom_into_memory(self, rom_data):
        # Copy ROM to memory (simplified)
        rom_size = len(rom_data)
        self.cpu.memory[0x08000000:0x08000000+rom_size] = rom_data
        self.cpu.reset()
            
    def start_emulation(self):
        self.running = True
        self.emulation_loop()
            
    def emulation_loop(self):
        if self.running:
            self.execute_frame()
            self.root.after(16, self.emulation_loop)  # ~60fps
            
    def execute_frame(self):
        # Simplified: execute 280896 cycles (1 frame @ 16.78MHz)
        for _ in range(280896 // 10):  # Reduced for demo
            self.execute_instruction()
        self.update_display()
            
    def execute_instruction(self):
        # Basic ARM instruction fetch (simplified)
        pc = self.cpu.registers[15]
        opcode = struct.unpack('<I', bytes(self.cpu.memory[pc:pc+4]))[0]
        self.cpu.registers[15] += 4
        
        # Basic NOP implementation
        if opcode == 0xE1A00000:  # MOV r0, r0
            pass  # Do nothing
            
    def update_display(self):
        # Simple display test pattern
        self.canvas.delete('all')
        for y in range(160):
            for x in range(240):
                color = '#{:02x}{:02x}{:02x}'.format(
                    (x*255)//240, 
                    (y*255)//160, 
                    128
                )
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
