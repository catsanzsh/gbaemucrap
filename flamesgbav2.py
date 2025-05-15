# gba_emu_enhanced.py
# Meowtastic! This is a purring GBA emulator by CATSEEK R1. Purrrr.
import tkinter as tk
from tkinter import filedialog
import struct
import time
import array

# --- Constants - GBA Specs ---
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 160
CPU_FREQ = 16777216  # 16.78 MHz - Super fast for its time, meow!
CYCLES_PER_FRAME = CPU_FREQ // 60  # Roughly, timing’s tricky, purr.

# --- Memory Map - So many addresses to explore! ---
BIOS_START = 0x00000000
BIOS_SIZE = 0x4000  # 16KB
EWRAM_START = 0x02000000  # On-board Work RAM
EWRAM_SIZE = 0x40000  # 256KB
IWRAM_START = 0x03000000  # On-chip Work RAM
IWRAM_SIZE = 0x8000  # 32KB
IO_REG_START = 0x04000000
IO_REG_SIZE = 0x400  # Loads of registers
PALETTE_RAM_START = 0x05000000
PALETTE_RAM_SIZE = 0x400  # 1KB
VRAM_START = 0x06000000
VRAM_SIZE = 0x18000  # 96KB
OAM_START = 0x07000000
OAM_SIZE = 0x400  # 1KB
GAMEPAK_ROM_START = 0x08000000  # Where the game lives, meow!

# --- CPU Modes - Lots of ways to be a CPU! ---
MODE_USER = 0x10
MODE_FIQ = 0x11
MODE_IRQ = 0x12
MODE_SUPERVISOR = 0x13
MODE_ABORT = 0x17
MODE_UNDEFINED = 0x1B
MODE_SYSTEM = 0x1F  # Default mode, purr.

