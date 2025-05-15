#!/usr/bin/env python
# test.py - Test application for GBA emulator
# No PNG dependency, with vibe mode support

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import time
import sys
import os
import random
import struct

# Define GBA constants (replace with gba_emu_enhanced if available)
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 160
GAMEPAK_ROM_START = 0x08000000

# Stub ARM7TDMI class (replace with real import when available)
class ARM7TDMI:
    def __init__(self, memory):
        self.memory = memory
        self.registers = [0] * 16
        self.pc = GAMEPAK_ROM_START
        self.CPSR = 0x0000001F  # System mode, ARM state
        self.cycle_count = 0

    def reset(self):
        self.registers = [0] * 16
        self.pc = GAMEPAK_ROM_START
        self.CPSR = 0x0000001F

    def step(self):
        # Simulate a simple instruction fetch and increment
        self.registers[0] += 1  # For test ROM (ADD R0, R0, #1)
        self.pc += 4
        if self.pc >= GAMEPAK_ROM_START + 12:  # Loop back (B loop)
            self.pc = GAMEPAK_ROM_START + 4
        self.cycle_count += 1

    def get_reg(self, n):
        return self.registers[n]

    def get_pc(self):
        return self.pc

    def set_pc(self, addr):
        self.pc = addr

    def get_flag_N(self):
        return (self.CPSR >> 31) & 1

    def get_flag_Z(self):
        return (self.CPSR >> 30) & 1

    def get_flag_C(self):
        return (self.CPSR >> 29) & 1

    def get_flag_V(self):
        return (self.CPSR >> 28) & 1

    def get_flag_T(self):
        return (self.CPSR >> 5) & 1

    def get_current_mode(self):
        return self.CPSR & 0x1F

# Import check (remove if using real gba_emu_enhanced)
try:
    from gba_emu_enhanced import ARM7TDMI, SCREEN_WIDTH, SCREEN_HEIGHT, GAMEPAK_ROM_START
except ImportError:
    print("Warning: gba_emu_enhanced.py not found. Using stub ARM7TDMI and default constants.")

