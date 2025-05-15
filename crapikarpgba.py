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
import array

# Import the GBA emulator module (assuming it's in the same directory)
try:
    from gba_emu_enhanced import ARM7TDMI, SCREEN_WIDTH, SCREEN_HEIGHT, GAMEPAK_ROM_START
except ImportError:
    print("Error: gba_emu_enhanced.py module not found!")
    sys.exit(1)

class MemoryManager:
    """Memory management for the GBA system"""
    def __init__(self):
        # Memory regions (simplified for testing)
        self.bios = bytearray(16 * 1024)        # 16KB BIOS
        self.ewram = bytearray(256 * 1024)      # 256KB external work RAM
        self.iwram = bytearray(32 * 1024)       # 32KB internal work RAM
        self.io_regs = bytearray(1024)          # 1KB I/O registers 
        self.palette = bytearray(1024)          # 1KB palette RAM
        self.vram = bytearray(96 * 1024)        # 96KB video RAM
        self.oam = bytearray(1024)              # 1KB OAM
        self.rom = bytearray()                  # ROM size varies
        self.sram = bytearray(64 * 1024)        # 64KB save RAM

        # For debug/display
        self.last_read_addr = 0
        self.last_write_addr = 0

    def load_bios(self, data):
        """Load BIOS data"""
        if len(data) <= len(self.bios):
            self.bios[:len(data)] = data
            print(f"Loaded {len(data)} bytes of BIOS data")
        else:
            print(f"Warning: BIOS data too large ({len(data)} bytes), truncating")
            self.bios[:] = data[:len(self.bios)]

    def load_rom(self, data):
        """Load ROM data"""
        self.rom = bytearray(data)
        print(f"Loaded {len(data)} bytes of ROM data")

    def map_address(self, addr):
        """Map GBA address to internal memory region"""
        addr &= 0xFFFFFFFF  # Ensure 32-bit address

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
            # For testing, let's wrap unknown addresses to open bus behavior
            print(f"Warning: Unmapped memory access at 0x{addr:08X}")
            return ("invalid", 0)

    def read_byte(self, addr):
        """Read a byte from memory"""
        self.last_read_addr = addr
        region, offset = self.map_address(addr)
        
        if region == "invalid":
            # Open bus behavior for testing
            return (addr >> 24) & 0xFF  
            
        # Get the appropriate memory region
        mem = getattr(self, region)
        
        # Check if the offset is within bounds
        if offset < len(mem):
            return mem[offset]
        else:
            print(f"Warning: Out of bounds read from {region} at offset 0x{offset:X}")
            return 0

    def read_halfword(self, addr):
        """Read a halfword (16 bits) from memory"""
        # GBA is little-endian
        self.last_read_addr = addr
        if addr & 1:  # Unaligned halfword
            print(f"Warning: Unaligned halfword read at 0x{addr:08X}")
            addr &= ~1  # Force alignment
        
        lo = self.read_byte(addr)
        hi = self.read_byte(addr + 1)
        return (hi << 8) | lo

    def read_word(self, addr):
        """Read a word (32 bits) from memory"""
        self.last_read_addr = addr
        if addr & 3:  # Unaligned word
            # GBA rotates the address for unaligned word reads
            print(f"Warning: Unaligned word read at 0x{addr:08X}")
            rot = (addr & 3) * 8
            aligned_addr = addr & ~3  # Force alignment
            val = self.read_byte(aligned_addr) | \
                 (self.read_byte(aligned_addr + 1) << 8) | \
                 (self.read_byte(aligned_addr + 2) << 16) | \
                 (self.read_byte(aligned_addr + 3) << 24)
            # Rotate right by rot bits
            return ((val >> rot) | (val << (32 - rot))) & 0xFFFFFFFF
        
        # Aligned read
        b0 = self.read_byte(addr)
        b1 = self.read_byte(addr + 1)
        b2 = self.read_byte(addr + 2)
        b3 = self.read_byte(addr + 3)
        return (b3 << 24) | (b2 << 16) | (b1 << 8) | b0

    def write_byte(self, addr, value):
        """Write a byte to memory"""
        self.last_write_addr = addr
        value &= 0xFF  # Ensure byte value
        region, offset = self.map_address(addr)
        
        if region == "invalid":
            print(f"Warning: Write to invalid address 0x{addr:08X}")
            return
            
        if region == "rom":
            print(f"Warning: Attempt to write to ROM at 0x{addr:08X}")
            return
            
        if region == "bios":
            print(f"Warning: Attempt to write to BIOS at 0x{addr:08X}")
            return
        
        # Get the appropriate memory region
        mem = getattr(self, region)
        
        # Check if the offset is within bounds
        if offset < len(mem):
            mem[offset] = value
        else:
            print(f"Warning: Out of bounds write to {region} at offset 0x{offset:X}")

    def write_halfword(self, addr, value):
        """Write a halfword (16 bits) to memory"""
        self.last_write_addr = addr
        value &= 0xFFFF  # Ensure halfword value
        
        if addr & 1:  # Unaligned halfword
            print(f"Warning: Unaligned halfword write at 0x{addr:08X}")
            addr &= ~1  # Force alignment
        
        # GBA is little-endian
        self.write_byte(addr, value & 0xFF)
        self.write_byte(addr + 1, (value >> 8) & 0xFF)

    def write_word(self, addr, value):
        """Write a word (32 bits) to memory"""
        self.last_write_addr = addr
        value &= 0xFFFFFFFF  # Ensure word value
        
        if addr & 3:  # Unaligned word
            print(f"Warning: Unaligned word write at 0x{addr:08X}")
            addr &= ~3  # Force alignment
        
        # GBA is little-endian
        self.write_byte(addr, value & 0xFF)
        self.write_byte(addr + 1, (value >> 8) & 0xFF)
        self.write_byte(addr + 2, (value >> 16) & 0xFF)
        self.write_byte(addr + 3, (value >> 24) & 0xFF)


