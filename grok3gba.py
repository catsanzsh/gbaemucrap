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
    # Constants already defined above

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
        self.c        self.memory = MemoryManager()
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

        # Refresh rate slider
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
        # Map keys to GBA buttons (stub for future implementation)
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

    def run(self):
        if not self.running:
            return
        try:
            # Target ~280,000 cycles per frame (16.78 MHz / 60 FPS)
            cycles_per_frame = 280000 // 60
            for _ in range(cycles_per_frame // 100):
                for _ in range(100):
                    if not self.running:
                        break
                    self.cpu.step()
            self.update_display()
            self.update_cpu_info()
            self.calculate_fps()
            self.show_memory_warnings()
            self.root.after(16, self.run)  # ~60 FPS (1000ms / 60 ≈ 16.67ms)
        except Exception as e:
            self.running = False
            self.run_button.config(text="Run")
            self.status_var.set(f"Status: Error - {e}")

    def show_memory_warnings(self):
        if self.memory.warnings:
            self.status_var.set(f"Status: Warning - {self.memory.warnings[-1]}")
            self.memory.warnings = []

    def update_display(self):
        self.canvas.delete("all")
        if self.vibe_mode.get():
            self.draw_vibe_mode()
        else:
            self.draw_normal_mode()

    def draw_vibe_mode(self):
        self.vibe_palette.update()
        base_color = self.vibe_palette.get_color()
        self.canvas.create_rectangle(
            0, 0, SCREEN_WIDTH*2, SCREEN_HEIGHT*2,
            fill="black", outline=""
        )
        for i in range(16):
            reg_val = self.cpu.get_reg(i)
            x = (reg_val & 0xFF) * (SCREEN_WIDTH*2/256)
            y = ((reg_val >> 8) & 0xFF) * (SCREEN_HEIGHT*2/256)
            size = ((reg_val >> 16) & 0x3F) + 10
            r = min((reg_val & 0xFF), 255)
            g = min(((reg_val >> 8) & 0xFF), 255)
            b = min(((reg_val >> 16) & 0xFF), 255)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.canvas.create_oval:
                x-size, y-size, x+size, y+size,
                fill=color, outline=base_color, width=2
            )
        read_x = (self.memory.last_read_addr & 0xFFFF) % (SCREEN_WIDTH*2)
        read_y = ((self.memory.last_read_addr >> 16) & 0xFFFF) % (SCREEN_HEIGHT*2)
        self.canvas.create_line(
            0, read_y, SCREEN_WIDTH*2, read_y,
            fill=base_color, width=1, dash=(4, 4)
        )
        self.canvas.create_line(
            read_x, 0, read_x, SCREEN_HEIGHT*2,
            fill=base_color, width=1, dash=(4, 4)
        )
        pc = self.cpu.get_pc()
        cpsr = self.cpu.CPSR
        self.canvas.create_text(
            SCREEN_WIDTH, 20,
            text=f"PC: 0x{pc:08X} | CPSR: 0x{cpsr:08X}",
            fill=base_color, font=("Courier", 12)
        )

    def draw_normal_mode(self):
        cell_size = 4
        cols = SCREEN_WIDTH*2 // cell_size
        rows = SCREEN_HEIGHT*2 // cell_size
        for y in range(rows):
            for x in range(cols):
                addr = x + y * cols
                if addr < len(self.memory.vram):
                    val = self.memory.vram[addr]
                    color = f"#{val:02x}{val:02x}{val:02x}"
                    self.canvas.create_rectangle(
                        x * cell_size, y * cell_size,
                        (x+1) * cell_size, (y+1) * cell_size,
                        fill=color, outline=""
                    )
        pc = self.cpu.get_pc()
        cpsr = self.cpu.CPSR
        self.canvas.create_text(
            SCREEN_WIDTH, 20,
            text=f"PC: 0x{pc:08X} | CPSR: 0x{cpsr:08X}",
            fill="white", font=("Courier", 12)
        )

    def update_cpu_info(self):
        pc = self.cpu.get_pc()
        cpsr = self.cpu.CPSR
        mode = self.cpu.get_current_mode()
        mode_names = {
            0x10: "USR", 0x11: "FIQ", 0x12: "IRQ",
            0x13: "SVC", 0x17: "ABT", 0x1B: "UND", 0x1F: "SYS"
        }
        mode_str = mode_names.get(mode, f"UNK({mode:02X})")
        n = "N" if self.cpu.get_flag_N() else "-"
        z = "Z" if self.cpu.get_flag_Z() else "-"
        c = "C" if self.cpu.get_flag_C() else "-"
        v = "V" if self.cpu.get_flag_V() else "-"
        t = "T" if self.cpu.get_flag_T() else "-"
        info = f"PC: 0x{pc:08X}  CPSR: 0x{cpsr:08X} [{n}{z}{c}{v}{t}] Mode: {mode_str}"
        self.cpu_info_var.set(info)

    def calculate_fps(self):
        self.frame_count += 1
        current_time = time.time()
        elapsed = current_time - self.last_time
        if elapsed >= 1.0:
            self.fps = self.frame_count / elapsed
            self.fps_var.set(f"FPS: {self.fps:.1f}")
            self.frame_count = 0
            self.last_time = current_time

    def setup_test_rom(self):
        # Test ROM: Infinite loop that increments R0
        # MOV R0, #0
        # loop:
        # ADD R0, R0, #1
        # B loop
        test_rom = bytearray()
        instructions = [
            0xE3A00000,  # MOV R0, #0
            0xE2800001,  # ADD R0, R0, #1
            0xEAFFFFFC   # B loop
        ]
        for instr in instructions:
            test_rom.extend(struct.pack("<I", instr))
        while len(test_rom) < 1024:
            test_rom.extend(b'\x00\x00\x00\x00')
        self.memory.load_rom(test_rom)
        self.cpu.set_pc(GAMEPAK_ROM_START)
        for i in range(len(self.memory.vram)):
            self.memory.vram[i] = i % 256
        self.status_var.set("Status: Test ROM loaded")

def main():
    root = tk.Tk()
    app = GBAEmulatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