class MemoryManager:
    """Memory management for the GBA system"""
    def __init__(self):
        self.bios = bytearray(16 * 1024)
        self.ewram = bytearray(256 * 1024)
        self.iwram = bytearray(32 * 1024)
        self.io_regs = bytearray(1024)
        self.palette = bytearray(1024)
        self.vram = bytearray(96 * 1024)
        self.oam = bytearray(1024)
        self.rom = bytearray()
        self.sram = bytearray(64 * 1024)
        self.last_read_addr = 0
        self.last_write_addr = 0
        self.warnings = []

    def load_bios(self, data):
        if len(data) <= len(self.bios):
            self.bios[:len(data)] = data
            print(f"Loaded {len(data)} bytes of BIOS data")
        else:
            self.warnings.append(f"BIOS data too large ({len(data)} bytes), truncating")
            self.bios[:] = data[:len(self.bios)]

    def load_rom(self, data):
        self.rom = bytearray(data)
        print(f"Loaded {len(data)} bytes of ROM data")

    def map_address(self, addr):
        addr &= 0xFFFFFFFF
        if 0x00000000 <= addr < 0x00004000:
            return ("bios", addr)
        elif 0x02000000 <= addr < 0x02040000:
            return ("ewram", addr - 0x02000000)
        elif 0x03000000 <= addr < 0x03008000:
            return ("iwram", addr - 0x03000000)
        elif 0x04000000 <= addr < 0x04000400:
            return ("io_regs", addr - 0x04000000)
        elif 0x05000000 <= addr < 0x05000400:
            return ("palette", addr - 0x05000000)
        elif 0x06000000 <= addr < 0x06018000:
            return ("vram", addr - 0x06000000)
        elif 0x07000000 <= addr < 0x07000400:
            return ("oam", addr - 0x07000000)
        elif 0x08000000 <= addr < 0x08000000 + len(self.rom):
            return ("rom", addr - 0x08000000)
        elif 0x0E000000 <= addr < 0x0E010000:
            return ("sram", addr - 0x0E000000)
        else:
            self.warnings.append(f"Unmapped memory access at 0x{addr:08X}")
            return ("invalid", 0)

    def read_byte(self, addr):
        self.last_read_addr = addr
        region, offset = self.map_address(addr)
        if region == "invalid":
            return (addr >> 24) & 0xFF
        mem = getattr(self, region)
        if offset < len(mem):
            return mem[offset]
        self.warnings.append(f"Out of bounds read from {region} at offset 0x{offset:X}")
        return 0

    def read_halfword(self, addr):
        self.last_read_addr = addr
        if addr & 1:
            self.warnings.append(f"Unaligned halfword read at 0x{addr:08X}")
            addr &= ~1
        lo = self.read_byte(addr)
        hi = self.read_byte(addr + 1)
        return (hi << 8) | lo

    def read_word(self, addr):
        self.last_read_addr = addr
        if addr & 3:
            self.warnings.append(f"Unaligned word read at 0x{addr:08X}")
            rot = (addr & 3) * 8
            aligned_addr = addr & ~3
            val = (self.read_byte(aligned_addr) |
                   (self.read_byte(aligned_addr + 1) << 8) |
                   (self.read_byte(aligned_addr + 2) << 16) |
                   (self.read_byte(aligned_addr + 3) << 24))
            return ((val >> rot) | (val << (32 - rot))) & 0xFFFFFFFF
        b0 = self.read_byte(addr)
        b1 = self.read_byte(addr + 1)
        b2 = self.read_byte(addr + 2)
        b3 = self.read_byte(addr + 3)
        return (b3 << 24) | (b2 << 16) | (b1 << 8) | b0

    def write_byte(self, addr, value):
        self.last_write_addr = addr
        value &= 0xFF
        region, offset = self.map_address(addr)
        if region == "invalid":
            self.warnings.append(f"Write to invalid address 0x{addr:08X}")
            return
        if region == "rom":
            self.warnings.append(f"Attempt to write to ROM at 0x{addr:08X}")
            return
        if region == "bios":
            self.warnings.append(f"Attempt to write to BIOS at 0x{addr:08X}")
            return
        mem = getattr(self, region)
        if offset < len(mem):
            mem[offset] = value
        else:
            self.warnings.append(f"Out of bounds write to {region} at offset 0x{offset:X}")

    def write_halfword(self, addr, value):
        self.last_write_addr = addr
        value &= 0xFFFF
        if addr & 1:
            self.warnings.append(f"Unaligned halfword write at 0x{addr:08X}")
            addr &= ~1
        self.write_byte(addr, value & 0xFF)
        self.write_byte(addr + 1, (value >> 8) & 0xFF)

    def write_word(self, addr, value):
        self.last_write_addr = addr
        value &= 0xFFFFFFFF
        if addr & 3:
            self.warnings.append(f"Unaligned word write at 0x{addr:08X}")
            addr &= ~3
        self.write_byte(addr, value & 0xFF)
        self.write_byte(addr + 1, (value >> 8) & 0xFF)
        self.write_byte(addr + 2, (value >> 16) & 0xFF)
        self.write_byte(addr + 3, (value >> 24) & 0xFF)

class VibeModePalette:
    """Color palette manager for vibe mode"""
    def __init__(self, refresh_rate=5):
        self.palettes = {
            "synthwave": [
                "#ff00ff", "#00ffff", "#ff0099", "#9900ff",
                "#0099ff", "#ff9900", "#9900cc", "#cc0099"
            ],
            "retrowave": [
                "#fd3777", "#3636b2", "#2ce8f5", "#fafd0f",
                "#fa4e79", "#5555ff", "#44ffff", "#fcff44"
            ],
            "cyberpunk": [
                "#00FFFF", "#FF00FF", "#FFFF00", "#00FF00",
                "#FF0000", "#0000FF", "#FF8000", "#8000FF"
            ],
            "vaporwave": [
                "#91D5FF", "#FF9EEE", "#55FFFF", "#FFD4FF",
                "#FFA9F9", "#91FFFF", "#CEFCFF", "#FFCCFF"
            ]
        }
        self.current_palette = "synthwave"
        self.palette_idx = 0
        self.refresh_rate = refresh_rate
        self.frame_counter = 0

    def get_color(self):
        palette = self.palettes[self.current_palette]
        return palette[self.palette_idx]

    def update(self):
        self.frame_counter += 1
        if self.frame_counter >= self.refresh_rate:
            self.frame_counter = 0
            self.palette_idx = (self.palette_idx + 1) % len(self.palettes[self.current_palette])

    def cycle_palette(self):
        palettes = list(self.palettes.keys())
        current_idx = palettes.index(self.current_palette)
        next_idx = (current_idx + 1) % len(palettes)
        self.current_palette = palettes[next_idx]
        self.palette_idx = 0
        return self.current_palette

    def set_refresh_rate(self, rate):
        self.refresh_rate = max(1, int(rate))