class VibeModePalette:
    """Color palette manager for vibe mode"""
    def __init__(self):
        # Generate some cool color schemes for vibe mode
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
        
        # Current palette selection
        self.current_palette = "synthwave"
        self.palette_idx = 0
        self.refresh_rate = 5  # How often to change colors (in frames)
        self.frame_counter = 0
        
    def get_color(self):
        """Get current color from the palette"""
        palette = self.palettes[self.current_palette]
        color = palette[self.palette_idx]
        return color
        
    def update(self):
        """Update the palette (called each frame)"""
        self.frame_counter += 1
        if self.frame_counter >= self.refresh_rate:
            self.frame_counter = 0
            self.palette_idx = (self.palette_idx + 1) % len(self.palettes[self.current_palette])
            
    def cycle_palette(self):
        """Switch to the next palette"""
        palettes = list(self.palettes.keys())
        current_idx = palettes.index(self.current_palette)
        next_idx = (current_idx + 1) % len(palettes)
        self.current_palette = palettes[next_idx]
        self.palette_idx = 0
        return self.current_palette
        

class GBAEmulatorApp:
    """Main application for testing the GBA emulator"""
    def __init__(self, root):
        self.root = root
        self.root.title("MEOWTASTIC GBA Emulator Test")
        self.root.geometry(f"{SCREEN_WIDTH*2}x{SCREEN_HEIGHT*2 + 150}")
        
        # Configure variables
        self.running = False
        self.vibe_mode = tk.BooleanVar(value=True)  # Vibe mode ON by default
        self.fps = 0
        self.last_time = time.time()
        self.frame_count = 0
        
        # Memory and CPU setup
        self.memory = MemoryManager()
        self.cpu = ARM7TDMI(self.memory)
        
        # Setup vibe mode
        self.vibe_palette = VibeModePalette()
        
        # Create UI
        self.create_ui()
        
        # Setup basic test
        self.setup_test_rom()
        
    def create_ui(self):
        """Create the UI components"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas for GBA display
        self.canvas = tk.Canvas(
            main_frame,
            width=SCREEN_WIDTH*2,
            height=SCREEN_HEIGHT*2,
            bg="black"
        )
        self.canvas.pack(pady=5)
        
        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        # Buttons
        self.run_button = ttk.Button(
            control_frame,
            text="Run",
            command=self.toggle_run
        )
        self.run_button.pack(side=tk.LEFT, padx=5)
        
        load_button = ttk.Button(
            control_frame,
            text="Load ROM",
            command=self.load_rom
        )
        load_button.pack(side=tk.LEFT, padx=5)
        
        step_button = ttk.Button(
            control_frame,
            text="Step",
            command=self.step
        )
        step_button.pack(side=tk.LEFT, padx=5)
        
        reset_button = ttk.Button(
            control_frame,
            text="Reset",
            command=self.reset
        )
        reset_button.pack(side=tk.LEFT, padx=5)
        
        # Vibe mode toggle
        vibe_check = ttk.Checkbutton(
            control_frame,
            text="Vibe Mode",
            variable=self.vibe_mode,
            command=self.toggle_vibe_mode
        )
        vibe_check.pack(side=tk.LEFT, padx=5)
        
        palette_button = ttk.Button(
            control_frame,
            text="Cycle Palette",
            command=self.cycle_palette
        )
        palette_button.pack(side=tk.LEFT, padx=5)
        
        # Info frame
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=5)
        
        # Status label
        self.status_var = tk.StringVar(value="Status: Ready")
        status_label = ttk.Label(
            info_frame,
            textvariable=self.status_var,
            font=("Courier", 10)
        )
        status_label.pack(side=tk.LEFT, padx=5)
        
        # FPS label
        self.fps_var = tk.StringVar(value="FPS: 0")
        fps_label = ttk.Label(
            info_frame,
            textvariable=self.fps_var,
            font=("Courier", 10)
        )
        fps_label.pack(side=tk.RIGHT, padx=5)
        
        # CPU info frame
        cpu_frame = ttk.LabelFrame(main_frame, text="CPU Info")
        cpu_frame.pack(fill=tk.X, pady=5)
        
        # CPU info text
        self.cpu_info_var = tk.StringVar(value="PC: 0x00000000  CPSR: 0x00000000")
        cpu_info_label = ttk.Label(
            cpu_frame,
            textvariable=self.cpu_info_var,
            font=("Courier", 10)
        )
        cpu_info_label.pack(side=tk.LEFT, padx=5)
        
    def toggle_run(self):
        """Toggle between running and paused states"""
        self.running = not self.running
        if self.running:
            self.run_button.config(text="Pause")
            self.status_var.set("Status: Running")
            self.run()
        else:
            self.run_button.config(text="Run")
            self.status_var.set("Status: Paused")
            
    def toggle_vibe_mode(self):
        """Toggle vibe mode on/off"""
        if self.vibe_mode.get():
            self.status_var.set("Status: Vibe Mode ON")
        else:
            self.status_var.set("Status: Vibe Mode OFF")
        self.update_display()
        
    def cycle_palette(self):
        """Cycle through vibe mode palettes"""
        if self.vibe_mode.get():
            new_palette = self.vibe_palette.cycle_palette()
            self.status_var.set(f"Status: Palette - {new_palette}")
            self.update_display()
        
    def load_rom(self):
        """Load a ROM file"""
        filename = filedialog.askopenfilename(
            title="Select GBA ROM",
            filetypes=[
                ("GBA ROMs", "*.gba"),
                ("All Files", "*.*")
            ]
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
        """Reset the emulator"""
        self.cpu.reset()
        self.update_display()
        self.status_var.set("Status: Reset")
        
    def step(self):
        """Execute a single CPU step"""
        try:
            self.cpu.step()
            self.update_display()
            self.update_cpu_info()
        except Exception as e:
            self.running = False
            self.run_button.config(text="Run")
            self.status_var.set(f"Status: Error - {e}")
            
    def run(self):
        """Run the emulator continuously"""
        if not self.running:
            return
            
        # Execute some steps
        try:
            # Run a batch of instructions for better performance
            for _ in range(1000):  # Adjust this number for speed vs. responsiveness
                if not self.running:
                    break
                self.cpu.step()
                
            self.update_display()
            self.update_cpu_info()
            self.calculate_fps()
            
            # Schedule the next run
            self.root.after(1, self.run)
        except Exception as e:
            self.running = False
            self.run_button.config(text="Run")
            self.status_var.set(f"Status: Error - {e}")
            
    def update_display(self):
        """Update the display canvas"""
        self.canvas.delete("all")
        
        if self.vibe_mode.get():
            # Vibe mode: Draw cool patterns based on emulator state
            self.draw_vibe_mode()
        else:
            # Normal mode: Draw a simple representation of VRAM
            self.draw_normal_mode()
            
    def draw_vibe_mode(self):
        """Draw cool vibe mode graphics"""
        # Update the vibe palette
        self.vibe_palette.update()
        
        # Get base color
        base_color = self.vibe_palette.get_color()
        
        # Draw background
        self.canvas.create_rectangle(
            0, 0, SCREEN_WIDTH*2, SCREEN_HEIGHT*2,
            fill="black", outline=""
        )
        
        # Draw a cool pattern based on CPU state
        for i in range(16):
            reg_val = self.cpu.get_reg(i)
            x = (reg_val & 0xFF) * (SCREEN_WIDTH*2/256)
            y = ((reg_val >> 8) & 0xFF) * (SCREEN_HEIGHT*2/256)
            size = ((reg_val >> 16) & 0x3F) + 10
            
            # Create a cool hex color based on register value
            r = (reg_val & 0xFF)
            g = ((reg_val >> 8) & 0xFF)
            b = ((reg_val >> 16) & 0xFF)
            color = f"#{r:02x}{g:02x}{b:02x}"
            
            # Draw a circle
            self.canvas.create_oval(
                x-size, y-size, x+size, y+size,
                fill=color, outline=base_color, width=2
            )
            
        # Draw memory access indicators
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
        
        # Add text info in vibe style
        pc = self.cpu.get_pc()
        cpsr = self.cpu.CPSR
        self.canvas.create_text(
            SCREEN_WIDTH, 20,
            text=f"PC: 0x{pc:08X} | CPSR: 0x{cpsr:08X}",
            fill=base_color, font=("Courier", 12)
        )
            
    def draw_normal_mode(self):
        """Draw a simple representation of VRAM for test purposes"""
        # Draw a simple grid representing VRAM content
        cell_size = 4
        cols = SCREEN_WIDTH*2 // cell_size
        rows = SCREEN_HEIGHT*2 // cell_size
        
        for y in range(rows):
            for x in range(cols):
                # Get a byte from VRAM for visualization
                addr = x + y * cols
                if addr < len(self.memory.vram):
                    val = self.memory.vram[addr]
                    
                    # Create grayscale color
                    color = f"#{val:02x}{val:02x}{val:02x}"
                    
                    # Draw cell
                    self.canvas.create_rectangle(
                        x * cell_size, y * cell_size,
                        (x+1) * cell_size, (y+1) * cell_size,
                        fill=color, outline=""
                    )
                    
        # Add text info
        pc = self.cpu.get_pc()
        cpsr = self.cpu.CPSR
        self.canvas.create_text(
            SCREEN_WIDTH, 20,
            text=f"PC: 0x{pc:08X} | CPSR: 0x{cpsr:08X}",
            fill="white", font=("Courier", 12)
        )
    
    def update_cpu_info(self):
        """Update CPU info display"""
        pc = self.cpu.get_pc()
        cpsr = self.cpu.CPSR
        mode = self.cpu.get_current_mode()
        mode_names = {
            0x10: "USR", 0x11: "FIQ", 0x12: "IRQ",
            0x13: "SVC", 0x17: "ABT", 0x1B: "UND", 0x1F: "SYS"
        }
        mode_str = mode_names.get(mode, f"UNK({mode:02X})")
        
        # Get flag states
        n = "N" if self.cpu.get_flag_N() else "-"
        z = "Z" if self.cpu.get_flag_Z() else "-"
        c = "C" if self.cpu.get_flag_C() else "-"
        v = "V" if self.cpu.get_flag_V() else "-"
        t = "T" if self.cpu.get_flag_T() else "-"
        
        info = f"PC: 0x{pc:08X}  CPSR: 0x{cpsr:08X} [{n}{z}{c}{v}{t}] Mode: {mode_str}"
        self.cpu_info_var.set(info)
    
    def calculate_fps(self):
        """Calculate and update the FPS display"""
        self.frame_count += 1
        current_time = time.time()
        elapsed = current_time - self.last_time
        
        if elapsed >= 1.0:  # Update FPS every second
            self.fps = self.frame_count / elapsed
            self.fps_var.set(f"FPS: {self.fps:.1f}")
            self.frame_count = 0
            self.last_time = current_time
            
    def setup_test_rom(self):
        """Create a simple test ROM for testing"""
        # Create a basic test ROM with a simple infinite loop
        test_rom = bytearray()
        
        # Simple ARM program:
        # MOV R0, #0
        # loop:
        # ADD R0, R0, #1
        # B loop
        
        instructions = [
            0xE3A00000,  # MOV R0, #0
            0xE2800001,  # ADD R0, R0, #1
            0xEAFFFFFC   # B loop (-4*4=16 bytes back)
        ]
        
        for instr in instructions:
            test_rom.extend(struct.pack("<I", instr))
        
        # Pad ROM to a reasonable size
        while len(test_rom) < 1024:
            test_rom.extend(b'\x00\x00\x00\x00')
            
        # Load the test ROM
        self.memory.load_rom(test_rom)
        
        # Set PC to ROM start
        self.cpu.set_pc(GAMEPAK_ROM_START)
        
        # Fill VRAM with test pattern
        for i in range(len(self.memory.vram)):
            self.memory.vram[i] = i % 256
            
        self.status_var.set("Status: Test ROM loaded")


def main():
    """Maain entry point"""
    root = tk.Tk()
    app = GBAEmulatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