# --- ARM7TDMI CPU - The brains of the operation! Purrrr. ---
class ARM7TDMI:
    def __init__(self, memory_manager):
        self.R = array.array('L', [0]*16)  # R0-R15, general purpose registers, uint32
        # Banked registers for different modes, quite a setup!
        self.R_banked = {
            MODE_FIQ: array.array('L', [0]*7),  # R8-R14_fiq
            MODE_IRQ: array.array('L', [0]*2),  # R13-R14_irq
            MODE_SUPERVISOR: array.array('L', [0]*2),  # R13-R14_svc
            MODE_ABORT: array.array('L', [0]*2),  # R13-R14_abt
            MODE_UNDEFINED: array.array('L', [0]*2),  # R13-R14_und
        }
        self.CPSR = MODE_SYSTEM  # Current Program Status Register - Quite the star!
        self.SPSR = {  # Saved Program Status Registers for each mode
            MODE_FIQ: 0, MODE_IRQ: 0, MODE_SUPERVISOR: 0, MODE_ABORT: 0, MODE_UNDEFINED: 0
        }
        self.memory = memory_manager  # The memory bus, meow!
        self.cycles = 0  # Cycle counter for timing

        self.lookup_arm = self.generate_arm_lookup()
        self.lookup_thumb = self.generate_thumb_lookup()
        
        # GBA BIOS is small, loading a dummy one for now
        # Real BIOS is copyrighted, so [COPYRIGHT NOVA] says we use a placeholder, meow!
        dummy_bios = [0x00, 0x00, 0xA0, 0xE1] * (BIOS_SIZE // 4)  # MOV R0, R0 (NOP)
        self.memory.load_bios(bytearray(dummy_bios))
        self.reset()  # Let’s reset this kitty!

    def reset(self):
        self.R = array.array('L', [0]*16)
        for mode_regs in self.R_banked.values():
            for i in range(len(mode_regs)):
                mode_regs[i] = 0
        self.CPSR = MODE_SYSTEM | 0xC0  # IRQ and FIQ disabled
        self.R[15] = BIOS_START  # PC starts at BIOS entry point, meow!
        self.set_thumb_mode(False)  # Start in ARM state, purr.
        print("CPU Reset, purrrr... PC at 0x{:08X}".format(self.R[15]))

    def get_reg(self, r_idx):
        # Register banking logic, a bit of a puzzle!
        current_mode = self.CPSR & 0x1F
        if r_idx < 8: return self.R[r_idx]
        if current_mode == MODE_FIQ:
            if r_idx >= 8 and r_idx <= 14: return self.R_banked[MODE_FIQ][r_idx - 8]
        # Other modes bank R13, R14
        if r_idx == 13:
            if current_mode in [MODE_IRQ, MODE_SUPERVISOR, MODE_ABORT, MODE_UNDEFINED]:
                return self.R_banked[current_mode][0]
        if r_idx == 14:
            if current_mode in [MODE_IRQ, MODE_SUPERVISOR, MODE_ABORT, MODE_UNDEFINED]:
                return self.R_banked[current_mode][1]
        return self.R[r_idx]

    def set_reg(self, r_idx, val):
        val &= 0xFFFFFFFF  # Ensure 32-bit, meow!
        current_mode = self.CPSR & 0x1F
        if r_idx < 8: self.R[r_idx] = val; return
        if current_mode == MODE_FIQ:
            if r_idx >= 8 and r_idx <= 14: self.R_banked[MODE_FIQ][r_idx - 8] = val; return
        if r_idx == 13:
            if current_mode in [MODE_IRQ, MODE_SUPERVISOR, MODE_ABORT, MODE_UNDEFINED]:
                self.R_banked[current_mode][0] = val; return
        if r_idx == 14:
            if current_mode in [MODE_IRQ, MODE_SUPERVISOR, MODE_ABORT, MODE_UNDEFINED]:
                self.R_banked[current_mode][1] = val; return
        self.R[r_idx] = val

    def get_pc(self): return self.R[15]
    def set_pc(self, val): self.R[15] = val & 0xFFFFFFFF

    def get_flag_N(self): return (self.CPSR >> 31) & 1
    def get_flag_Z(self): return (self.CPSR >> 30) & 1
    def get_flag_C(self): return (self.CPSR >> 29) & 1
    def get_flag_V(self): return (self.CPSR >> 28) & 1
    def get_flag_T(self): return (self.CPSR >> 5) & 1

    def set_flag_N(self, bit): self.CPSR = (self.CPSR & ~(1 << 31)) | (bit << 31)
    def set_flag_Z(self, bit): self.CPSR = (self.CPSR & ~(1 << 30)) | (bit << 30)
    def set_flag_C(self, bit): self.CPSR = (self.CPSR & ~(1 << 29)) | (bit << 29)
    def set_flag_V(self, bit): self.CPSR = (self.CPSR & ~(1 << 28)) | (bit << 28)
    
    def set_thumb_mode(self, active):
        if active: self.CPSR |= (1 << 5)
        else: self.CPSR &= ~(1 << 5)

    def check_cond(self, cond):  # Conditional execution magic, meow!
        if cond == 0x0: return self.get_flag_Z() == 1  # EQ - Z set
        if cond == 0x1: return self.get_flag_Z() == 0  # NE - Z clear
        if cond == 0x2: return self.get_flag_C() == 1  # CS/HS - C set
        if cond == 0x3: return self.get_flag_C() == 0  # CC/LO - C clear
        if cond == 0x4: return self.get_flag_N() == 1  # MI - N set
        if cond == 0x5: return self.get_flag_N() == 0  # PL - N clear
        if cond == 0x6: return self.get_flag_V() == 1  # VS - V set
        if cond == 0x7: return self.get_flag_V() == 0  # VC - V clear
        if cond == 0x8: return self.get_flag_C() == 1 and self.get_flag_Z() == 0  # HI - C set and Z clear
        if cond == 0x9: return self.get_flag_C() == 0 or self.get_flag_Z() == 1  # LS - C clear or Z set
        if cond == 0xA: return self.get_flag_N() == self.get_flag_V()  # GE - N equals V
        if cond == 0xB: return self.get_flag_N() != self.get_flag_V()  # LT - N not equals V
        if cond == 0xC: return self.get_flag_Z() == 0 and (self.get_flag_N() == self.get_flag_V())  # GT - Z clear AND (N equals V)
        if cond == 0xD: return self.get_flag_Z() == 1 or (self.get_flag_N() != self.get_flag_V())  # LE - Z set OR (N not equals V)
        if cond == 0xE: return True  # AL - Always, meow!
        if cond == 0xF: return False  # NV - Never (obsolete, purr)
        return False  # Shouldn’t happen, meow!

    def step(self):  # Execute one instruction
        pc = self.get_pc()
        
        # TODO: Pipeline emulation? Maybe later, meow.
        
        if self.get_flag_T():  # THUMB mode, purr!
            opcode = self.memory.read_halfword(pc)
            self.set_pc(pc + 2)
            self.execute_thumb(opcode)
            self.cycles += 1  # Simplified cycle counting
        else:  # ARM mode, meow
            opcode = self.memory.read_word(pc)
            self.set_pc(pc + 4)
            self.execute_arm(opcode)
            self.cycles += 1  # Simplified, timing’s complex

    def execute_arm(self, opcode):
        cond = (opcode >> 28) & 0xF
        if not self.check_cond(cond):
            return  # Condition not met, skip, purr.

        # Decode the instruction type
        instr_type = (opcode >> 25) & 0x7  # Bits 27-25
        
        if instr_type == 0b000 or instr_type == 0b001:  # Data Processing / PSR Transfer
            if (opcode & 0x0FC000F0) == 0x00000090:  # Multiply instructions
                self.arm_multiply(opcode)
            elif (opcode & 0x0FB00FF0) == 0x01000090:  # SWP
                self.arm_swp(opcode)
            elif (opcode & 0x0FBF0FFF) == 0x012FFF10:  # BX and BLX (immediate)
                self.arm_bx_blx(opcode)
            elif ((opcode >> 22) & 0x3F) == 0b001000 and ((opcode >> 4) & 0xF) == 0b0000:  # MSR, MRS
                pass  # Placeholder, meow!
            else:
                self.arm_data_processing(opcode)
        elif instr_type == 0b010 or instr_type == 0b011:  # Load/Store Immediate/Register
            self.arm_load_store(opcode)
        elif instr_type == 0b100:  # Load/Store Multiple
            self.arm_load_store_multiple(opcode)
        elif instr_type == 0b101:  # Branch / Branch with Link
            self.arm_branch(opcode)
        elif instr_type == 0b110:  # Coprocessor Load/Store / Double Reg Transfer
            pass  # No coprocessors on GBA except for debugging
        elif instr_type == 0b111:  # Coprocessor Data Op / Reg Transfer / SWI
            if (opcode >> 24) & 0xF == 0xF:  # Software Interrupt (SWI)
                self.arm_swi(opcode)
            else:
                pass
        else:
            pass  # Trigger undefined instruction exception, purr

    def arm_data_processing(self, opcode):
        # Handles many operations, a big task!
        if opcode == 0xE1A00000:  # MOV R0, R0 (NOP)
            pass
        elif (opcode & 0x0FFF0FFF) == 0x01A00000:  # MOV PC, LR (common return)
            if ((opcode >> 12) & 0xF) == 15 and (opcode & 0xF) == 14:  # Rd == PC, Rm == LR
                self.set_pc(self.get_reg(14))

    def arm_load_store(self, opcode):
        is_ldr = (opcode >> 20) & 1
        is_byte = (opcode >> 22) & 1
        rn_idx = (opcode >> 16) & 0xF
        rd_idx = (opcode >> 12) & 0xF
        base_addr = self.get_reg(rn_idx)
        
        if is_ldr and rn_idx == 15:  # LDR Rx, [PC, #imm]
            offset = opcode & 0xFFF
            addr = (self.get_pc() & ~0b10) + offset  # Simplified PC alignment
            if is_byte:
                val = self.memory.read_byte(addr)
            else:
                val = self.memory.read_word(addr)  # Word aligned
            self.set_reg(rd_idx, val)
            return

    def arm_load_store_multiple(self, opcode):
        pass  # For block transfers, meow

    def arm_branch(self, opcode):
        offset = opcode & 0x00FFFFFF
        if offset & 0x00800000:  # Sign extend
            offset |= 0xFF000000
        offset <<= 2  # Word offset
        current_pc = self.get_pc()
        if (opcode >> 24) & 1:  # Link bit
            self.set_reg(14, current_pc - 4)  # LR = next instruction
        self.set_pc(current_pc + offset)

    def arm_bx_blx(self, opcode):
        rn_idx = opcode & 0xF
        target_addr = self.get_reg(rn_idx)
        if (opcode & 0x0FFFFFF0) == 0x012FFF30:  # BLX Rn
            self.set_reg(14, self.get_pc() - 4)  # LR
        self.set_thumb_mode(target_addr & 1)
        self.set_pc(target_addr & ~1)

    def arm_swi(self, opcode):
        swi_num = opcode & 0xFFFFFF
        if swi_num == 0x00:  # SoftReset
            self.set_pc(self.get_reg(14))  # Hack for testing
        elif swi_num == 0x01:  # RegisterRamReset
            self.set_pc(self.get_reg(14))
        elif swi_num == 0x02:  # Halt
            self.set_pc(self.get_reg(14))  # Hack

    def arm_multiply(self, opcode):
        pass  # Math time, meow!

    def arm_swp(self, opcode):
        pass  # Atomic swap, fancy stuff

    def execute_thumb(self, opcode):
        if (opcode >> 8) == 0b11010000:  # B (Conditional branch)
            cond = (opcode >> 8) & 0xF
            if self.check_cond(cond):
                offset = opcode & 0xFF
                if offset & 0x80: offset |= ~0xFF  # Sign extend
                offset <<= 1
                self.set_pc(self.get_pc() + offset)
        elif (opcode >> 11) == 0b11100:  # B (Unconditional)
            offset = opcode & 0x7FF
            if offset & 0x400: offset |= ~0x7FF  # Sign extend
            offset <<= 1
            self.set_pc(self.get_pc() + offset)
        elif (opcode >> 8) == 0b01000111:  # BX/BLX Rd
            rm_idx = (opcode >> 3) & 0xF
            target_addr = self.get_reg(rm_idx)
            self.set_thumb_mode(target_addr & 1)
            self.set_pc(target_addr & ~1)
        pass

    def ror(self, val, shift, bits=32):
        mask = (1 << bits) - 1
        shift %= bits
        return ((val >> shift) | (val << (bits - shift))) & mask

    def generate_arm_lookup(self): return {}  # TODO: Implement, meow!
    def generate_thumb_lookup(self): return {}  # TODO: More to do, purr!

# --- Memory Management Unit - Controls all memory access! ---
class Memory:
    def __init__(self):
        self.bios = bytearray(BIOS_SIZE)
        self.ewram = bytearray(EWRAM_SIZE)
        self.iwram = bytearray(IWRAM_SIZE)
        self.gamepak_rom = bytearray()
        self.io_regs = bytearray(IO_REG_SIZE)
        self.palette_ram = bytearray(PALETTE_RAM_SIZE)
        self.vram = bytearray(VRAM_SIZE)
        self.oam = bytearray(OAM_SIZE)
        self.ppu = None
        self.keypad = None

    def connect_ppu(self, ppu): self.ppu = ppu
    def connect_keypad(self, keypad): self.keypad = keypad

    def load_bios(self, data):
        if len(data) > BIOS_SIZE:
            raise ValueError("BIOS too large, meow!")
        self.bios[:len(data)] = data
        print(f"BIOS loaded, {len(data)} bytes. Purrrr.")

    def load_rom(self, data):
        self.gamepak_rom = bytearray(data)
        print(f"ROM loaded, {len(self.gamepak_rom)} bytes. Let’s play, meow!")

    def _get_memory_region_and_offset(self, addr):
        addr &= 0xFFFFFFFF
        if addr < BIOS_START + BIOS_SIZE:
            return self.bios, addr
        if EWRAM_START <= addr < EWRAM_START + 0xFFFFFF:
            return self.ewram, (addr - EWRAM_START) % EWRAM_SIZE
        if IWRAM_START <= addr < IWRAM_START + 0xFFFFFF:
            return self.iwram, (addr - IWRAM_START) % IWRAM_SIZE
        if IO_REG_START <= addr < IO_REG_START + 0xFFFFFF:
            offset = (addr - IO_REG_START) % IO_REG_SIZE
            return self.io_regs, offset
        if PALETTE_RAM_START <= addr < PALETTE_RAM_START + 0xFFFFFF:
            return self.palette_ram, (addr - PALETTE_RAM_START) % PALETTE_RAM_SIZE
        if VRAM_START <= addr < VRAM_START + 0xFFFFFF:
            return self.vram, (addr - VRAM_START) % VRAM_SIZE
        if OAM_START <= addr < OAM_START + 0xFFFFFF:
            return self.oam, (addr - OAM_START) % OAM_SIZE
        if GAMEPAK_ROM_START <= addr < GAMEPAK_ROM_START + len(self.gamepak_rom):
            return self.gamepak_rom, addr - GAMEPAK_ROM_START
        if 0x0E000000 <= addr < 0x0E010000:
            if not hasattr(self, 'sram'): self.sram = bytearray(0x10000)
            return self.sram, addr - 0x0E000000
        if not hasattr(self, 'dummy_unmapped'): self.dummy_unmapped = bytearray(4)
        return self.dummy_unmapped, 0

    def read_byte(self, addr):
        mem_region, offset = self._get_memory_region_and_offset(addr)
        if mem_region is self.io_regs and addr == 0x04000130:  # KEYINPUT
            return self.keypad.get_keyinput_reg() if self.keypad else 0xFF
        if offset >= len(mem_region):
            return 0xFF
        return mem_region[offset]

    def read_halfword(self, addr):
        if addr & 1:
            addr &= ~1
        mem_region, offset = self._get_memory_region_and_offset(addr)
        if offset + 1 >= len(mem_region):
            return 0xFFFF
        return mem_region[offset] | (mem_region[offset+1] << 8)

    def read_word(self, addr):
        if addr & 3:
            addr &= ~3
        mem_region, offset = self._get_memory_region_and_offset(addr)
        if offset + 3 >= len(mem_region):
            return 0xFFFFFFFF
        return mem_region[offset] | (mem_region[offset+1] << 8) | \
               (mem_region[offset+2] << 16) | (mem_region[offset+3] << 24)

    def write_byte(self, addr, val):
        val &= 0xFF
        mem_region, offset = self._get_memory_region_and_offset(addr)
        if mem_region is self.bios or mem_region is self.gamepak_rom:
            return
        if mem_region is self.io_regs and self.ppu and self.ppu.is_ppu_register(addr):
            self.ppu.write_register_byte(addr, val)
        if offset >= len(mem_region):
            return
        mem_region[offset] = val

    def write_halfword(self, addr, val):
        val &= 0xFFFF
        if addr & 1:
            addr &= ~1
        mem_region, offset = self._get_memory_region_and_offset(addr)
        if mem_region is self.bios or mem_region is self.gamepak_rom:
            return
        if mem_region is self.io_regs and self.ppu and self.ppu.is_ppu_register(addr):
            self.ppu.write_register_halfword(addr, val)
        if offset + 1 >= len(mem_region):
            return
        mem_region[offset] = val & 0xFF
        mem_region[offset+1] = (val >> 8) & 0xFF

    def write_word(self, addr, val):
        val &= 0xFFFFFFFF
        if addr & 3:
            addr &= ~3
        mem_region, offset = self._get_memory_region_and_offset(addr)
        if mem_region is self.bios or mem_region is self.gamepak_rom:
            return
        if mem_region is self.io_regs and self.ppu and self.ppu.is_ppu_register(addr):
            self.ppu.write_register_word(addr, val)
        if offset + 3 >= len(mem_region):
            return
        mem_region[offset] = val & 0xFF
        mem_region[offset+1] = (val >> 8) & 0xFF
        mem_region[offset+2] = (val >> 16) & 0xFF
        mem_region[offset+3] = (val >> 24) & 0xFF

# --- PPU (Picture Processing Unit) - Draws all the pretty pictures! ---
class PPU:
    def __init__(self, memory):
        self.memory = memory
        self.frame_buffer = ['#000000'] * (SCREEN_WIDTH * SCREEN_HEIGHT)
        self.DISPCNT = 0x00
        self.DISPSTAT = 0x04
        self.VCOUNT = 0x06
        self.current_scanline = 0
        self.cycles_scanline = 0
        self.color_cache = {}

    def is_ppu_register(self, addr):
        offset = addr - IO_REG_START
        return 0x00 <= offset <= 0x5F

    def write_register_byte(self, addr, value):
        offset = addr - IO_REG_START
        self.memory.io_regs[offset] = value

    def write_register_halfword(self, addr, value):
        offset = addr - IO_REG_START
        self.memory.io_regs[offset] = value & 0xFF
        self.memory.io_regs[offset+1] = (value >> 8) & 0xFF
        if offset == self.DISPCNT:
            pass

    def write_register_word(self, addr, value):
        self.write_register_halfword(addr, value & 0xFFFF)
        self.write_register_halfword(addr + 2, (value >> 16) & 0xFFFF)

    def get_dispstat(self):
        vcount_setting = (self.memory.io_regs[self.DISPSTAT+1] << 8) | self.memory.io_regs[self.DISPSTAT]
        lyc_val = vcount_setting >> 8
        stat = 0
        if 160 <= self.current_scanline < 228: stat |= 1
        if self.current_scanline == lyc_val: stat |= (1 << 2)
        self.memory.io_regs[self.VCOUNT] = self.current_scanline & 0xFF
        return stat | (vcount_setting & 0xFFF8)

    def step(self, cycles):
        self.cycles_scanline += cycles
        if self.cycles_scanline >= 1232:
            self.cycles_scanline -= 1232
            if self.current_scanline < SCREEN_HEIGHT:
                self.render_scanline(self.current_scanline)
            self.current_scanline += 1
            if self.current_scanline == 160:
                if (self.memory.io_regs[self.DISPSTAT] >> 3) & 1:
                    pass
            if self.current_scanline == 228:
                self.current_scanline = 0
            self.memory.write_byte(IO_REG_START + self.VCOUNT, self.current_scanline)
            dispstat_val = self.memory.read_halfword(IO_REG_START + self.DISPSTAT)
            if (dispstat_val >> 5) & 1:
                lyc = dispstat_val >> 8
                if self.current_scanline == lyc:
                    pass

    def render_scanline(self, y):
        dispcnt = self.memory.read_halfword(IO_REG_START + self.DISPCNT)
        mode = dispcnt & 0x7
        if mode == 3:
            if (dispcnt >> 7) & 1:
                for x in range(SCREEN_WIDTH):
                    self.frame_buffer[y * SCREEN_WIDTH + x] = '#000000'
                return
            vram_offset = y * SCREEN_WIDTH * 2
            for x in range(SCREEN_WIDTH):
                if vram_offset + 1 < VRAM_SIZE:
                    color_15bit = self.memory.vram[vram_offset] | (self.memory.vram[vram_offset+1] << 8)
                    if color_15bit in self.color_cache:
                        tk_color = self.color_cache[color_15bit]
                    else:
                        r5 = (color_15bit & 0x1F)
                        g5 = (color_15bit >> 5) & 0x1F
                        b5 = (color_15bit >> 10) & 0x1F
                        r8 = (r5 * 255) // 31
                        g8 = (g5 * 255) // 31
                        b8 = (b5 * 255) // 31
                        tk_color = f"#{r8:02x}{g8:02x}{b8:02x}"
                        self.color_cache[color_15bit] = tk_color
                    self.frame_buffer[y * SCREEN_WIDTH + x] = tk_color
                else:
                    self.frame_buffer[y * SCREEN_WIDTH + x] = '#FF00FF'
                vram_offset += 2
        elif mode == 4:
            if (dispcnt >> 7) & 1:
                for x in range(SCREEN_WIDTH):
                    self.frame_buffer[y * SCREEN_WIDTH + x] = '#000000'
                return
            page_offset = 0xA000 if (dispcnt >> 4) & 1 else 0
            vram_base = page_offset + y * SCREEN_WIDTH
            for x in range(SCREEN_WIDTH):
                if vram_base < VRAM_SIZE:
                    palette_idx = self.memory.vram[vram_base]
                    pal_addr = palette_idx * 2
                    if pal_addr + 1 < PALETTE_RAM_SIZE:
                        color_15bit = self.memory.palette_ram[pal_addr] | (self.memory.palette_ram[pal_addr+1] << 8)
                        if color_15bit in self.color_cache:
                            tk_color = self.color_cache[color_15bit]
                        else:
                            r5, g5, b5 = (color_15bit&0x1F), ((color_15bit>>5)&0x1F), ((color_15bit>>10)&0x1F)
                            r8, g8, b8 = (r5*255)//31, (g5*255)//31, (b5*255)//31
                            tk_color = f"#{r8:02x}{g8:02x}{b8:02x}"
                            self.color_cache[color_15bit] = tk_color
                        self.frame_buffer[y * SCREEN_WIDTH + x] = tk_color
                    else:
                        self.frame_buffer[y * SCREEN_WIDTH + x] = '#00FF00'
                else:
                    self.frame_buffer[y * SCREEN_WIDTH + x] = '#0000FF'
                vram_base += 1
        else:
            for x in range(SCREEN_WIDTH):
                self.frame_buffer[y * SCREEN_WIDTH + x] = '#111111'

    def get_frame(self):
        return self.frame_buffer

# --- Keypad - Handles button presses, meow! ---
class Keypad:
    def __init__(self, memory_ref):
        self.memory = memory_ref
        self.key_state = 0xFFFF
        self.key_map = {
            'z': 0,      # A button
            'x': 1,      # B button
            'return': 3, # Start button (Enter key)
            'shift_r': 2,# Select button (Right Shift)
            'up': 6,     # D-Pad Up
            'down': 7,   # D-Pad Down
            'left': 5,   # D-Pad Left
            'right': 4,  # D-Pad Right
            'a': 9,      # L button (kbd 'a')
            's': 8,      # R button (kbd 's')
        }
        print("Keypad initialized. Z=A, X=B, Enter=Start, RShift=Select, Arrows=D-Pad, A=L, S=R. Purrrr.")

    def key_down(self, key_name):
        key_name = key_name.lower()
        if key_name in self.key_map:
            bit = self.key_map[key_name]
            self.key_state &= ~(1 << bit)
        self.update_keyinput_reg()

    def key_up(self, key_name):
        key_name = key_name.lower()
        if key_name in self.key_map:
            bit = self.key_map[key_name]
            self.key_state |= (1 << bit)
        self.update_keyinput_reg()

    def update_keyinput_reg(self):
        self.memory.io_regs[0x130] = self.key_state & 0xFF
        self.memory.io_regs[0x131] = (self.key_state >> 8) & 0xFF

    def get_keyinput_reg(self):
        return self.key_state

# --- APU, Timers, DMA, InterruptController - Stubs for now ---
class APU:
    def __init__(self, memory): self.memory = memory; print("APU Stub created. No sound yet, meow!")
    def step(self, cycles): pass
class Timers:
    def __init__(self, memory): self.memory = memory; print("Timers Stub created. Time’s ticking, purr!")
    def step(self, cycles): pass
class DMA:
    def __init__(self, memory): self.memory = memory; print("DMA Stub created. No fast transfers yet, meow!")
    def step(self, cycles): pass
class InterruptController:
    def __init__(self, memory, cpu): self.memory = memory; self.cpu = cpu; print("IRQ Stub created. No interrupts yet, purr!")
    def check_and_service_irqs(self): pass

# --- GBA Emulator Main Class - Where the magic comes together! ---
class GBAEmulator:
    def __init__(self, root_tk_window):
        self.root = root_tk_window
        self.memory = Memory()
        self.cpu = ARM7TDMI(self.memory)
        self.ppu = PPU(self.memory)
        self.keypad = Keypad(self.memory)
        self.memory.connect_ppu(self.ppu)
        self.memory.connect_keypad(self.keypad)
        self.apu = APU(self.memory)
        self.timers = Timers(self.memory)
        self.dma = DMA(self.memory)
        self.irq_controller = InterruptController(self.memory, self.cpu)
        self.setup_gui()
        self.frame_time = time.perf_counter()
        self.running = False
        self.cycles_this_frame = 0
        self.image_data_str = ""
        self.tk_image = tk.PhotoImage(width=SCREEN_WIDTH, height=SCREEN_HEIGHT)

    def setup_gui(self):
        self.root.title("CATSEEK R1’s GBA Emulator - PyGBA v0.69 Meow")
        self.root.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT + 50}")  # 1x scale
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(self.root, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, bg='black')
        self.canvas.pack()
        self.canvas_image_item_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open ROM", command=self.load_rom_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Reset", command=self.reset_emulator)
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File (Meow!)", menu=file_menu)
        self.root.config(menu=menubar)
        self.status_bar = tk.Label(self.root, text="Load a ROM, purrrr...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.root.bind('<KeyPress>', self.on_key_down)
        self.root.bind('<KeyRelease>', self.on_key_up)

    def on_key_down(self, event):
        if self.running: self.keypad.key_down(event.keysym)
            
    def on_key_up(self, event):
        if self.running: self.keypad.key_up(event.keysym)

    def load_rom_dialog(self):
        rom_path = filedialog.askopenfilename(filetypes=[("GBA ROMs", "*.gba"), ("All Files", "*.*")])
        if rom_path:
            try:
                with open(rom_path, 'rb') as f:
                    rom_data = f.read()
                self.memory.load_rom(rom_data)
                self.status_bar.config(text=f"Loaded {rom_path.split('/')[-1]}. Let’s go, meow!")
                self.reset_emulator()
                self.start_emulation()
            except Exception as e:
                self.status_bar.config(text=f"Error loading ROM: {e}")
                print(f"ROM Load Error: {e}")

    def reset_emulator(self):
        print("Resetting emulator, purrrr...")
        self.cpu.reset()
        self.cycles_this_frame = 0
        self.ppu.current_scanline = 0
        self.ppu.cycles_scanline = 0
        self.ppu.frame_buffer = ['#101010'] * (SCREEN_WIDTH * SCREEN_HEIGHT)
        self.update_display()

    def start_emulation(self):
        if not self.memory.gamepak_rom:
            self.status_bar.config(text="No ROM loaded, meow!")
            return
        self.running = True
        self.frame_time = time.perf_counter()
        print("Starting emulation loop, purrrr!")
        self.emulation_loop()

    def emulation_loop(self):
        if not self.running:
            return
        now = time.perf_counter()
        delta_time = now - self.frame_time
        cycles_to_run_this_tick = CYCLES_PER_FRAME
        executed_cycles_total = 0
        while executed_cycles_total < cycles_to_run_this_tick:
            cycles_before_step = self.cpu.cycles
            self.cpu.step()
            executed_this_step = self.cpu.cycles - cycles_before_step
            self.ppu.step(executed_this_step)
            executed_cycles_total += executed_this_step
        self.cycles_this_frame = executed_cycles_total
        if delta_time >= (1/60.0):
            self.update_display()
            self.frame_time = now
            actual_fps = 1.0 / delta_time if delta_time > 0 else 0
            self.status_bar.config(text=f"Running... PC:0x{self.cpu.get_pc():08X} CPSR:0x{self.cpu.CPSR:08X} FPS:{actual_fps:.1f} Purrrr!")
        self.root.after(1, self.emulation_loop)

    def update_display(self):
        pixels_hex = self.ppu.get_frame()
        idx = 0
        for y_pixel in range(SCREEN_HEIGHT):
            row_data = []
            for x_pixel in range(SCREEN_WIDTH):
                row_data.append(pixels_hex[idx])
                idx += 1
            self.tk_image.put("{" + " ".join(row_data) + "}", to=(0, y_pixel))
        self.root.update_idletasks()

# --- Main Execution ---
if __name__ == '__main__':
    print("Booting up CATSEEK R1’s GBA Emulator, meow!")
    main_window = tk.Tk()
    emu = GBAEmulator(main_window)
    main_window.mainloop()
    print("Emulator shut down. Hope you had fun, meow!")