class GBAEmulatorApp:
    """Main application for testing the GBA emulator"""
    def __init__(self, root):
        self.root = root
        self.root.title("MEOWTASTIC GBA Emulator Test")
        self.root.geometry(f"{SCREEN_WIDTH*2}x{SCREEN_HEIGHT*2 + 200}")
        self.running = False
        self.vibe_mode = tk.BooleanVar(value=True)
        self.fps = 0
        self.last_time = time.time()
        self.frame_count = 0
        self.memory = MemoryManager()
        self.cpu = ARM7TDMI(self.memory)
        self.vibe_palette = VibeModePalette()
        self.create_ui()
        self.setup_test_rom()
        self.root.bind("<KeyPress>", self.handle_keypress)

    def create_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            main_frame,
            width=SCREEN_WIDTH*2,
            height=SCREEN_HEIGHT*2,
            bg="black"
        )
        self.canvas.pack(pady=5)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)

        self.run_button = ttk.Button(control_frame, text="Run", command=self.toggle_run)
        self.run_button.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="Load ROM", command=self.load_rom).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Step", command=self.step).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Reset", command=self.reset).pack(side=tk.LEFT, padx=5)

        ttk.Checkbutton(
            control_frame, text="Vibe Mode", variable=self.vibe_mode, command=self.toggle_vibe_mode
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="Cycle Palette", command=self.cycle_palette).pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Vibe Refresh:").pack(side=tk.LEFT, padx=5)
        refresh_slider = ttk.Scale(control_frame, from_=1, to_=20, orient=tk.HORIZONTAL)
        refresh_slider.set(5)
        refresh_slider.bind("<ButtonRelease-1>", lambda e: self.vibe_palette.set_refresh_rate(refresh_slider.get()))
        refresh_slider.pack(side=tk.LEFT, padx=5)

        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=5)

        self.status_var = tk.StringVar(value="Status: Ready")
        ttk.Label(info_frame, textvariable=self.status_var, font=("Courier", 10)).pack(side=tk.LEFT, padx=5)

        self.fps_var = tk.StringVar(value="FPS: 0")
        ttk.Label(info_frame, textvariable=self.fps_var, font=("Courier", 10)).pack(side=tk.RIGHT, padx=5)

        cpu_frame = ttk.LabelFrame(main_frame, text="CPU Info")
        cpu_frame.pack(fill=tk.X, pady=5)

        self.cpu_info_var = tk.StringVar(value="PC: 0x00000000  CPSR: 0x00000000")
        ttk.Label(cpu_frame, textvariable=self.cpu_info_var, font=("Courier", 10)).pack(side=tk.LEFT, padx=5)

    def handle_keypress(self, event):
        key_map = {
            "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right",
            "z": "A", "x": "B", "Return": "Start", "BackSpace": "Select"
        }
        if event.keysym in key_map:
            self.status_var.set(f"Status: Key {key_map[event.keysym]} pressed")

    def toggle_run(self):
        self.running = not self.running
        self.run_button.config(text="Pause" if self.running else "Run")
        self.status_var.set("Status: Running" if self.running else "Status: Paused")
        if self.running:
            self.run()

    def toggle_vibe_mode(self):
        self.status_var.set("Status: Vibe Mode " + ("ON" if self.vibe_mode.get() else "OFF"))
        self.update_display()

    def cycle_palette(self):
        if self.vibe_mode.get():
            new_palette = self.vibe_palette.cycle_palette()
            self.status_var.set(f"Status: Palette - {new_palette}")
            self.update_display()

    def load_rom(self):
        filename = filedialog.askopenfilename(
            title="Select GBA ROM",
            filetypes=[("GBA ROMs", "*.gba"), ("All Files", "*.*")]
        )
        if filename:
            try:
                with open(filename, "rb") as f:
                    rom_data = f.read()
                self.memory.load_rom(rom_data)
                self.reset()
                self.status_var.set(f"Status: Loaded ROM - {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load ROM: {e}")

    def reset(self):
        self.cpu.reset()
        self.memory.warnings = []
        self.update_display()
        self.status_var.set("Status: Reset")

    def step(self):
        try:
            self.cpu.step()
            self.update_display()
            self.update_cpu_info()
            self.show_memory_warnings()
        except Exception as e:
            self.running = False
            self.run_button.config(text="Run")
            self.status_var.set(f"Status: Error - {e}")

#!/usr/bin/env python3
"""test.py - Optimized GBA emulator test application with no PNG dependency and vibe mode support."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import time
import os

# Emulator constants and import
try:
    from gba_emu_enhanced import ARM7TDMI, SCREEN_WIDTH, SCREEN_HEIGHT, GAMEPAK_ROM_START
except ImportError:
    SCREEN_WIDTH = 240
    SCREEN_HEIGHT = 160
    GAMEPAK_ROM_START = 0x08000000

    class ARM7TDMI:
        def __init__(self, memory):
            self.memory = memory
            self.registers = [0] * 16
            self.reset()
            self.cycle_count = 0

        def reset(self):
            self.registers = [0] * 16
            self.pc = GAMEPAK_ROM_START
            self.CPSR = 0x0000001F  # System mode, ARM state

        def step(self):
            # Test ROM: ADD R0, R0, #1; loop
            self.registers[0] = (self.registers[0] + 1) & 0xFFFFFFFF
            self.pc = GAMEPAK_ROM_START + (4 if self.pc + 4 >= GAMEPAK_ROM_START + 12 else self.pc + 4 - GAMEPAK_ROM_START)
            self.cycle_count += 1

        def __getattr__(self, name):
            if name.startswith('get_'):
                # Return zeros for flags/register access stubs
                return lambda *args, **kwargs: 0
            raise AttributeError

# Memory manager
class MemoryManager:
    REGION_MAP = [
        (0x00000000, 0x00004000, 'bios'),
        (0x02000000, 0x02040000, 'ewram'),
        (0x03000000, 0x03008000, 'iwram'),
        (0x04000000, 0x04000400, 'io_regs'),
        (0x05000000, 0x05000400, 'palette'),
        (0x06000000, 0x06018000, 'vram'),
        (0x07000000, 0x07000400, 'oam'),
        (0x08000000, None, 'rom'),  # end determined by length
        (0x0E000000, 0x0E010000, 'sram')
    ]

    def __init__(self):
        self.bios = bytearray(16 * 1024)
        self.ewram = bytearray(256 * 1024)
        self.iwram = bytearray(32 * 1024)
        self.io_regs = bytearray(1024)
        self.palette = bytearray(1024)
        self.vram = bytearray(96 * 1024)
        self.oam = bytearray(1024)
        self.sram = bytearray(64 * 1024)
        self.rom = bytearray()
        self.warnings = []

    def load_bios(self, data: bytes):
        size = min(len(data), len(self.bios))
        self.bios[:size] = data[:size]
        if len(data) > len(self.bios):
            self.warnings.append(f"BIOS truncated to {len(self.bios)} bytes")

    def load_rom(self, data: bytes):
        self.rom = bytearray(data)
        print(f"Loaded {len(data)} bytes of ROM")

    def map_address(self, addr: int):
        for start, end, name in self.REGION_MAP:
            end = end or (start + len(self.rom))
            if start <= addr < end:
                offset = addr - start
                return name, offset
        self.warnings.append(f"Unmapped access 0x{addr:08X}")
        return 'invalid', 0

    def read(self, addr: int, size: int = 1):
        region, offset = self.map_address(addr)
        if region == 'invalid':
            return 0
        mem = getattr(self, region)
        if offset + size <= len(mem):
            return int.from_bytes(mem[offset:offset+size], 'little')
        self.warnings.append(f"Out of bounds read at {region} offset 0x{offset:X}")
        return 0

    def write(self, addr: int, value: int, size: int = 1):
        region, offset = self.map_address(addr)
        if region in ('invalid', 'rom', 'bios'):
            self.warnings.append(f"Illegal write to {region} 0x{addr:08X}")
            return
        mem = getattr(self, region)
        if offset + size <= len(mem):
            mem[offset:offset+size] = value.to_bytes(size, 'little')
        else:
            self.warnings.append(f"Out of bounds write at {region} offset 0x{offset:X}")

# Vibe mode palette
class VibeModePalette:
    def __init__(self, refresh_rate=5):
        self.palettes = {
            'synthwave': ['#ff00ff', '#00ffff', '#ff0099', '#9900ff'],
            'retrowave': ['#fd3777', '#3636b2', '#2ce8f5', '#fafd0f'],
            'cyberpunk': ['#00FFFF', '#FF00FF', '#FFFF00', '#00FF00'],
            'vaporwave': ['#91D5FF', '#FF9EEE', '#55FFFF', '#FFD4FF']
        }
        self.current = 'synthwave'
        self.idx = 0
        self.rate = max(1, refresh_rate)
        self.counter = 0

    def get_color(self):
        return self.palettes[self.current][self.idx]

    def update(self):
        self.counter = (self.counter + 1) % self.rate
        if self.counter == 0:
            self.idx = (self.idx + 1) % len(self.palettes[self.current])

    def cycle(self):
        keys = list(self.palettes)
        self.current = keys[(keys.index(self.current) + 1) % len(keys)]
        self.idx = 0
        return self.current

# Main application
class GBAEmulatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MEOWTASTIC GBA Emulator Test")
        self.geometry(f"{SCREEN_WIDTH*2}x{SCREEN_HEIGHT*2+200}")
        self.running = False
        self.vibe_on = tk.BooleanVar(value=True)
        self.memory = MemoryManager()
        self.cpu = ARM7TDMI(self.memory)
        self.palette = VibeModePalette()
        self._last_time = time.time()
        self._frames = 0
        self._build_ui()
        self._reset()

    def _build_ui(self):
        canvas = tk.Canvas(self, width=SCREEN_WIDTH*2, height=SCREEN_HEIGHT*2, bg='black')
        canvas.pack(pady=5)
        controls = ttk.Frame(self)
        controls.pack(fill='x', pady=5)
        ttk.Button(controls, text='Run', command=self._toggle).pack(side='left')
        ttk.Button(controls, text='Load ROM', command=self._load_rom).pack(side='left')
        ttk.Button(controls, text='Step', command=self._step).pack(side='left')
        ttk.Button(controls, text='Reset', command=self._reset).pack(side='left')
        ttk.Checkbutton(controls, text='Vibe Mode', variable=self.vibe_on).pack(side='left')
        ttk.Button(controls, text='Cycle Palette', command=self._cycle).pack(side='left')
        self.status = ttk.Label(self, text='Status: Ready', font=('Courier', 10))
        self.status.pack(side='left', padx=5)
        self.fps_label = ttk.Label(self, text='FPS: 0', font=('Courier', 10))
        self.fps_label.pack(side='right', padx=5)
        self.canvas = canvas

    def _toggle(self):
        self.running = not self.running
        self.title('Paused' if not self.running else 'Running')
        if self.running:
            self._run()

    def _run(self):
        if not self.running:
            return
        self._step()
        self.after(0, self._run)

    def _step(self):
        self.cpu.step()
        self._update_display()
        self._update_fps()

    def _update_display(self):
        if self.vibe_on.get():
            self.palette.update()
            color = self.palette.get_color()
            self.canvas.configure(bg=color)

    def _update_fps(self):
        self._frames += 1
        now = time.time()
        if now - self._last_time >= 1:
            self.fps_label.config(text=f"FPS: {self._frames}")
            self._frames = 0
            self._last_time = now

    def _cycle(self):
        name = self.palette.cycle()
        self.status.config(text=f"Palette: {name}")

    def _load_rom(self):
        file = filedialog.askopenfilename(filetypes=[('GBA ROMs','*.gba')])
        if file:
            with open(file, 'rb') as f:
                self.memory.load_rom(f.read())
            self._reset()
            self.status.config(text=f"Loaded {os.path.basename(file)}")

    def _reset(self):
        self.cpu.reset()
        self.memory.warnings.clear()
        self.palette.idx = 0
        self._update_display()
        self.status.config(text='Status: Reset')

if __name__ == '__main__':
    GBAEmulatorApp().mainloop()
